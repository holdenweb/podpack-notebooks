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
    owner: Steve Holden
    group: Data
```

`owner` is optional and free text: nothing joins on it, and no column anywhere
holds it. The app does nonetheless declare `needs_tables={"user"}`, because a
notebook belongs to somebody and only a logged-in user may put one here — a
site that cannot satisfy that fails at boot rather than at the first query
(podpack ADR-0034). The two are not in tension: the declaration records the
dependency, and matching the string to a row is work nothing does yet.

The landing page puts each owner's notebooks under their own heading, in the
order the owners first appear in the file, with `group` as a sub-heading within
an owner. **An index where nothing has an `owner` builds exactly the page it
built before the field existed**, so a collection adopts it one entry at a time.

```bash
uv run build.py            # notebooks.yaml -> build/html-pages/
```

`build.py` drives nbconvert through its Python API — an `HTMLExporter` with
`template_name="basic"` and `embed_images = True`, plus `exclude_input` per
entry for `hide_input` — rather than by running a command. It prepends the
title comment, links a shared `common/notebooks.css` (pygments highlighting +
cell layout, which podpack-pages does not ship), and
injects MathJax 3 only where a notebook uses TeX. It writes `index.html`, one
`<slug>.html` per notebook, and `common/notebooks.css`. `mount` must match
where the site mounts the app, because the landing page links notebooks by
absolute path.

`nbconvert` and `pyyaml` are build-time tools only (the dev group); the running
need never import them, since the HTML snippets are what gets published.

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

## Contributing a collection

**Each contributor keeps their own notebooks, and their own `notebooks.yaml`,
in a GitHub repository of their own.** Ask by email to have a collection
published. The repository is then cloned, reviewed by the section above, and
published if it is appropriate — which is a judgement, not a formality, and the
reasons a notebook is declined are the ones below.

A contributor's `notebooks.yaml` is a **proposal, not an input to the build**.
It says which notebooks are offered, in what order, under what titles, and
under which `owner` and `group` — the same schema as this one, so nothing has
to be translated. What it does not do is feed `build.py`: this repository's
`notebooks.yaml` stays the single publication list, and an entry appears there
only when it has been read.

Accepting a notebook copies it to `notebooks/<contributor>/` here, and adds an
entry naming that path. It is deliberately a copy: `notebooks.yaml` is built by
the test suite, on a machine that has only this repository, so every path in it
must resolve inside the repository. Out-of-repo paths belong in `review.yaml`,
which is exactly where a fresh clone is reviewed from before anything is
accepted.

**Give every contributed entry an explicit `slug`.** Slugs are a single flat
namespace for the whole site — the built tree is one directory of
`<slug>.html` — and an absent `slug` defaults to the notebook's filename stem.
Two contributors with `analysis.ipynb` would therefore collide, and the
collision is silent: `build.py` writes the second over the first and the
landing page goes on linking to both. This is not a thin edge: 118 of the
first 551 shared a stem with another notebook, within one person's collection.
Prefixing the contributor's name is enough.

Review is reading, because nothing here is executed: a notebook's outputs are
whatever its author last saved (ADR-0001), so output that disagrees with its
code publishes exactly as it stands. Four things to look for, the first three
being the categories `review.yaml`'s `omitted:` list already uses, with 44
entries behind them:

- **Credentials and personal data travel in saved output.** This is the largest
  category by some way — 22 of the first 551 candidates, against 15 and 7 for
  the other two. A cell that once printed an API token, a connection string or
  a list of customer email addresses carries it into the published HTML — and
  images are inlined, so a screenshot does too. All three shapes turned up in
  that first pass, one of them 861 distinct addresses in a single notebook.
  The `reason:` records the shape and the count; the values were never written
  down.
- **Not yours to publish.** A collaborator's draft, a third-party manuscript, a
  tutorial reproduced verbatim. Being sent a notebook is not being given
  permission to publish it.
- **Will not convert**, and this is not merely that entry's problem. No
  conversion is wrapped in `try`, and `build_tree()` deletes the output tree
  before it starts, writing pages as it goes and `index.html` last. So one
  unconvertible notebook leaves **a half-written tree with no landing page,
  and the previous good build already gone** — verified by putting a
  non-notebook in the list: the entry before it was written, `index.html` was
  not. Convert a new collection on its own, into a throwaway `--out`, before
  adding any of it to the publication list.
- **Raw HTML in a markdown cell is served verbatim.** nbconvert passes it
  through and the pages kind renders the fragment with `| safe`, so a
  `<script>` tag in a notebook becomes a `<script>` tag on the site, inside the
  site's own origin. Read the markdown cells, not just the rendered page. This
  is the one risk that review is the only defence against, and it is the reason
  publication is by invitation rather than by pull request.

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
