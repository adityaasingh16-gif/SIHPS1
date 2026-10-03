"""Relative SQLite URLs must not depend on the process working directory.

`sqlite:///mospi_ew.db` is resolved by SQLite against the CWD, so running the
test suite from the repo root created an empty database there and produced nine
spurious "no such table: projects" failures. These tests pin the resolution.
"""

import os
import pathlib
import subprocess
import sys

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
REPO = BACKEND.parent


@pytest.fixture(scope="module")
def resolver():
    """Import the helper without requiring a configured engine."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_db_url_probe", BACKEND / "app" / "database.py"
    )
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:  # pragma: no cover - engine setup may need the DB
        pytest.skip("could not import app/database.py in isolation")
    return mod._resolve_sqlite_path


def test_relative_path_is_anchored_to_backend(resolver):
    out = resolver("sqlite:///mospi_ew.db")
    assert os.path.isabs(out.replace("sqlite:///", "").split("?")[0])


def test_backend_root_is_the_backend_directory(resolver):
    out = resolver("sqlite:///mospi_ew.db")
    resolved = pathlib.Path(out.replace("sqlite:///", ""))
    assert resolved.parent == BACKEND.resolve(), (
        f"expected the DB to resolve inside {BACKEND}, got {resolved.parent}"
    )


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///:memory:",
        "postgresql://user:pw@host/db",
        "mysql+pymysql://user:pw@host/db",
    ],
)
def test_non_relative_urls_untouched(resolver, url):
    assert resolver(url) == url


def test_absolute_path_untouched(resolver):
    url = "sqlite:///C:/somewhere/else.db"
    assert resolver(url) == url


def test_query_string_preserved(resolver):
    out = resolver("sqlite:///mospi_ew.db?mode=ro")
    assert out.endswith("?mode=ro"), out


def test_real_database_still_resolves():
    """The configured DATABASE_URL must point at the populated database."""
    env = dict(os.environ)
    # conftest points the suite at a throwaway SQLite file; strip it here so
    # this subprocess exercises the *default* resolution, which must land on
    # the real, populated backend database.
    env.pop("DATABASE_URL", None)
    env["PYTHONPATH"] = str(BACKEND)
    code = (
        "from app.database import DATABASE_URL;"
        "print(DATABASE_URL)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=REPO,  # deliberately the repo root: the case that used to break
        env=env,
        timeout=180,
    )
    assert out.returncode == 0, out.stderr
    url = out.stdout.strip().splitlines()[-1]
    path = pathlib.Path(url.replace("sqlite:///", ""))
    assert path.exists(), f"resolved DB does not exist: {path}"
    assert path.stat().st_size > 1_000_000, (
        f"resolved DB looks empty ({path.stat().st_size} bytes) -- wrong file?"
    )
