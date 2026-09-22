"""Packaging invariants.

These fail at test time rather than at release time, when the consequence is
a bad artefact on PyPI that cannot be replaced — PyPI does not allow
re-uploading a version, so a mistake means burning a version number.
"""
from __future__ import annotations

import pathlib
import re

import thirdtrail

ROOT = pathlib.Path(__file__).resolve().parent.parent
PYPROJECT = (ROOT / "pyproject.toml").read_text()


def test_version_matches_pyproject():
    """The tag drives the release; the metadata drives what pip installs.

    If they disagree, `pip install thirdtrail==0.1.1` fails for a version the
    git history says exists.
    """
    declared = re.search(r'^version = "([^"]+)"', PYPROJECT, re.MULTILINE).group(1)
    assert thirdtrail.__version__ == declared, (
        f"__init__ says {thirdtrail.__version__}, pyproject says {declared}"
    )


def test_readme_exists_and_is_the_pypi_landing_page():
    readme = ROOT / "README.md"
    assert readme.exists()
    body = readme.read_text()
    assert len(body) > 1000, "the README is the PyPI page; make it earn the visit"
    assert "pip install thirdtrail" in body
    assert "elevation" in body.lower()


def test_py_typed_ships():
    """Without this marker, the type hints are invisible to consumers."""
    assert (ROOT / "src" / "thirdtrail" / "py.typed").exists()
    assert "py.typed" not in (ROOT / ".gitignore").read_text()


def test_public_api_is_explicit():
    for name in thirdtrail.__all__:
        assert hasattr(thirdtrail, name), f"{name} exported but missing"


def test_no_hardcoded_key_anywhere():
    """A live key in a published artefact is unrecoverable — it is on PyPI
    forever, in every mirror."""
    for path in (ROOT / "src").rglob("*.py"):
        assert "tt_live_" not in path.read_text().replace(
            'f"Bearer {api_key}"', ""
        ) or "tt_live_…" in path.read_text(), f"possible key literal in {path.name}"
