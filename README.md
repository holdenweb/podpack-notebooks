# podpack-notebooks

A podpack app that publishes Jupyter notebooks as **static HTML** — the
rendered notebook, wrapped in the site's chrome. No kernel runs here and none
runs on the server; a notebook is converted once, on the laptop, and served as
a plain fragment.

The distribution is `podpack-notebooks`, the import name (for a site's `apps`
list) is `podpack_notebooks`, and the app answers to `notebooks` — its
blueprint's name, which keys `[site.mounts]`, `[apps.notebooks]` and its
directories on disk.

## It is the pages kind

A converted notebook is one HTML fragment per URL, titled by a leading
`<!-- title: ... -->` comment and wrapped verbatim in the chrome — exactly what
`podpack-pages` serves. So the app *is* that package's `PagesApp` under the
name `notebooks` (the pybooks pattern, from a distribution of its own):

```python
from podpack import Section
from podpack_pages.views import PagesApp, make_blueprint

site_app = PagesApp(
    blueprint=make_blueprint("notebooks"),
    url_prefix="/notebooks",
    nav=(Section("Notebooks", "notebooks.page"),),
)
```

Everything else — the routes `/notebooks/`, `/notebooks/<name>`,
`/notebooks/asset/<path>`, the data directory `<root>/notebooks/html-pages/`,
the log, the template namespace — follows from that name.

## Requirements

Python ≥ 3.12, and at runtime both **`podpack` ≥ 0.8** and
**`podpack-pages` ≥ 0.3.0**. Neither is listed in `[project.dependencies]`: both
are git-sourced, and a git dependency's `[tool.uv.sources]` entry would travel
with this distribution and break a consuming site's lock (podpack
`writing-an-app.md` rule 1). They live in the dev dependency group instead, so
the tests can build a real site, and the **consuming site installs both
itself** — `holdenweb.com` already ships `podpack-pages`. When `podpack-pages`
reaches PyPI this becomes an ordinary dependency.

## Producing the content

Notebooks are converted by `build.py`, driven by `notebooks.yaml` — the whole
curation surface. List what to publish, in what order, under what titles:

```yaml
mount: /notebooks
notebooks:
  - file: notebooks/analysis.ipynb
    title: A century of rainfall
    group: Data
```

```bash
uv run build.py            # notebooks.yaml -> build/html-pages/
```

`build.py` runs nbconvert (`--to html --template basic --embed-images`) per
notebook, prepends the title comment, links a shared `common/notebooks.css`
(pygments highlighting + cell layout, which podpack-pages does not ship), and
injects MathJax 3 only where a notebook uses TeX. It writes `index.html`, one
`<slug>.html` per notebook, and `common/notebooks.css`. `mount` must match
where the site mounts the app, because the landing page links notebooks by
absolute path.

`nbconvert` and `pyyaml` are build-time tools only (the dev group); the running
app never imports them.

## Reviewing candidates before publishing

`notebooks.yaml` is the *publication* list — short, ordered, and what `build.py`
converts by default. Deciding what belongs on it is a separate job with its own
list: `review.yaml`, a scratch candidate set of the same schema. It is not
tracked, it may point at notebooks anywhere on the laptop (outside this repo),
and it must never be renamed into `notebooks.yaml` — the tests build the real
`notebooks.yaml` on a CI machine where those outside paths do not exist, so
out-of-repo paths belong only in a file the tests never read.

`build.py` takes `--index` (which list) and `--out` (where to write), so a
review list builds into the throwaway dev site — `devsite.py`, whose `devdata/`
is gitignored — rather than into `build/`:

```bash
uv run build.py --index review.yaml --out devdata/notebooks/html-pages
uv run flask --app "devsite:create" run --port 8470
```

Then read `http://127.0.0.1:8470/notebooks/` and delete from `review.yaml` what
does not earn its place. Pages are re-read per request, so rebuild and refresh
without restarting the server. When the survivors are settled they move into
`notebooks.yaml`, and the ordinary `uv run build.py` above publishes them.

## Installing on a site

Add the git source and the import name, then push the built tree to the host's
data directory:

```toml
# pyproject.toml
[tool.uv.sources]
podpack-notebooks = { git = "…/podpack-notebooks.git", rev = "…" }

# config/app.toml
apps = ["…", "podpack_notebooks"]

[apps.notebooks]
default_title = "Notebook"   # optional; for a page that declares no title
```

```bash
# on holdenweb.com, after `uv run build.py`:
just notebooks staging --mirror     # or: ops/push-content.sh … --app notebooks --tree html-pages
```

Until a tree is pushed, the app serves a seeded placeholder saying so.

## Development

```bash
uv run pytest    # the app installs as the pages kind and serves build.py's output
uv run mypy
```
