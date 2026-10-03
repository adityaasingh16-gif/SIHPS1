import { useEffect, useMemo, useRef, useState } from "react";
import { Map as MapLibreMap, NavigationControl, ScaleControl } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { useT } from "../hooks/useT";

const INDIA_BOUNDS = [[68.0, 6.5], [97.6, 37.3]];

/**
 * Basemap sources, all keyless and verified to serve real tiles.
 *
 * OpenStreetMap is the default baseline: a real street map with place names,
 * so the map opens on recognisable geography rather than a blank fill.
 *
 * Esri services order their path as {z}/{y}/{x}; the OSM-derived servers use
 * {z}/{x}/{y}. Both are expressed as MapLibre templates so the difference stays
 * in the data rather than in code that assumes one ordering.
 */
const BASEMAPS = {
  osm: {
    id: "osm",
    labelKey: "map.basemap.osm",
    type: "raster",
    tiles: [
      "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
      "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
      "https://c.tile.openstreetmap.org/{z}/{x}/{y}.png",
    ],
    tileSize: 256,
    maxzoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  },
  none: { id: "none", labelKey: "map.basemap.none" },
  light: {
    id: "light",
    labelKey: "map.basemap.light",
    type: "raster",
    // The neutral choice for a choropleth: it gives the district shapes a
    // backdrop to sit on without competing with the shading.
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    ],
    tileSize: 256,
    maxzoom: 16,
    attribution: "Esri, HERE, Garmin, &copy; OpenStreetMap contributors",
  },
  topo: {
    id: "topo",
    labelKey: "map.basemap.topo",
    type: "raster",
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
    ],
    tileSize: 256,
    maxzoom: 16,
    attribution: "Esri, HERE, Garmin, USGS, NOAA, &copy; OpenStreetMap contributors",
  },
  satellite: {
    id: "satellite",
    labelKey: "map.basemap.satellite",
    type: "raster",
    tiles: [
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    ],
    tileSize: 256,
    maxzoom: 19,
    attribution:
      "Imagery &copy; Esri, Maxar, Earthstar Geographics, and the GIS User Community",
  },
  opentopo: {
    id: "opentopo",
    labelKey: "map.basemap.opentopo",
    type: "raster",
    tiles: ["https://a.tile.opentopomap.org/{z}/{x}/{y}.png"],
    tileSize: 256,
    maxzoom: 17,
    attribution:
      "Map data &copy; OpenStreetMap contributors, SRTM | Map style &copy; OpenTopoMap (CC-BY-SA)",
  },
};

/**
 * `labelKey`, `format` and `legend` are resolved through the translator at
 * call time. The module-level table stays a plain table: mutating it with the
 * active language would make the metric display depend on render order.
 */
const METRICS = {
  projects: {
    labelKey: "map.metric.projects",
    format: (s) => s.project_count.toLocaleString(),
    legend: ([min, max]) => [min, max.toLocaleString()],
  },
  delayedShare: {
    labelKey: "map.metric.delayedShare",
    format: (s) => `${Math.round(s.delayedShare)}%`,
    legend: () => ["0%", "100%"],
  },
  completion: {
    labelKey: "map.metric.completion",
    format: (s) => `${s.avg_completion_percent}%`,
    legend: () => ["0%", "100%"],
  },
  // Only offered when satellite data is present. EVI is a vegetation index,
  // so it gets a brown-to-green ramp rather than the purple used for
  // monitoring figures: reusing one ramp for unrelated quantities makes the
  // colours imply a comparison that is not there.
  evi: {
    labelKey: "map.metric.evi",
    format: (s, t) => (s.evi_median == null ? t("map.eviNotMeasured") : s.evi_median.toFixed(3)),
    legend: ([min, max], t) => [min.toFixed(2), t("map.legendMax", { max: max.toFixed(2) })],
  },
};

function valueFor(state, metric) {
  if (metric === "delayedShare") {
    return state.project_count ? (state.delayed_count / state.project_count) * 100 : 0;
  }
  if (metric === "completion") return state.avg_completion_percent;
  if (metric === "evi") return state.evi_median ?? 0;
  return state.project_count;
}

// EVI is only meaningful between roughly 0 and 1, so the ramp is anchored to
// that range instead of being stretched to the data. Auto-scaling would make
// a bad month look identical to a good one.
const EVI_RANGE = [0, 0.8];
const PROJECT_STOPS = ["#ede9fe", "#c4b5fd", "#a78bfa", "#7c3aed", "#5b21b6", "#4a1a94"];
const VEGETATION_STOPS = [
  "#f7f4e8",
  "#e8e0b0",
  "#c9d99b",
  "#9dc47e",
  "#5fa55f",
  "#2d7d46",
  "#14532d",
];

function rampColor(t, metric) {
  if (metric === "evi") {
    const scaled = (t - EVI_RANGE[0]) / (EVI_RANGE[1] - EVI_RANGE[0]);
    const i = Math.min(
      VEGETATION_STOPS.length - 1,
      Math.max(0, Math.round(scaled * (VEGETATION_STOPS.length - 1))),
    );
    return VEGETATION_STOPS[i];
  }
  const stops = PROJECT_STOPS;
  const i = Math.min(stops.length - 1, Math.max(0, Math.round(t * (stops.length - 1))));
  return stops[i];
}

function buildColorExpression(states, metric) {
  // EVI is fed to the ramp as an absolute value, because `rampColor` anchors
  // it to EVI_RANGE itself. Min/max normalising first would apply the range
  // twice and make a poor month shade the same as a healthy one.
  if (metric === "evi") {
    const pairs = states.map((s) => [
      s.state,
      rampColor(valueFor(s, metric), metric),
    ]);
    return ["match", ["get", "st_nm"], ...pairs.flat(), "#e5e7eb"];
  }

  const values = states.map((s) => valueFor(s, metric));
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 1;
  const span = max - min || 1;
  const pairs = states.map((s) => [
    s.state,
    rampColor((valueFor(s, metric) - min) / span, metric),
  ]);
  return ["match", ["get", "st_nm"], ...pairs.flat(), "#e5e7eb"];
}

/**
 * Choropleth of state-level monitoring figures over an India district basemap.
 *
 * Two deliberate constraints shape this component.
 *
 * First, the shading is state-level because that is the resolution the panel
 * data supports. Districts are the geometry, but every district of a state
 * receives that state's value, so the map never implies sub-state precision
 * that the underlying data does not have.
 *
 * Second, the coordinates the API returns are administrative centroids, and
 * they are only ever drawn as a labelled state marker, never as a project
 * pin. A marker standing in for hundreds of projects is a centre-of-mass
 * artefact, so it is presented as a state label and nothing more.
 */
export function StateMap({
  states = [],
  unplaced = [],
  onSelect,
  hasVegetation = false,
  eviDate = null,
}) {
  const t = useT();
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const [metricPref, setMetric] = useState("projects");
  // The satellite request can fail or come back empty while the vegetation
  // layer is selected. Rather than store an invalid choice and correct it in
  // an effect, the metric actually used is derived here, so an absent EVI
  // dataset can never shade every state a uniform zero - which would read as
  // a real and very alarming measurement.
  const metric = metricPref === "evi" && !hasVegetation ? "projects" : metricPref;
  const [basemap, setBasemap] = useState("osm");
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(null);

  // Held in a ref so the map is built once. `onSelect` is usually an inline
  // arrow in the parent, so putting it in the mount effect's dependencies
  // would give it a new identity on every render and rebuild the whole map,
  // discarding its tiles each time.
  const onSelectRef = useRef(onSelect);
  useEffect(() => {
    onSelectRef.current = onSelect;
  });

  const colorExpr = useMemo(
    () => buildColorExpression(states, metric),
    [states, metric],
  );

  // The first paint is applied when the layer is created; every later change is
  // applied by the effect below. Reading the initial value through a ref keeps
  // the map construction out of the dependency list, so a metric switch
  // recolours the existing layer instead of rebuilding the map.
  const colorExprRef = useRef(colorExpr);
  useEffect(() => {
    colorExprRef.current = colorExpr;
  });

  useEffect(() => {
    if (mapRef.current || !containerRef.current) return;

    let cancelled = false;
    let map;
    try {
      map = new MapLibreMap({
        container: containerRef.current,
        style: {
          version: 8,
          sources: {},
          layers: [{ id: "bg", type: "background", paint: { "background-color": "#f8fafc" } }],
        },
        bounds: INDIA_BOUNDS,
        fitBoundsOptions: { padding: 24 },
        attributionControl: { compact: true },
      });
    } catch (err) {
      // The usual cause is WebGL being unavailable, typically because hardware
      // acceleration is switched off. Without this the constructor throws into
      // React and the user is left looking at an empty box with no idea why.
      setFailed(
        err?.message ||
          "The map could not start. This usually means WebGL is unavailable — " +
            "try enabling hardware acceleration in your browser settings.",
      );
      return undefined;
    }
    mapRef.current = map;

    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new ScaleControl({ unit: "metric" }), "bottom-left");

    map.on("error", (e) => {
      if (cancelled) return;
      const msg = e?.error?.message || String(e?.error ?? "");
      // Tile-level hiccups are noise and must not blank the map. A failure to
      // reach the boundary file, or anything fatal, has to be visible.
      const fatal =
        /webgl/i.test(msg) ||
        msg.includes("Failed to fetch") ||
        msg.includes("404") ||
        msg.includes("not found");
      if (fatal) setFailed(msg);
    });

    map.on("load", async () => {
      if (cancelled) return;
      try {
        const geojson = await fetch(
          new URL("../data/india_states.geojson", import.meta.url),
        ).then((r) => r.json());
        if (cancelled) return;

        map.addSource("districts", { type: "geojson", data: geojson });

        map.addLayer({
          id: "district-fill",
          type: "fill",
          source: "districts",
          paint: { "fill-color": colorExprRef.current, "fill-opacity": 0.75 },
        });
        map.addLayer({
          id: "district-line",
          type: "line",
          source: "districts",
          paint: {
            "line-color": "#ffffff",
            "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.4, 7, 1.4],
          },
        });

        map.on("click", "district-fill", (e) => {
          const name = e.features?.[0]?.properties?.st_nm;
          if (name) onSelectRef.current?.(name);
        });
        map.on("mouseenter", "district-fill", () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", "district-fill", () => {
          map.getCanvas().style.cursor = "";
        });

        setReady(true);
      } catch (err) {
        if (!cancelled) setFailed(String(err));
      }
    });

    map.fitBounds(INDIA_BOUNDS, { padding: 24, duration: 0 });

    return () => {
      cancelled = true;
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;
    map.setPaintProperty("district-fill", "fill-color", colorExpr);
  }, [colorExpr, ready]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    // Only one basemap at a time. The previous source is removed before the
    // next is added so switching never leaves two raster stacks downloading
    // tiles the user is not looking at.
    if (map.getLayer("basemap-layer")) {
      map.removeLayer("basemap-layer");
      map.removeSource("basemap-source");
    }

    const cfg = BASEMAPS[basemap];
    if (!cfg || cfg.id === "none") {
      map.setPaintProperty("district-fill", "fill-opacity", 0.75);
      return;
    }

    // Build the raster source explicitly rather than spreading the config,
    // so the `id` and `label` used only by the UI cannot leak into the
    // MapLibre source object.
    map.addSource("basemap-source", {
      type: cfg.type,
      tiles: cfg.tiles,
      tileSize: cfg.tileSize,
      maxzoom: cfg.maxzoom,
      attribution: cfg.attribution,
    });
    map.addLayer(
      {
        id: "basemap-layer",
        type: "raster",
        source: "basemap-source",
        // Slightly muted so the choropleth stays the figure and the imagery
        // stays the ground beneath it.
        paint: { "raster-opacity": 0.85 },
      },
      "district-fill",
    );
    // A solid wash over satellite hides the geography it is supposed to
    // provide, so the fill is thinned when imagery is underneath.
    map.setPaintProperty(
      "district-fill",
      "fill-opacity",
      basemap === "satellite" ? 0.45 : 0.7,
    );
  }, [basemap, ready]);

  const maxValue = states.length
    ? Math.max(...states.map((s) => valueFor(s, metric)))
    : 0;
  const unplacedTotal = unplaced.reduce((a, b) => a + b.project_count, 0);

  return (
    <div className="rounded-2xl border border-line bg-raised shadow-sm">
      <div className="flex flex-col gap-3 border-b border-line p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-sm font-bold text-fg">{t("map.title")}</h3>
          <p className="text-[11px] text-fg-3">
            {metric === "evi" ? (
              t("map.subEvi", {
                when: eviDate
                  ? t("map.subEviAcquired", { date: eviDate })
                  : t("map.subEviLatest"),
              })
            ) : (
              t("map.subShaded")
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-xl border border-line bg-page p-1 text-[11px] font-semibold">
            {Object.entries(METRICS)
              // The vegetation option only appears when there is satellite
              // data to shade by. Offering it otherwise would produce an
              // empty map of confidently uniform colour.
              .filter(([key]) => key !== "evi" || hasVegetation)
              .map(([key, m]) => (
                <button
                  key={key}
                  onClick={() => setMetric(key)}
                  className={`rounded-lg px-2.5 py-1.5 transition ${
                    metric === key ? "bg-raised text-brand-hover shadow-sm" : "text-fg-2 hover:text-fg"
                  }`}
                >
                  {t(m.labelKey)}
                </button>
              ))}
          </div>
          <label className="flex items-center gap-1.5" htmlFor="basemap-select">
            <span className="text-[11px] font-semibold text-fg-2">{t("map.basemap")}</span>
            <select
              id="basemap-select"
              value={basemap}
              onChange={(e) => setBasemap(e.target.value)}
              className="rounded-xl border border-line bg-page px-2 py-1.5 text-[11px] font-semibold text-fg"
            >
              {Object.values(BASEMAPS).map((b) => (
                <option key={b.id} value={b.id}>
                  {t(b.labelKey)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      <div className="relative">
        <div ref={containerRef} className="h-[420px] w-full" />
        {failed && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-page p-6 text-center">
            <p className="text-sm font-bold text-fg">{t("map.unavailable")}</p>
            <p className="max-w-sm text-[11px] text-fg-3">
              {t("map.unavailableCause")} <code className="text-fg-2">{failed}</code>
            </p>
            <p className="max-w-sm text-[11px] text-fg-3">
              {t("map.unavailableWebgl")}
            </p>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-3 border-t border-line p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <div className="flex overflow-hidden rounded">
            {(metric === "evi" ? VEGETATION_STOPS : PROJECT_STOPS).map((c) => (
              <span key={c} className="h-3 w-7" style={{ background: c }} />
            ))}
          </div>
          <span className="text-[11px] text-fg-3">
            {metric === "evi"
              ? t("map.eviFixedScale")
              : (() => {
                  const [from, to] = METRICS[metric].legend([0, maxValue], t);
                  return t("map.legendRange", { from, to });
                })()}
          </span>
        </div>
        {unplacedTotal > 0 && (
          <p className="text-[11px] text-fg-3">
            {t("map.unplaced", {
              n: unplacedTotal.toLocaleString(),
              buckets: unplaced
                .map((b) => `${b.bucket} (${b.project_count})`)
                .join(", "),
            })}
          </p>
        )}
      </div>
    </div>
  );
}
