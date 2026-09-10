# ADR-0002: Reuse podpack-pages' pages kind, depending on it dev-only

**Status:** Accepted

**Date:** 2026-09-10

## Context

A static notebook (ADR-0001) is one titled HTML fragment per URL, wrapped in the
site's chrome — identical to what `podpack-pages` serves as its "pages kind"
(the `pybooks` app is that same code under another name). podpack-pages
explicitly supports, and has tested, building such an app from a *separate*
distribution via `podpack_pages.views.PagesApp` + `make_blueprint`.

Two things pull against simply naming it a runtime dependency. First, the app
could instead be reimplemented against `podpack` alone. Second, podpack-pages is
git-only (not on PyPI), and podpack's packaging rule (`writing-an-app.md` rule
1) is that a git-sourced entry in `[project.dependencies]` drags its
`[tool.uv.sources]` into every consuming site's resolution, so a site whose own
podpack-pages source differs can no longer `uv lock`. The same trap podpack
itself sidesteps.

## Decision

The app is `PagesApp` from `podpack_pages.views`, under the blueprint name
`notebooks` — the pybooks pattern, imported cross-distribution. Both `podpack`
and `podpack-pages` are imported at runtime but declared **only in the dev
dependency group**, with git `[tool.uv.sources]`; they are documented as
required installs with a minimum version, and the **consuming site installs
both and names their sources itself**. The build tool ships a pygments
stylesheet and a MathJax 3 loader in the content tree, because podpack-pages
ships neither.

## Consequences

The app is six lines and inherits the fragment renderer, the asset route and its
path-traversal guard, the seeded placeholder, titling-by-comment and the
`/_status` entry — none of it reimplemented, all of it already tested upstream.
holdenweb.com locks cleanly with notebooks added (verified: `uv lock` resolves
it from GitHub with no conflict), precisely because the framework deps do not
travel.

The cost is that a site using notebooks must also install podpack-pages —
holdenweb already does, so it is free here, but notebooks is not self-contained.
When podpack-pages reaches PyPI this relaxes to an ordinary version specifier
and the dev-group placement can go.

## Alternatives considered

- **Reimplement a minimal fragment server against `podpack` alone.** Saves an
  unused Markdown-tree stat and an asset route, and buys a cleaner dependency
  story — at the price of hand-writing views, a safe-path reader, chrome wiring,
  a placeholder and a full contract-test suite, forgoing verified reuse. Not
  worth it while the site already ships podpack-pages.
- **`chrome.blueprint(name, "podpack_notebooks")` with its own thin views.**
  Only buys a template namespace of its own, which a single app doesn't need;
  `render()` already resolves `notebooks/<page>` before the package default.
- **Declare podpack-pages as a normal runtime dependency.** The obvious shape,
  and the one that breaks a consuming site's lock while podpack-pages is
  git-only. Revisit when it is on PyPI.
