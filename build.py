#!/usr/bin/env python
"""Convert the notebooks named in notebooks.yaml to static HTML fragments.

The counterpart of orpy's `build.py --fragments`: read the curated index, run
nbconvert per notebook to a body-only fragment, prepend the pages-kind
`<!-- title: ... -->` comment, link the shared stylesheet, add MathJax only
where a notebook uses TeX, and emit `index.html`, one `<slug>.html` per
notebook, and `common/notebooks.css` into an html-pages tree ready to push to
the notebooks app's data directory.

Static only: nbconvert renders the notebook exactly as it was last executed.
No kernel runs here, and none runs on the server.

    uv run build.py               # notebooks.yaml -> build/html-pages/
    uv run build.py --out DIR     # write the tree elsewhere
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
from pathlib import Path
from typing import Any

import nbformat
import yaml
from nbconvert import HTMLExporter
from pygments.formatters import HtmlFormatter

HERE = Path(__file__).resolve().parent
DEFAULT_INDEX = HERE / "notebooks.yaml"
DEFAULT_OUT = HERE / "build" / "html-pages"

_H1 = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)
_HAS_TEX = re.compile(r"\$|\\\(|\\\[")

# MathJax 3, configured for the delimiters nbconvert leaves as literal TeX --
# note inlineMath must be set explicitly, as v3 does not enable $...$ by default.
_MATHJAX = """\
<script>
window.MathJax = {
  tex: {
    inlineMath: [["$", "$"], ["\\\\(", "\\\\)"]],
    displayMath: [["$$", "$$"], ["\\\\[", "\\\\]"]]
  }
};
</script>
<script defer src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.min.js"></script>
"""


def _title(entry: dict[str, Any], nb: nbformat.NotebookNode, slug: str) -> str:
    """Curated title wins, then the notebook's own metadata, then a first H1,
    then the slug -- the same precedence orpy uses for its lesson titles."""
    if entry.get("title"):
        return str(entry["title"])
    if nb.metadata.get("title"):
        return str(nb.metadata["title"])
    for cell in nb.cells:
        if cell.cell_type == "markdown":
            if m := _H1.search(cell.source):
                return m.group(1)
            break
    return slug.replace("-", " ").replace("_", " ")


def _stylesheet() -> str:
    """pygments highlighting plus the little layout the `basic` template needs.

    podpack-pages ships neither, so a notebooks tree carries its own, linked by
    every fragment and served (cached) through the app's asset route -- exactly
    how pybooks carries common/course.css."""
    mono = "ui-monospace, SFMono-Regular, Menlo, monospace"
    pygments = HtmlFormatter(style="default").get_style_defs(".notebook .highlight")
    layout = f"""
/* Layout for nbconvert's `basic` template (classic .input_area/.output_area/
   .prompt classes), scoped under .notebook so it cannot touch the chrome. */
.notebook .cell {{ margin: 0 0 1.1em; }}
.notebook .prompt, .notebook .anchor-link {{ display: none; }}  /* drop In[ ]/Out[ ] gutter and heading pilcrows */
.notebook .highlight {{
  background: #f6f6ef; border: 1px solid #e7e4d4; border-radius: 6px;
}}
.notebook .highlight pre {{
  margin: 0; padding: 10px 12px; overflow-x: auto;
  font-family: {mono}; font-size: 13px; line-height: 1.5;
}}
.notebook .output_area pre, .notebook .output_text {{
  margin: .3em 0; padding: 2px 12px; overflow-x: auto; white-space: pre-wrap;
  font-family: {mono}; font-size: 13px; line-height: 1.5;
}}
.notebook .output_area img {{ max-width: 100%; height: auto; }}
.notebook table.dataframe {{ border-collapse: collapse; font-size: 13px; }}
.notebook table.dataframe th, .notebook table.dataframe td {{
  border: 1px solid #e7e4d4; padding: 3px 8px;
}}
"""
    return f"{pygments}\n{layout}"


def convert(entry: dict[str, Any], exporter: HTMLExporter) -> tuple[str, str, str]:
    """Return (slug, title, fragment) for one notebooks.yaml entry."""
    # Expand `~` and absolutes before the join: `HERE / <absolute>` yields the
    # absolute path, `HERE / <relative>` roots it at the repo, and src stays a
    # Path so .stem works below.
    src = HERE / Path(entry["file"]).expanduser()
    nb = nbformat.read(src, as_version=4)
    slug = str(entry.get("slug") or src.stem)
    title = _title(entry, nb, slug)

    exporter.exclude_input = bool(entry.get("hide_input", False))
    body, _ = exporter.from_notebook_node(nb)

    parts = [
        f"<!-- title: {title} -->",
        '<link rel="stylesheet" href="common/notebooks.css">',
        f'<div class="notebook">{body}</div>',
    ]
    if _HAS_TEX.search(body):
        parts.append(_MATHJAX)
    return slug, title, "\n".join(parts) + "\n"


def landing(mount: str, published: list[tuple[str, str, str]]) -> str:
    """The /notebooks/ index: notebooks by group, linked by absolute path so
    the links survive wherever the site mounts the app (the pybooks caveat)."""
    groups: dict[str, list[tuple[str, str]]] = {}
    for slug, title, group in published:
        groups.setdefault(group, []).append((slug, title))
    out = ["<!-- title: Notebooks -->", "<h1>Notebooks</h1>"]
    for group in groups:
        if group:
            out.append(f"<h2>{html.escape(group)}</h2>")
        out.append("<ul>")
        for slug, title in groups[group]:
            href = f"{mount.rstrip('/')}/{slug}"
            out.append(f'  <li><a href="{href}">{html.escape(title)}</a></li>')
        out.append("</ul>")
    return "\n".join(out) + "\n"


def build_tree(index: Path, out: Path) -> list[tuple[str, str, str]]:
    """Convert every notebook in `index` into an html-pages tree at `out`.

    Returns the (slug, title, group) of each published notebook. Rebuilds
    `out` from scratch so a notebook removed from the index disappears here."""
    spec = yaml.safe_load(index.read_text())
    mount = str(spec.get("mount", "/notebooks"))
    entries = spec.get("notebooks", [])

    if out.exists():
        shutil.rmtree(out)
    (out / "common").mkdir(parents=True)

    exporter = HTMLExporter(template_name="basic")
    exporter.embed_images = True

    published: list[tuple[str, str, str]] = []
    for entry in entries:
        slug, title, fragment = convert(entry, exporter)
        (out / f"{slug}.html").write_text(fragment)
        published.append((slug, title, str(entry.get("group", ""))))
        print(f"  {entry['file']}  ->  {slug}.html   ({title})")

    (out / "common" / "notebooks.css").write_text(_stylesheet())
    (out / "index.html").write_text(landing(mount, published))
    return published


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    published = build_tree(args.index, args.out)
    print(f"wrote {len(published)} notebook(s) + index.html + common/notebooks.css to {args.out}")


if __name__ == "__main__":
    main()
