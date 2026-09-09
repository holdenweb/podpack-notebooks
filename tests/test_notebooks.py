"""The notebooks app, exercised as a real podpack site would run it.

The app is six lines of its own; what these prove is that it installs as the
pages kind (seeds its placeholder, serves fragments in chrome, rewrites its
asset links) and that build.py's output is what that app actually serves.
"""

import shutil
from pathlib import Path

import build
from conftest import SiteFactory

REPO = Path(__file__).resolve().parent.parent


def test_the_app_installs_and_seeds_its_placeholder(site: SiteFactory) -> None:
    """A fresh host has no notebooks yet, so the shipped placeholder is seeded
    and served -- proving the app registered, its data dir resolved, and the
    pages-kind HTML path titles from the leading comment."""
    client = site().test_client()
    response = client.get("/notebooks/")

    assert response.status_code == 200
    assert b"<title>Notebooks" in response.data  # titled from the placeholder's comment
    assert b"no\nnotebooks have been published" in response.data


def test_a_built_notebook_is_served(site: SiteFactory, tmp_path: Path) -> None:
    """build.py's fragment tree is what the app serves: the notebook body in
    the chrome, its stylesheet link rewritten to the app's asset route, and
    MathJax present because the sample uses TeX."""
    app = site()
    tree = tmp_path / "data" / "notebooks" / "html-pages"
    build.build_tree(REPO / "notebooks.yaml", tmp_path / "nb-out")
    shutil.copytree(tmp_path / "nb-out", tree, dirs_exist_ok=True)

    client = app.test_client()
    page = client.get("/notebooks/sample")
    assert page.status_code == 200
    assert b"hello from a static notebook" in page.data          # the code cell's output
    assert b"[0, 1, 4, 9, 16]" in page.data                      # the execute_result
    assert b"/notebooks/asset/common/notebooks.css" in page.data  # relative link rewritten
    assert b"MathJax" in page.data                               # TeX present -> injected

    css = client.get("/notebooks/asset/common/notebooks.css")
    assert css.status_code == 200
    assert b".notebook .highlight" in css.data                   # pygments, scoped

    # The landing page the build wrote replaces the seeded placeholder and
    # links the notebook by its mounted, absolute path.
    index = client.get("/notebooks/")
    assert index.status_code == 200
    assert b'href="/notebooks/sample"' in index.data


def test_mathjax_is_injected_only_when_tex_is_present() -> None:
    """The guard that keeps MathJax off pages that don't need it: it fires on
    the delimiters nbconvert leaves in the body, and not on plain prose."""
    assert build._HAS_TEX.search("prose with inline $x^2$ math")
    assert build._HAS_TEX.search(r"a display \[ y = mx + c \] block")
    assert build._HAS_TEX.search(r"or \( inline \) too")
    assert not build._HAS_TEX.search("<p>plain prose, nothing to typeset</p>")
