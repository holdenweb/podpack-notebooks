# Architectural decision records

Why podpack-notebooks is the way it is — the pressure behind each choice, what
it cost, and what else was on the table. Records are immutable once accepted;
when a decision changes, a new record supersedes the old rather than editing it.

| | |
| --- | --- |
| [ADR-0001](0001-notebooks-are-static-html.md) | **Notebooks are published as static HTML.** Converted ahead of time by nbconvert, no kernel at build or serve time, no interactivity — the site displays notebooks, it does not host a runtime. |
| [ADR-0002](0002-reuse-the-pages-kind.md) | **Reuse podpack-pages' pages kind, depending on it dev-only.** The app is `PagesApp` under the name `notebooks`; podpack and podpack-pages are runtime imports kept out of `[project.dependencies]` so a consuming site can still lock, and it installs them itself. |
