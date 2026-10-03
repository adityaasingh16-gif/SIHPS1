"""Measure per-state satellite vegetation and store it in `state_vegetation`.

Fetches NASA GIBS MODIS Terra EVI tiles, decodes and inverts the published
colour map, and reduces each state to a vegetation observation per acquisition
date. Results are cached on disk by the tile fetcher, so a re-run costs
nothing for dates already measured.

    python backend/scripts/compute_vegetation.py --dry-run
    python backend/scripts/compute_vegetation.py --dates 8
    python backend/scripts/compute_vegetation.py --state "Madhya Pradesh"

The point of the dry run is that this makes real outbound requests to a public
NASA service. A full 35-state, 12-date run is a few thousand tile fetches, so
start with one date and see the numbers before committing to a history.
"""

import argparse
import os
import sys

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, BACKEND_DIR)

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database import DATABASE_URL, Base  # noqa: E402
from app import models  # noqa: E402
from app.geo import STATE_REFERENCE, sample_points  # noqa: E402
from app.vegetation import (  # noqa: E402
    EVI_LAYER,
    EVI_RESOLUTION_M,
    available_dates,
    flag_low_outliers,
    state_vegetation,
)

sys.path.insert(0, os.path.join(BACKEND_DIR, "scripts"))
from backfill_project_geo import resolve_database_url  # noqa: E402

DB_URL = resolve_database_url(DATABASE_URL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", type=int, default=1,
                    help="how many of the most recent acquisitions to process")
    ap.add_argument("--state", help="limit to one state (for spot checks)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-valid", type=float, default=0.05,
                    help="reject an observation covering less than this "
                         "fraction of its pixels")
    args = ap.parse_args()

    print(f"layer      : {EVI_LAYER}")
    print(f"database   : {DB_URL}")

    all_dates = available_dates(EVI_LAYER)
    dates = all_dates[-args.dates:] if args.dates else all_dates
    print(f"acquisitions: {len(dates)} selected from {len(all_dates)} available")
    print(f"             {dates[0]} .. {dates[-1]}")
    if not args.dry_run:
        print("\nNOTE: this makes real requests to a public NASA service.")

    states = sorted(STATE_REFERENCE)
    if args.state:
        states = [s for s in states if s.lower() == args.state.lower()]
        if not states:
            sys.exit(f"unknown state: {args.state}")
    print(f"states     : {len(states)}")
    total_pts = sum(len(sample_points(s)) for s in states)
    print(f"sample pts : {total_pts} "
          f"(~{total_pts * 2 * len(dates)} tile fetches, cached after first run)")

    if args.dry_run:
        for s in states[:3]:
            pts = sample_points(s)
            print(f"\n{s}: {len(pts)} points, e.g. "
                  + ", ".join(f"({a:.2f},{b:.2f})" for a, b in pts[:4]))
        print("\n--dry-run: nothing written.")
        return 0

    engine = _engine_for()
    Base.metadata.create_all(engine, tables=[models.StateVegetation.__table__])
    db = sessionmaker(bind=engine)()
    written = 0
    skipped = 0
    suspect_total = 0
    try:
        # Date-major on purpose. The cloud check compares a state against
        # every other state on the same acquisition, so all states for a date
        # have to be measured before any of them can be judged.
        for date in dates:
            print(f"\n=== {date} ===")
            results = {}
            pending = []
            for state in states:
                existing = db.execute(
                    text("SELECT 1 FROM state_vegetation WHERE state=:s "
                         "AND acquisition_date=:d AND source_layer=:l"),
                    {"s": state, "d": date.isoformat(), "l": EVI_LAYER},
                ).first()
                if existing:
                    skipped += 1
                    continue

                res = state_vegetation(state, date, sample_points(state))
                frac = res.get("valid_pixel_fraction", 0.0)
                if res.get("status") == "ok" and frac < args.min_valid:
                    res["status"] = "no_data"
                    res["note"] = (f"only {frac:.1%} of pixels valid, below the "
                                   f"{args.min_valid:.1%} floor")
                res["state"] = state
                res["valid_pixel_fraction"] = frac
                results[state] = res
                if res.get("status") == "ok":
                    pending.append(res)
                else:
                    print(f"  {state:<40} {res['status']}: {res.get('note','')}")

            outliers = flag_low_outliers(pending) if not args.state else set()
            suspect_total += len(outliers)

            for state, res in results.items():
                if res.get("status") != "ok":
                    continue
                mark = "  ** LOW OUTLIER?" if state in outliers else ""
                db.add(models.StateVegetation(
                    state=state,
                    acquisition_date=date,
                    evi_mean=res["evi_mean"],
                    evi_median=res.get("evi_state_median", res["evi_median"]),
                    evi_p10=res["evi_p10"],
                    evi_p90=res["evi_p90"],
                    ndvi_median=res.get("ndvi_state_median"),
                    valid_pixel_fraction=res["valid_pixel_fraction"],
                    tiles_sampled=res["tiles_sampled"],
                    source_layer=EVI_LAYER,
                    resolution_m=EVI_RESOLUTION_M,
                    status="ok",
                    low_outlier=state in outliers,
                    outlier_z=res.get("outlier_z"),
                    outlier_note=res.get("outlier_note"),
                    note=(f"{res['fetch_failures']} of "
                          f"{res.get('tiles_sampled', 0) + res['fetch_failures']} "
                          f"tiles could not be downloaded" if res.get("fetch_failures")
                          else None),
                ))
                written += 1
                ndvi = (f" ndvi={res['ndvi_state_median']:.3f}"
                        if res.get("ndvi_state_median") is not None else "")
                print(f"  {state:<40} EVI {res.get('evi_state_median', 0):.3f}"
                      f"{ndvi} (frac {res['valid_pixel_fraction']:.0%},"
                      f" {res['tiles_sampled']} tiles){mark}")
            db.commit()

        print(f"\nwrote {written} observations, skipped {skipped} already present")
        print(f"flagged {suspect_total} state-dates as low outliers")
    finally:
        db.close()
    return 0


def _engine_for():
    from sqlalchemy import create_engine
    return create_engine(
        DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
    )


def _session():
    return sessionmaker(bind=_engine_for())()


if __name__ == "__main__":
    sys.exit(main())
