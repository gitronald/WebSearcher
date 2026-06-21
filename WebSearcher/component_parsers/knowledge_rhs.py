"""Parse the Right-Hand-Side Knowledge Panel.

The wide-format entity panel that appears in the right-hand column. This
includes the main panel (title, description, image grid, submenu links) and
zero or more follow-on sections beneath it.

Rows are emitted as ``type="side_bar"`` with ``sub_type="panel"`` for the main
entity panel, ``sub_type="fact"`` for each ``kc:/`` entity-fact row (label +
value, e.g. "Director: David Lean"), and ``sub_type="links"`` for each link
box / follow-on section.
"""

from typing import Any

from selectolax.lexbor import LexborNode as Node

from .._slx import get_text, next_sibling, next_siblings, previous_sibling
from ._common import parse_alink

# Chrome links that show up inside RHS boxes but are not content.
_RHS_BOX_CHROME = {"Claim this knowledge panel", "Send feedback", "Feedback", "See more"}

# kc:/ rows that are edit affordances, not entity facts.
_FACT_ROW_CHROME = {"kc:/local:edit info", "kc:/local:pending edits"}


def _is_chrome_box(title: str) -> bool:
    """Box headings that are affordances/ads, not content sections."""
    return "feedback" in title.lower() or title == "Sponsored"


def parse_knowledge_rhs(elem, sub_rank: int = 0) -> list:
    node: Node = elem
    parsed_list = parse_knowledge_rhs_main(node)
    main_title = parsed_list[0]["title"] if parsed_list else None
    description = node.css_first("h2.Uo8X3b")
    if description is not None and description.parent is not None:
        tag_subs = [
            s for s in next_siblings(description.parent) if s.tag and not s.tag.startswith("-")
        ]
        for i, s in enumerate(tag_subs):
            sub = parse_knowledge_rhs_sub(s, i)
            # Skip hollow follow-on sections (no heading and no links).
            if sub["title"] or sub["details"]:
                parsed_list.append(sub)
    else:
        # Complementary kp-wholepage RHS panel: entity facts ride on ``kc:/``
        # data-attrid rows, and its sections (Listen / About / Profiles /
        # People also search for) are boxes anchored by aria-level=2 headings
        # rather than Uo8X3b follow-on siblings. Emit the fact rows first
        # (they carry the label+value semantics), then one row per box with
        # the box's remaining links in details.
        facts, fact_ids, used_heading_ids = _parse_rhs_facts(node, start_rank=len(parsed_list))
        parsed_list.extend(facts)
        parsed_list.extend(
            _parse_rhs_boxes(
                node,
                start_rank=len(parsed_list),
                fact_ids=fact_ids,
                used_heading_ids=used_heading_ids,
                main_title=main_title,
            )
        )
    return parsed_list


def _under_any(node: Node, ids: set, stop_id: int) -> bool:
    """True if any ancestor of ``node`` (up to ``stop_id``, exclusive) is in ``ids``."""
    p = node.parent
    while p is not None and p.mem_id != stop_id:
        if p.mem_id in ids:
            return True
        p = p.parent
    return False


def _collect_links(node: Node, exclude_ids: set | None = None, stop_id: int = -1) -> list:
    """Non-navigational-chrome links under ``node`` (deduped). Links nested
    inside an ``exclude_ids`` node (an already-emitted fact row) are skipped so
    box rows don't re-list links the fact rows carry."""
    items: list = []
    seen: set = set()
    for a in node.css("a[href]"):
        href = a.attributes.get("href")
        text = get_text(a, " ", strip=True) or ""
        # Drop non-navigational affordances: missing or "#" hrefs (general
        # feedback, expanders, "Write a review", "Ask a question") carry no
        # content.
        if not href or href == "#" or text in _RHS_BOX_CHROME or (text, href) in seen:
            continue
        if exclude_ids and _under_any(a, exclude_ids, stop_id):
            continue
        seen.add((text, href))
        items.append({"url": href, "text": text})
    return items


def _rhs_box_links(heading: Node, exclude_ids: set | None = None, stop_id: int = -1) -> list:
    """Links of the box a heading labels: climb to the first ancestor holding
    links, then collect them (deduped, chrome dropped). A box left with no
    real links is then handled as a text-only section by the caller."""
    box = heading.parent
    for _ in range(5):
        if box is None:
            return []
        if box.css_first("a[href]") is not None:
            break
        box = box.parent
    else:
        return []
    return _collect_links(box, exclude_ids=exclude_ids, stop_id=stop_id)


def _rhs_qa_topics(node: Node) -> list:
    """The panel's "Things to know" Q&A topic labels (``lab/title/*`` attrids).

    Ordered as they appear so the main panel row can list them; the box pass
    uses the same labels (as a set) to avoid re-emitting them as noisy rows."""
    return [
        attr.split("/")[-1]
        for d in node.css("[data-attrid]")
        if (attr := str(d.attributes.get("data-attrid") or "")).startswith("lab/title/")
    ]


def _rhs_expander_topics(node: Node) -> list:
    """Topic labels of "Things to know" Q&A boxes flagged only by the ``…``
    expander span (``iwY1Mb``), for panels without ``lab/title/*`` attrids.

    ``_is_qa_topic_box`` skips these headings in the box pass, so without this
    fallback their titles would be dropped entirely (plan 041)."""
    topics = []
    for heading in node.css('[role="heading"][aria-level="2"]'):
        if heading.css_first("span.iwY1Mb") is None:
            continue
        label_span = heading.css_first("span")
        label = get_text(label_span, " ", strip=True) if label_span is not None else None
        if label:
            topics.append(label)
    return topics


def _is_qa_topic_box(heading: Node, qa_topics: set) -> bool:
    """True if a heading is a "Things to know" Q&A topic, not a real link-box.

    These are already surfaced cleanly on the main panel row, so the box pass
    must skip them. Semantic check: the heading's label span matches a
    ``lab/title/*`` topic. Structural fallback (for panels without
    ``lab/title/*``): the heading carries the ``…`` expander span (``iwY1Mb``)
    that only Q&A topic headings use."""
    label_span = heading.css_first("span")
    if label_span is not None and get_text(label_span, " ", strip=True) in qa_topics:
        return True
    return heading.css_first("span.iwY1Mb") is not None


def _fact_box_heading(fact: Node, root: Node) -> Node | None:
    """The aria-level=2 heading of the box that holds this fact row alone.

    When a box wraps exactly one ``kc:/`` row, its heading is the fact's
    display label (e.g. "Watch movie" for ``media_actions``, "Popular Times"
    for ``busyness``). Returns ``None`` when the fact shares its box with
    other facts (e.g. the film "About" box)."""
    best = None
    box = fact.parent
    while box is not None and box.mem_id != root.mem_id:
        others = [
            n
            for n in box.css("[data-attrid^='kc:/']")
            if n.mem_id != fact.mem_id and not _under_any(n, {fact.mem_id}, box.mem_id)
        ]
        if others:
            break
        heading = box.css_first('[role="heading"][aria-level="2"]')
        if heading is not None:
            title = get_text(heading, " ", strip=True)
            # "?" titles are survey prompts ("How much do you trust..."), not
            # section labels.
            if title and not _is_chrome_box(title) and not title.endswith("?"):
                best = heading
        box = box.parent
    return best


def _parse_rhs_facts(node: Node, start_rank: int = 1) -> tuple:
    """One ``side_bar`` row per ``kc:/`` entity-fact row.

    Labeled facts ("Born: April 8, 1901") put the label in ``title`` and the
    value in ``text``; label-less rows (reviews, social profiles, watch
    actions) fall back to the enclosing box heading or a humanized attrid tail.
    The attrid rides in ``details`` as provenance, alongside the row's links
    when it has any. Returns ``(rows, fact_ids, used_heading_ids)`` so the box
    pass can skip content these rows already carry."""
    rows: list = []
    fact_ids: set = set()
    used_heading_ids: set = set()
    for fact in node.css("[data-attrid^='kc:/']"):
        attrid = str(fact.attributes.get("data-attrid") or "")
        if attrid in _FACT_ROW_CHROME:
            continue
        # Outermost match wins: skip kc:/ rows nested in an emitted one.
        if _under_any(fact, fact_ids, node.mem_id):
            continue

        label_el = fact.css_first("span.w8qArf")
        label = (get_text(label_el, " ", strip=True) or "").rstrip(" :") or None
        if label is not None:
            value_el = fact.css_first("span.LrzXr")
            if value_el is not None:
                text = get_text(value_el, " ", strip=True) or None
            else:
                # No value span (e.g. the hours table): everything after the
                # "Label :" prefix in the row's text.
                full = get_text(fact, " ", strip=True) or ""
                text = full.split(":", 1)[-1].strip() or None
        else:
            text = get_text(fact, " ", strip=True) or None

        links = _collect_links(fact)
        title = label
        if title is None:
            box_heading = _fact_box_heading(fact, node)
            if box_heading is not None:
                title = get_text(box_heading, " ", strip=True)
                used_heading_ids.add(box_heading.mem_id)
                # The consumed box may hold links outside the kc:/ row itself
                # (e.g. the expanded watch-provider list next to
                # ``media_actions``) -- fold them in so they aren't lost with
                # the skipped box.
                seen = {(i["text"], i["url"]) for i in links}
                links += [
                    i
                    for i in _rhs_box_links(
                        box_heading, exclude_ids={fact.mem_id}, stop_id=node.mem_id
                    )
                    if (i["text"], i["url"]) not in seen
                ]
            else:
                # Humanized attrid tail: "kc:/film/film:reviews" -> "Reviews".
                tail = attrid.split(":")[-1].replace("_", " ").strip()
                title = (tail[:1].upper() + tail[1:]) or None

        details: dict[str, Any]
        if links:
            details = {"type": "hyperlinks", "attrid": attrid, "items": links}
        else:
            details = {"type": "item", "attrid": attrid}

        fact_ids.add(fact.mem_id)
        rows.append(
            {
                "type": "side_bar",
                "sub_type": "fact",
                "sub_rank": start_rank + len(rows),
                "title": title,
                "text": text,
                "details": details,
            }
        )
    return rows, fact_ids, used_heading_ids


def _box_sibling_text(heading: Node) -> str | None:
    """Text of the first content sibling after a link-less box heading (e.g.
    the "PayPal Apple Pay" values under a "Payment options" heading)."""
    if heading.parent is None:
        return None
    for s in next_siblings(heading.parent):
        if s.tag and not s.tag.startswith("-"):
            text = get_text(s, " ", strip=True)
            if text:
                return text
    return None


def _parse_rhs_boxes(
    node: Node,
    start_rank: int = 1,
    fact_ids: set | None = None,
    used_heading_ids: set | None = None,
    main_title: str | None = None,
) -> list:
    """One ``side_bar`` row per aria-level=2 box (title = heading, links in
    details). Boxes whose content the fact pass already emitted are skipped;
    a link-less content box keeps its title and sibling text instead of being
    dropped (plan 041)."""
    fact_ids = fact_ids or set()
    used_heading_ids = used_heading_ids or set()
    qa_topics = set(_rhs_qa_topics(node))
    rows: list = []
    for heading in node.css('[role="heading"][aria-level="2"]'):
        title = get_text(heading, " ", strip=True)
        if not title or _is_chrome_box(title) or _is_qa_topic_box(heading, qa_topics):
            continue
        if heading.mem_id in used_heading_ids or _under_any(heading, fact_ids, node.mem_id):
            continue
        items = _rhs_box_links(heading, exclude_ids=fact_ids, stop_id=node.mem_id)
        if items:
            rows.append(
                {
                    "type": "side_bar",
                    "sub_type": "links",
                    "sub_rank": start_rank + len(rows),
                    "title": title,
                    "details": {"type": "hyperlinks", "items": items},
                }
            )
            continue
        # Link-less box: keep the section title (and any sibling text) unless
        # it duplicates the main panel title, is a survey prompt, or its
        # content was already emitted by the fact pass (climb like
        # ``_rhs_box_links`` and look for an emitted kc:/ row).
        if title == main_title or title.endswith("?"):
            continue
        box = heading.parent
        for _ in range(5):
            if box is None:
                break
            if box.css_first("a[href]") is not None or box.css_first("[data-attrid^='kc:/']"):
                break
            box = box.parent
        if box is not None and any(n.mem_id in fact_ids for n in box.css("[data-attrid^='kc:/']")):
            continue
        rows.append(
            {
                "type": "side_bar",
                "sub_type": "links",
                "sub_rank": start_rank + len(rows),
                "title": title,
                "text": _box_sibling_text(heading),
                "details": None,
            }
        )
    return rows


def parse_knowledge_rhs_main(elem, sub_rank: int = 0) -> list:
    node: Node = elem
    parsed: dict[str, Any] = {
        "type": "side_bar",
        "sub_type": "panel",
        "sub_rank": sub_rank,
        "title": None,
        "text": None,
        "url": None,
        "details": {},
    }

    # images
    h3 = node.css_first("h3")
    if h3 is not None and (get_text(h3) or "") == "Images":
        sibling = next_sibling(h3)
        if sibling is not None and sibling.tag and not sibling.tag.startswith("-"):
            img_urls = [
                img.attributes["href"] for img in sibling.css("a") if "href" in img.attributes
            ]
            if img_urls:
                parsed["details"]["img_urls"] = img_urls

    # title, subtitle (data-attrid carries the title on any tag, not just h2)
    title = node.css_first('h2[data-attrid="title"]') or node.css_first('[data-attrid="title"]')
    if title is not None:
        parsed["title"] = get_text(title, " ", strip=True) or None
    subtitle = node.css_first('div[data-attrid="subtitle"]')
    if subtitle is not None and (subtitle_text := get_text(subtitle)):
        parsed["details"]["subtitle"] = subtitle_text

    # description (heading-anchored)
    description = node.css_first("h2.Uo8X3b")
    if description is not None and description.parent is not None:
        span = description.parent.css_first("span")
        if span is not None:
            parsed["text"] = get_text(span)
        a = description.parent.css_first("a")
        if a is not None and "href" in a.attributes:
            parsed["url"] = a.attributes["href"]

    # description (kno-rdesc)
    description = node.css_first("div.kno-rdesc")
    if description is not None:
        span = description.css_first("span")
        parsed["text"] = get_text(span) if span is not None else parsed["text"]
        a = description.css_first("a")
        if a is not None and "href" in a.attributes:
            parsed["url"] = a.attributes["href"]

    # submenu
    if description is not None and description.parent is not None:
        alinks = list(description.parent.css("a"))
        prev = previous_sibling(description.parent)
        if prev is not None and prev.tag and not prev.tag.startswith("-"):
            alinks += list(prev.css("a"))
        if len(alinks) > 1:  # 1st match has main description
            urls = []
            for a in alinks[1:]:
                if "href" in a.attributes:
                    urls.append(parse_alink(a))
            if urls:
                parsed["details"]["urls"] = urls

    # description fallback (entity panels whose description sits on a
    # data-attrid rather than Uo8X3b / kno-rdesc)
    if not parsed["text"]:
        desc = node.css_first("[data-attrid=description]")
        if desc is not None:
            parsed["text"] = get_text(desc, " ", strip=True) or None

    # "Things to know" RHS panels carry topic sections on lab/title/* attrs
    # rather than a single description -- surface the topics instead of an
    # empty placeholder. Panels that flag the topics only with the expander
    # span (no lab/title/*) get the same treatment so the box pass's skip of
    # those headings doesn't lose the titles.
    topics = _rhs_qa_topics(node) or _rhs_expander_topics(node)
    if topics:
        if not parsed["title"]:
            parsed["title"] = "Things to know"
        parsed["details"]["items"] = topics

    if parsed["details"]:
        parsed["details"]["type"] = "panel"
    else:
        parsed["details"] = None

    # Drop genuinely hollow placeholder rows (nothing extracted at all).
    if (
        not parsed["title"]
        and not parsed["text"]
        and not parsed["url"]
        and parsed["details"] is None
    ):
        return []

    return [parsed]


def parse_knowledge_rhs_sub(sub: Node, sub_rank: int = 0) -> dict:
    parsed: dict = {
        "type": "side_bar",
        "sub_type": "links",
        "sub_rank": sub_rank + 1,
        "title": None,
        "details": None,
    }

    heading = sub.css_first('div[role="heading"]')
    if heading is not None:
        parsed["title"] = get_text(heading, " ") or None

    alinks = list(sub.css("a"))
    if alinks:
        items = []
        for a in alinks:
            if "href" in a.attributes:
                items.append(parse_alink(a))
        parsed["details"] = {"type": "hyperlinks", "items": items} if items else None

    return parsed
