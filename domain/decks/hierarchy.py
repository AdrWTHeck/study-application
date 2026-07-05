"""Hierarchy helpers for '::'-separated deck/folder paths.

These pure functions are the single source of truth for how nested names are
parsed, displayed, and compared.  No database access — compose with the service
layer when you need DB queries.

Convention (mirrors Anki):
    "Science::Biology::Genetics"  → path with 3 segments
    display_name → "Genetics"
    parent_path  → "Science::Biology"

The separator constant lives here so callers never hardcode it.
"""
from __future__ import annotations

SEP = "::"


# ── Path decomposition ────────────────────────────────────────────────────────

def split_path(name: str) -> list[str]:
    """Split a potentially nested name into its segments.

    "Science::Biology" → ["Science", "Biology"]
    "Math"            → ["Math"]
    ""                → []
    """
    return [s for s in name.split(SEP) if s]


def display_name(name: str) -> str:
    """Return the leaf segment of a nested name, or the whole name if flat.

    "Science::Biology" → "Biology"
    "Math"            → "Math"
    """
    parts = split_path(name)
    return parts[-1] if parts else name


def parent_path(name: str) -> str | None:
    """Return the parent path string, or None if already top-level.

    "Science::Biology::Genetics" → "Science::Biology"
    "Math"                       → None
    """
    parts = split_path(name)
    if len(parts) <= 1:
        return None
    return SEP.join(parts[:-1])


def all_ancestor_paths(name: str) -> list[str]:
    """Return all ancestor paths from top-level down (excluding the name itself).

    "Science::Biology::Genetics" → ["Science", "Science::Biology"]
    "Math"                       → []
    """
    parts = split_path(name)
    return [SEP.join(parts[:i]) for i in range(1, len(parts))]


def depth(name: str) -> int:
    """0-based depth of the name in the hierarchy.

    "Science"                    → 0
    "Science::Biology"           → 1
    "Science::Biology::Genetics" → 2
    """
    return max(0, len(split_path(name)) - 1)


# ── Prefix / subtree checks ───────────────────────────────────────────────────

def is_child_of(name: str, prefix: str) -> bool:
    """True if *name* is a direct or indirect descendant of *prefix*.

    "Science::Biology"           is_child_of "Science"          → True
    "Science::Biology::Genetics" is_child_of "Science"          → True
    "Science::Biology"           is_child_of "Science::Biology" → False (same level)
    "Math"                       is_child_of "Science"          → False
    """
    if name == prefix:
        return False
    return name == prefix or name.startswith(prefix + SEP)


def subtree_names(names: list[str], root: str) -> list[str]:
    """Return all names from *names* that are in the subtree rooted at *root*,
    including *root* itself if present.

    names  = ["Science", "Science::Biology", "Science::Biology::Genetics", "Math"]
    root   = "Science"
    result = ["Science", "Science::Biology", "Science::Biology::Genetics"]
    """
    return [n for n in names if n == root or is_child_of(n, root)]


# ── Tree construction helper ──────────────────────────────────────────────────

def build_tree(
    items: list[dict],
    path_key: str = "path",
) -> list[dict]:
    """Convert a flat list of items into a tree structure.

    Each input item must have a *path_key* field (e.g. "Science::Biology").
    Returns a list of top-level tree nodes, each with:
        {
            "segment":  "Science",        # display label (last segment)
            "path":     "Science",        # full path to this node
            "data":     <original item or None for virtual parents>,
            "children": [...],            # nested list of same shape
        }

    Virtual parent nodes are created automatically for missing intermediate paths.
    """
    # Build a map from path → item (or None for virtual)
    all_paths: dict[str, dict | None] = {}
    for it in items:
        path = it[path_key]
        all_paths[path] = it
        for ancestor in all_ancestor_paths(path):
            all_paths.setdefault(ancestor, None)

    # Sort so parents always come before children
    sorted_paths = sorted(all_paths.keys(), key=lambda p: (depth(p), p.lower()))

    nodes: dict[str, dict] = {}
    roots: list[dict] = []

    for p in sorted_paths:
        item = all_paths[p]
        node = {
            "segment":  display_name(p),
            "path":     p,
            "data":     item,
            "children": [],
        }
        nodes[p] = node
        par = parent_path(p)
        if par is None:
            roots.append(node)
        else:
            nodes[par]["children"].append(node)

    return roots
