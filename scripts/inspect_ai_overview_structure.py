"""Inspect AI Overview component tree structure.

For each saved overview HTML file, print a structural skeleton: heading tree,
the role-heading boundaries, and how the Fzsovc blocks relate to siblings —
to find a reliable section delimiter for the parser.
"""

import argparse
import pathlib

import bs4


def walk(node, depth=0, max_depth=6):
    if depth > max_depth or not getattr(node, "name", None):
        return
    role = node.attrs.get("role") if hasattr(node, "attrs") else None
    aria_level = node.attrs.get("aria-level") if hasattr(node, "attrs") else None
    cls = node.attrs.get("class", []) if hasattr(node, "attrs") else []
    cls_str = " ".join(cls[:3]) + ("..." if len(cls) > 3 else "")
    snippet = ""
    if role == "heading":
        snippet = " | text=" + repr(node.get_text(" ", strip=True))[:70]
    elif node.name == "a" and node.get("href"):
        snippet = f" | href={node['href'][:50]} text={node.get_text(strip=True)[:30]!r}"
    if role or node.name in {"h1", "h2", "h3", "h4", "a", "ul", "ol", "li", "g-link"}:
        print(
            f"{'  ' * depth}<{node.name}"
            f"{' role=' + role if role else ''}"
            f"{' aria-level=' + aria_level if aria_level else ''}"
            f"{' class=' + cls_str if cls_str else ''}>"
            f"{snippet}"
        )
    for child in node.children:
        walk(child, depth + 1, max_depth)


def show_top_level_children(node):
    """Print direct children to understand structural layout."""
    for i, child in enumerate(node.children):
        if not getattr(child, "name", None):
            continue
        cls = child.attrs.get("class", [])
        text = child.get_text(" ", strip=True)[:80]
        n_headings = len(child.find_all(attrs={"role": "heading"}))
        n_anchors = len([a for a in child.find_all("a", href=True) if a["href"] != "#"])
        print(
            f"  child[{i}] <{child.name}> class={cls[:3]} | h={n_headings} a={n_anchors} | text={text!r}"
        )


def find_sections(node):
    """Find candidate section delimiters."""
    # Look for repeating sibling structures that contain a heading + content
    sections = []
    headings = node.find_all(attrs={"role": "heading", "aria-level": "3"})
    for h in headings:
        sections.append(
            {
                "heading": h.get_text(" ", strip=True),
                "level": h.attrs.get("aria-level"),
                "h_classes": h.attrs.get("class", []),
                "parent_classes": (h.parent.attrs.get("class", []) if h.parent else []),
            }
        )
    return sections


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--mode", choices=["walk", "children", "sections"], default="sections")
    parser.add_argument("--depth", type=int, default=5)
    args = parser.parse_args()

    for p in args.paths:
        path = pathlib.Path(p)
        print(f"\n========== {path.name} ==========")
        soup = bs4.BeautifulSoup(path.read_text(), "lxml")
        root = soup.find()
        if args.mode == "walk":
            walk(root, max_depth=args.depth)
        elif args.mode == "children":
            show_top_level_children(root)
        elif args.mode == "sections":
            secs = find_sections(root)
            print(f"  {len(secs)} aria-level=3 headings:")
            for s in secs:
                print(f"    {s}")


if __name__ == "__main__":
    main()
