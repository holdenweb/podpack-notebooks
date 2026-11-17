"""The notebooks app: Jupyter notebooks published as static HTML.

A converted notebook is one HTML fragment per URL, titled by its own leading
`<!-- title: ... -->` comment and wrapped in the site's chrome -- which is the
pages kind exactly. So this is the pages app under the name `notebooks`,
installed from its own distribution: everything that differs (its data
directory, config section, mount, log, template namespace) follows from the
blueprint name, by podpack's own rules. Its `html-pages/` tree is the output of
this repository's `build.py`, which runs nbconvert over the notebooks named in
`notebooks.yaml`.

`podpack` and `podpack_pages` are imported at runtime but declared only in the
dev dependency group (see pyproject.toml and the README): a git-sourced runtime
dependency would drag its source into a consuming site's lock. A site installs
both itself -- holdenweb.com already ships podpack-pages.
"""

from podpack import Section
from podpack_pages.views import PagesApp, make_blueprint

site_app = PagesApp(
    blueprint=make_blueprint("notebooks"),
    url_prefix="/notebooks",
    nav=(Section("Notebooks", "notebooks.page"),),
    # A notebook belongs to somebody, and only a logged-in user can put one
    # here, so the `user` table is this app's dependency whether or not this
    # app reads it. Declaring it makes a site that cannot satisfy it fail at
    # boot rather than at the first query (podpack ADR-0034), and records the
    # dependency where the next reader will look.
    #
    # podpack defines the table itself, since login became core (ADR-0033), so
    # the need is satisfied by construction today. That is not a reason to
    # leave it undeclared: if login ever moves out into an app of its own, this
    # is the line that turns a silent breakage into a refusal to start.
    needs_tables=frozenset({"user"}),
)
