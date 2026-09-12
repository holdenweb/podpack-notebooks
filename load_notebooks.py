#!/usr/bin/env python
"""Load the curated index into MongoDB as the `notebooks` and `omitted` collections.

The counterpart of build.py: where that turns the index into HTML, this turns it
into documents, so the curation can be queried rather than read. One document per
entry, keyed by slug -- the same identity the built tree and the site's URLs use.

The index has two lists. `notebooks:` is what build.py converts; `omitted:` is
what it deliberately does not, each entry carrying the `reason` it was left out
(credentials and personal data, not yours to publish, or will not convert).
build.py reads only `mount` and `notebooks`, so the second list costs it nothing
and the single file stays the record of both decisions.

A run is a *sync*, not an append: entries are upserted and any document whose
slug has left its list is deleted. That mirrors build_tree()'s promise that a
notebook removed from the index disappears from the output, and it is what makes
the script safe to re-run after every edit. Promoting an entry out of `omitted:`
into `notebooks:` therefore moves its document between collections.

    uv run load_notebooks.py                    # review.yaml -> alembic
    uv run load_notebooks.py --index notebooks.yaml
    uv run load_notebooks.py --dry-run          # say what would change, write nothing
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml
from mongoengine import Document, StringField, connect
from pymongo.errors import PyMongoError

HERE = Path(__file__).resolve().parent
DEFAULT_INDEX = HERE / "review.yaml"
DEFAULT_DB = "alembic"
DEFAULT_HOST = "mongodb://localhost:27017"


class Entry(Document):
    """The fields are exactly the index's own vocabulary -- nothing is derived
    here, because deriving a title means reading and upconverting the notebook,
    which is build.py's job and not worth doing twice with two chances to
    disagree. An entry with no `title` is one where the index defers to the
    notebook's own metadata, and that stays visible as a missing field rather
    than being silently filled in."""

    slug = StringField(required=True, unique=True)
    file = StringField(required=True)
    title = StringField()
    group = StringField()

    # Grouping is how the landing page and any review query reads the set.
    meta = {"abstract": True, "indexes": ["group"]}

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.slug}>"


class Notebook(Entry):
    # mongoengine would name the collection `notebook` from the class; the site
    # talks about them in the plural.
    meta = {"collection": "notebooks"}


class Omitted(Entry):
    """Listed in the index but not built. `reason` opens with the category, so
    the three kinds stay distinguishable without a second field to keep in step
    with the index's own wording."""

    reason = StringField(required=True)

    meta = {"collection": "omitted"}


# Which list feeds which collection, and what a missing entry in it means.
LISTS: list[tuple[str, type[Entry]]] = [("notebooks", Notebook), ("omitted", Omitted)]


def read_index(path: Path) -> dict[str, list[dict[str, Any]]]:
    """The two lists, validated here so a bad index fails before any write.

    `file` and `slug` are both required: build.py will default a missing slug to
    the file stem, but 118 of these notebooks share a stem, so a defaulted slug
    is a silent collision -- and here it would also collide on the unique key.
    Slugs must be unique across *both* lists, because promoting an entry from
    one to the other must not have to rename it."""
    spec = yaml.safe_load(path.read_text()) or {}
    lists = {name: (spec.get(name) or []) for name, _ in LISTS}
    if not any(lists.values()):
        sys.exit(f"{path}: no `notebooks:` or `omitted:` entries to load")

    seen: dict[str, str] = {}
    for name, model in LISTS:
        required = [f for f in ("file", "slug") + (("reason",) if model is Omitted else ())]
        for n, entry in enumerate(lists[name], 1):
            for field in required:
                if not entry.get(field):
                    sys.exit(f"{path}: {name}[{n}] has no `{field}` ({entry.get('file', '?')})")
            slug = str(entry["slug"])
            if slug in seen:
                sys.exit(f"{path}: slug {slug!r} used twice -- {seen[slug]} and {entry['file']}")
            seen[slug] = str(entry["file"])
    return lists


def sync(model: type[Entry], entries: list[dict[str, Any]], dry_run: bool = False) -> tuple[int, int, int]:
    """Upsert every entry into `model`'s collection, drop any document the list
    no longer names. Returns (written, unchanged, deleted)."""
    # Everything the model stores except its identity -- so adding a field to a
    # Document above is enough to make it travel, with nothing to update here.
    names = [f for f in model._fields if f not in ("id", "slug")]
    current = {str(e["slug"]): e for e in entries}
    existing = {d.slug: d for d in model.objects.only("slug", *names)}

    written = unchanged = 0
    for slug, entry in current.items():
        fields = {n: (str(entry[n]) if entry.get(n) else None) for n in names}
        was = existing.get(slug)
        if was and all(getattr(was, k) == v for k, v in fields.items()):
            unchanged += 1
            continue
        written += 1
        if not dry_run:
            # upsert rather than save(): the slug is the identity, and a rerun
            # must not depend on holding on to Mongo's _id from last time.
            model.objects(slug=slug).update_one(
                upsert=True, **{f"set__{k}": v for k, v in fields.items()}
            )

    stale = sorted(set(existing) - set(current))
    if stale and not dry_run:
        model.objects(slug__in=stale).delete()
    return written, unchanged, len(stale)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", type=Path, default=DEFAULT_INDEX, help="curation index to load (default: review.yaml)")
    ap.add_argument("--db", default=DEFAULT_DB, help=f"database name (default: {DEFAULT_DB})")
    ap.add_argument("--host", default=DEFAULT_HOST, help=f"MongoDB URI (default: {DEFAULT_HOST})")
    ap.add_argument("--dry-run", action="store_true", help="report what would change without writing")
    args = ap.parse_args()

    lists = read_index(args.index)

    # mongoengine connects lazily, so without this an unreachable server first
    # surfaces as a timeout inside the write loop, half way through the set.
    conn = connect(db=args.db, host=args.host, serverSelectionTimeoutMS=3000)
    try:
        conn.admin.command("ping")
    except PyMongoError as exc:
        sys.exit(f"cannot reach MongoDB at {args.host}: {type(exc).__name__}")

    print(f"{args.index.name} -> {args.db}")
    verb = "would write" if args.dry_run else "wrote"
    gone = "would delete" if args.dry_run else "deleted"
    for name, model in LISTS:
        written, unchanged, deleted = sync(model, lists[name], dry_run=args.dry_run)
        total = "" if args.dry_run else f", {model.objects.count()} total"
        print(f"  {model._meta['collection']:<10} {verb} {written}, unchanged {unchanged}, {gone} {deleted}{total}")


if __name__ == "__main__":
    main()
