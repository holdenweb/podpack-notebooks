# ADR-0001: Notebooks are published as static HTML

**Status:** Accepted

**Date:** 2026-09-10

## Context

holdenweb.com wants to publish Jupyter notebooks. A notebook can reach a reader
several ways: as a live in-browser kernel (JupyterLite / Pyodide), through a
remote kernel service (Binder, thebe), or as the rendered notebook converted
once to static HTML. The site is a small content site behind a container stack
on a shared host; there is no appetite to run or maintain a compute
environment for it. Steve's words settling it: *"I'm not supporting a computing
ecosystem here."*

## Decision

Notebooks are published as **static HTML**, converted ahead of time by
`nbconvert` on the laptop and served as plain body fragments. No kernel runs —
not at build time (nbconvert renders the notebook exactly as it was last
executed) and not at request time. There is no interactivity: a reader sees the
code and its saved outputs, and cannot run or edit them.

## Consequences

A rendered notebook is then just one titled HTML fragment per URL — which is
the pages kind (ADR-0002), so no new serving machinery, no runtime compute, and
hosting is static files. Maths and syntax highlighting are resolved at build
time (a MathJax loader and a pygments stylesheet ship with the tree), because
nothing renders them at serve time.

The costs are the flip side of "static": a notebook's outputs are whatever was
saved when its author last executed it, so the author must run it before
converting; a correction means re-convert and re-push, not an edit in place; and
a reader who wants to experiment must download the notebook and run it
themselves. All accepted deliberately — the point is to *show* notebooks, not to
host a runtime.

## Alternatives considered

- **In-browser kernel (JupyterLite / Pyodide).** Real interactivity with no
  server, but a compute ecosystem to keep working, a heavy client payload, and
  squarely the thing this project is declining to be.
- **Remote kernel (Binder / thebe).** Depends on an external service and its
  availability, and puts someone else's infrastructure in the page's critical
  path.
- **A live server-side kernel.** Interactivity at the cost of arbitrary code
  execution and its security and operations burden on a shared host — not worth
  it to display a notebook.
