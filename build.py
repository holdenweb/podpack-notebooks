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
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

import nbformat
import yaml
from nbconvert import HTMLExporter
from pygments.formatters import HtmlFormatter

HERE = Path(__file__).resolve().parent
DEFAULT_INDEX = HERE / "notebooks.yaml"
DEFAULT_OUT = HERE / "build" / "html-pages"


class Published(NamedTuple):
    """One notebook, as the landing page needs to know it.

    A named tuple rather than four positional fields: `owner` was the fourth
    thing the index could say about a notebook, and a 4-tuple of strings is the
    point at which a reader has to count commas to know which is which. Still a
    tuple, so anything unpacking the first three keeps working.

    `group` and `owner` are "" when the index does not say, never None, so the
    landing page can test them without asking which kind of absence it has.
    """

    slug: str
    title: str
    group: str
    owner: str

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


def _bucket(
    items: list["Published"], key: Callable[["Published"], str]
) -> dict[str, list["Published"]]:
    """Group `items` by `key`, keeping the order each key was first seen.

    Order comes from the index file, not from sorting: notebooks.yaml is a
    curated list, so the sequence an author chose is the sequence to publish --
    the same reason `build_tree` walks it rather than a directory.
    """
    buckets: dict[str, list["Published"]] = {}
    for item in items:
        buckets.setdefault(key(item), []).append(item)
    return buckets


def landing(mount: str, published: list["Published"]) -> str:
    """The /notebooks/ index: notebooks by owner and then by group, linked by
    absolute path so the links survive wherever the site mounts the app (the
    pybooks caveat).

    An index with no `owner` anywhere produces exactly the page it produced
    before owners existed -- group headings at h2, in first-seen order. That is
    deliberate and is pinned by a test: adding `owner` to one entry must not
    reshape the page for every collection that has not adopted the field.
    Within an owner, groups drop to h3, because the owner's heading is now
    above them and a document whose headings skip a level is a document a
    screen reader reads wrongly.
    """
    out = ["<!-- title: Notebooks -->", "<h1>Notebooks</h1>"]
    for owner, owned in _bucket(published, lambda p: p.owner).items():
        if owner:
            out.append(f"<h2>{html.escape(owner)}</h2>")
        level = 3 if owner else 2
        for group, items in _bucket(owned, lambda p: p.group).items():
            if group:
                out.append(f"<h{level}>{html.escape(group)}</h{level}>")
            out.append("<ul>")
            for item in items:
                href = f"{mount.rstrip('/')}/{item.slug}"
                out.append(f'  <li><a href="{href}">{html.escape(item.title)}</a></li>')
            out.append("</ul>")
    return "\n".join(out) + "\n"


def build_tree(index: Path, out: Path) -> list["Published"]:
    """Convert every notebook in `index` into an html-pages tree at `out`.

    Returns a `Published` per notebook. Rebuilds `out` from scratch so a
    notebook removed from the index disappears here."""
    spec = yaml.safe_load(index.read_text())
    mount = str(spec.get("mount", "/notebooks"))
    entries = spec.get("notebooks", [])

    if out.exists():
        shutil.rmtree(out)
    (out / "common").mkdir(parents=True)

    exporter = HTMLExporter(template_name="basic")
    exporter.embed_images = True

    published: list[Published] = []
    for entry in entries:
        slug, title, fragment = convert(entry, exporter)
        (out / f"{slug}.html").write_text(fragment)
        # `or ""` and not just a default: `group:` written with no value parses
        # as None, which str() would publish as the heading "None".
        published.append(Published(
            slug=slug,
            title=title,
            group=str(entry.get("group") or ""),
            owner=str(entry.get("owner") or ""),
        ))
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
