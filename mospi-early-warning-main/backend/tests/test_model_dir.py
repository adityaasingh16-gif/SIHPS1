"""Relative MODEL_DIR must not depend on the process working directory.

The shipped `.env` sets `MODEL_DIR=./models`. Nothing anchored it, so running
the suite from the repo root wrote a second copy of the model directory at the
root while the trained artifacts stayed in backend/models. The seed endpoint
then reported the new empty directory as `models_saved_to` and the registry
loaded nothing from it, so a reseed looked successful and quietly stopped
serving real predictions.

These tests pin the resolution, and pin that the seed endpoint and the
comparison router agree on it -- they used to compute the path independently,
so there were two places to fix and neither was covered.
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
    """Import the helper without triggering model loading."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "_model_dir_probe", BACKEND / "app" / "ml_loader.py"
    )
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:  # pragma: no cover - joblib import may fail
        pytest.skip("could not import app/ml_loader.py in isolation")
    return mod.resolve_model_dir


def test_shipped_env_value_resolves_inside_backend(resolver):
    """This is the literal value in backend/.env."""
    out = pathlib.Path(resolver("./models"))
    assert out.parent == BACKEND.resolve(), (
        f"expected the model dir to resolve inside {BACKEND}, got {out.parent}"
    )


def test_result_is_absolute(resolver):
    assert os.path.isabs(resolver("./models"))
    assert os.path.isabs(resolver("models"))


def test_bare_relative_name_is_anchored(resolver):
    assert pathlib.Path(resolver("models")) == pathlib.Path(resolver("./models"))


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_unset_falls_back_to_backend_models(resolver, raw):
    assert pathlib.Path(resolver(raw)) == (BACKEND / "models").resolve()


def test_absolute_path_untouched(resolver):
    raw = os.path.abspath(os.path.join(os.sep, "srv", "models"))
    assert resolver(raw) == raw


def test_nested_relative_path_preserved(resolver):
    out = pathlib.Path(resolver("./artifacts/models"))
    assert out == (BACKEND / "artifacts" / "models").resolve()


def test_every_module_agrees_on_the_path():
    """One definition. A second copy of this path is how the bug returned."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(BACKEND)
    code = (
        "from app.ml_loader import MODEL_DIR;"
        "from app.routers.comparison import MODEL_DIR as C;"
        "from app.routers.admin import MODEL_DIR as A;"
        "print(MODEL_DIR); print(C); print(A)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=REPO,  # deliberately the repo root: the case that used to break
        env=env,
        timeout=300,
    )
    assert out.returncode == 0, out.stderr
    paths = [pathlib.Path(line) for line in out.stdout.strip().splitlines()]
    assert len(set(paths)) == 1, f"modules disagree on MODEL_DIR: {paths}"
    assert paths[0] == (BACKEND / "models").resolve()


def test_resolved_directory_is_the_one_holding_the_trained_artifacts():
    """It has to be the populated directory, not just the right-looking path."""
    env = dict(os.environ)
    env["PYTHONPATH"] = str(BACKEND)
    code = "from app.ml_loader import MODEL_DIR; print(MODEL_DIR)"
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=REPO,
        env=env,
        timeout=300,
    )
    assert out.returncode == 0, out.stderr
    resolved = pathlib.Path(out.stdout.strip().splitlines()[-1])
    artifacts = list(resolved.glob("*.joblib"))
    assert artifacts, f"no trained models in {resolved}"
    assert (resolved / "rag_index.pkl").exists(), (
        f"rag_index.pkl missing from {resolved}"
    )


def test_repo_root_has_no_stray_model_directory():
    """The failure mode itself: a duplicate directory at the CWD."""
    stray = REPO / "models"
    assert not stray.exists(), (
        f"{stray} exists -- a relative MODEL_DIR is still being resolved "
        f"against the working directory"
    )
