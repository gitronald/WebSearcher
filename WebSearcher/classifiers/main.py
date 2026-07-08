from typing import Any

from selectolax.lexbor import LexborNode as Node

from .. import logger
from .._slx import _iter_text_fragments, class_tokens, get_text
from ..parsers.component_types import header_text_to_type

log = logger.Logger().start(__name__)

_VIDEO_CLASSES = {"VibNM", "mLmaBd", "RzdJxc", "sHEJob"}
_LOCAL_CLASSES = {"Qq3Lb", "VkpGBb"}


# Tag names and ids the classifier chain actually gates on. The chain consults
# ``signals.names``/``signals.ids`` for only this fixed handful of tokens, so
# ``_ComponentSignals`` keeps just these rather than every element's tag/id --
# one frozenset membership test per element instead of growing a set ~2.5M times
# per corpus pass. NOTE: any new precondition that tests ``s.names``/``s.ids``
# for a token MUST register it here, or the precondition will silently never
# fire (the token never enters the set). The 87-snapshot suite pins the existing
# tokens. ``classes`` is consulted broadly (incl. intersection with
# ``_VIDEO_CLASSES``/``_LOCAL_CLASSES``) so it must stay complete.
_NAME_SIGNALS: frozenset[str] = frozenset(
    {
        "g-scrolling-carousel",
        "g-tray-header",
        "block-component",
        "h2",
        "promo-throttler",
        "product-viewer-group",
        "g-more-link",
    }
)
_ID_SIGNALS: frozenset[str] = frozenset(
    {
        "imagebox_bigimages",
        "iur",
        "knowledge-finance-wholepage__entity-summary",
        "eer-masthead",
    }
)


class _ComponentSignals:
    """One-pass summary of a component's gating class names, ids, and tag names.

    The classifier chain consults this to skip a classifier whose necessary
    structural signal is absent, replacing many full-subtree ``find()`` misses
    with set lookups. Preconditions are necessary conditions only, so a skip can
    never change a classification (pinned by the snapshot suite). ``names`` and
    ``ids`` are filtered to ``_NAME_SIGNALS``/``_ID_SIGNALS`` -- the only tokens
    the chain ever tests -- while ``classes`` is kept in full.
    """

    __slots__ = ("classes", "ids", "names")

    def __init__(self, cmpt: Node) -> None:
        classes: set[str] = set()
        ids: set[str] = set()
        names: set[str] = set()
        # ``el.attrs`` is a non-allocating view over the element's attribute
        # table (vs ``el.attributes`` which materializes a dict per call);
        # ``el.id`` is a direct property, 3x cheaper than ``attrs.get('id')``.
        # The leading truthiness guard narrows ``str | None`` -> ``str`` for the
        # type checker and short-circuits the (common) no-id element before the
        # membership test; only interest-set tokens reach ``set.add``.
        for el in cmpt.css("*"):
            name = el.tag
            if name and name in _NAME_SIGNALS:
                names.add(name)
            cls = el.attrs.get("class")
            if cls:
                classes.update(cls.split())
            el_id = el.id
            if el_id and el_id in _ID_SIGNALS:
                ids.add(el_id)
        self.classes = classes
        self.ids = ids
        self.names = names


_HEADER_CSS_BY_LEVEL: dict[int, tuple[str, ...]] = {
    level: (
        f'h{level}[role="heading"]',
        f"h{level}.O3JH7, h{level}.q8U8x, h{level}.mfMhoc",
        f'[aria-level="{level}"][role="heading"]',
    )
    for level in (2, 3)
}


class ClassifyMainHeader:
    """Classify a main-section component by its h2/h3 header text."""

    @staticmethod
    def classify(cmpt, levels: tuple[int, ...] = (2, 3)) -> str:
        node: Node = cmpt
        # A whole-page entity panel (``kp-wholepage-osrp``) can embed sub-carousels
        # ("People also search for") and feedback affordances whose level-2 headings
        # would mis-claim the entire panel (e.g. as ``searches_related``). Defer to the
        # structural classifiers downstream (``available_on``, ``knowledge_panel``),
        # which type these panels correctly.
        if node.css_first("div.kp-wholepage-osrp") is not None:
            return "unknown"
        for level in levels:
            header = ClassifyMainHeader._classify_header(node, level)
            if header != "unknown":
                return header
        return "unknown"

    @staticmethod
    def _classify_header(node: Node, level: int) -> str:
        """Check text in common headers for dict matches."""
        markers = header_text_to_type(level)
        for css in _HEADER_CSS_BY_LEVEL[level]:
            for header in node.css(css):
                text = (get_text(header) or "").strip()
                # local_results' "locations" is the lone endswith marker.
                if text.endswith("locations"):
                    return "local_results"
                for marker, label in markers.items():
                    if marker == "locations":
                        continue
                    if text.startswith(marker):
                        return label
        return "unknown"


class ClassifyMain:
    """Classify a component from the main section based on its selectolax Node."""

    @staticmethod
    def classify(cmpt) -> str:
        node: Node = cmpt
        signals = _ComponentSignals(node)

        # Preconditions test ``s.classes`` freely, but any ``s.names``/``s.ids``
        # token must also live in ``_NAME_SIGNALS``/``_ID_SIGNALS`` (see above) or
        # the precondition silently never fires.
        component_classifiers = [
            (ClassifyMain.locations, None),
            (ClassifyMain.top_stories, lambda s: "g-scrolling-carousel" in s.names),
            (ClassifyMain.discussions_and_forums, lambda s: "IFnjPb" in s.classes),
            # Structural-first: ITWcLb rows type a buying_guide before the
            # English-only header-text path, so a localized/reworded heading
            # ("Buying guide: ...") still classifies.
            (ClassifyMain.buying_guide, lambda s: "ITWcLb" in s.classes),
            # Structural-first: a left-bar/inline dictionary panel (``dob-modules``,
            # no ``kp-blk``/``ULSxyf`` wrapper) is a ``knowledge`` panel whose
            # "Dictionary" label sits in a non-heading span; type it structurally
            # so ``parse_knowledge_panel``'s ``_subtype_dictionary`` recovers it,
            # before the header-text path (which would miss it) reaches unknown.
            (ClassifyMain.dictionary_panel, None),
            # NOTE: ``most_read_articles`` has no unique structural signal -- it is
            # classified purely by its English header "Most-read articles" via
            # ``ClassifyMainHeader`` below, so a localized heading is unclassifiable.
            # Unlike buying_guide/products it cannot be made structural-first.
            (ClassifyMainHeader.classify, None),
            (ClassifyMain.news_quotes, lambda s: "g-tray-header" in s.names),
            (ClassifyMain.img_cards, lambda s: "block-component" in s.names),
            (ClassifyMain.images, lambda s: "imagebox_bigimages" in s.ids or "iur" in s.ids),
            (ClassifyMain.ai_overview, lambda s: "Fzsovc" in s.classes or "h2" in s.names),
            # available_on's full-component ``get_text`` fallback (the
            # ``/Available on`` substring path) fires 0x across the corpus; the
            # real cases are caught by its cheap ``span.mgAbYb`` heading. Gating on
            # that class stops the expensive fallback from running on the ~10
            # non-available_on components/SERP that otherwise reach this classifier
            # (plan 036 Lever 3). Tradeoff: a non-mgAbYb component carrying
            # ``/Available on`` text would no longer be typed available_on --
            # unobserved on the corpus, accepted as evidence-backed dead code.
            (ClassifyMain.available_on, lambda s: "mgAbYb" in s.classes),
            (ClassifyMain.knowledge_panel, None),
            (ClassifyMain.knowledge_block, lambda s: "block-component" in s.names),
            (ClassifyMain.banner, lambda s: "uzjuFc" in s.classes),
            (
                ClassifyMain.finance_panel,
                lambda s: "knowledge-finance-wholepage__entity-summary" in s.ids,
            ),
            (ClassifyMain.map_result, lambda s: "lu_map_section" in s.classes),
            (ClassifyMain.general_questions, lambda s: "ifM9O" in s.classes),
            (ClassifyMain.short_videos, lambda s: "IFnjPb" in s.classes),
            (ClassifyMain.videos, lambda s: bool(s.classes & _VIDEO_CLASSES)),
            (ClassifyMain.knowledge_subcard, lambda s: "JNkvid" in s.classes),
            (ClassifyMain.twitter, None),
            (ClassifyMain.flights, None),
            (ClassifyMain.promo, lambda s: "promo-throttler" in s.names),
            (
                ClassifyMain.products,
                lambda s: (
                    "product-viewer-group" in s.names
                    or "g-more-link" in s.names
                    or "gON1yc" in s.classes
                ),
            ),
            (
                ClassifyMain.election,
                lambda s: (
                    "eer-rc-b" in s.classes or "eer-rc-i" in s.classes or "eer-masthead" in s.ids
                ),
            ),
            (ClassifyMain.general, None),
            (ClassifyMain.people_also_ask, None),
            (ClassifyMain.knowledge_box, None),
            (ClassifyMain.local_results, lambda s: bool(s.classes & _LOCAL_CLASSES)),
            # End-of-chain rules: each keys on a signal that also lives inside
            # components other classifiers own (knowledge panels embed lab/
            # attribute modules and AI-overview controllers; kp hotel sections
            # carry travel links), so they may only claim components nothing
            # above typed.
            (ClassifyMain.knowledge_submodule, None),
            (ClassifyMain.hotel_carousel, None),
            (ClassifyMain.images_strip, None),
            (ClassifyMain.ai_overview_banner, lambda s: "hdzaWe" in s.classes),
        ]

        for classifier, precondition in component_classifiers:
            if precondition is not None and not precondition(signals):
                continue
            cmpt_type = classifier(node)
            if cmpt_type != "unknown":
                return cmpt_type
        return "unknown"

    @staticmethod
    def discussions_and_forums(cmpt) -> str:
        node: Node = cmpt
        # bs4 ``find("div", {"class": "IFnjPb", "role": "heading"})`` = AND of
        # both conditions; CSS compound div.IFnjPb[role="heading"] = same.
        heading = node.css_first('div.IFnjPb[role="heading"]')
        if heading is not None and (get_text(heading, strip=True) or "").startswith(
            "Discussions and forums"
        ):
            return "discussions_and_forums"
        return "unknown"

    @staticmethod
    def images_strip(cmpt) -> str:
        """Type the left-bar/inline "Images" thumbnail strip as ``images``.

        The older layout (root ``div.TzHB6b``) labels a small image/video result
        strip with an offscreen a11y heading ``h3.bNg8Rb`` reading exactly
        "Images", and carries none of the imagebox signals (``imagebox_bigimages``
        / ``iur`` / carousel) that ``ClassifyMain.images`` keys on, so it reaches
        unknown. This is end-of-chain, so it only claims a component nothing above
        typed -- the real imagebox is caught earlier and never reaches here.
        """
        node: Node = cmpt
        for heading in node.css('h3.bNg8Rb, [role="heading"]'):
            if (get_text(heading, strip=True) or "") == "Images":
                return "images"
        return "unknown"

    @staticmethod
    def dictionary_panel(cmpt) -> str:
        """Type the Oxford Languages word-definition panel as ``knowledge``.

        The dictionary "definition on board" box carries a ``div.dob-modules``
        container. When it renders inside a ``kp-blk``/``ULSxyf`` wrapper the
        knowledge classifiers already catch it, but the left-bar/inline layout
        (root ``div.TzHB6b``) has no such wrapper and its "Dictionary" label sits
        in a non-heading span, so it reaches unknown. Anchor on the stable
        ``dob-modules`` class -- which also survives the "Report a problem"
        feedback-modal wrapper that prepends chrome to the panel text -- and route
        it to ``parse_knowledge_panel`` (``_subtype_dictionary`` recovers the
        headword + definitions and sets ``sub_type="dictionary"``).
        """
        node: Node = cmpt
        return "knowledge" if node.css_first("div.dob-modules") is not None else "unknown"

    @staticmethod
    def available_on(cmpt) -> str:
        node: Node = cmpt
        for heading in node.css("span.mgAbYb"):
            if (get_text(heading, strip=True) or "") == "Available on":
                return "available_on"
        text = get_text(node) or ""
        return "available_on" if "/Available on" in text else "unknown"

    @staticmethod
    def banner(cmpt) -> str:
        node: Node = cmpt
        if "ULSxyf" not in class_tokens(node):
            return "unknown"
        return "banner" if node.css_first("div.uzjuFc") is not None else "unknown"

    @staticmethod
    def buying_guide(cmpt) -> str:
        """Classify a faceted "Buying guide" accordion by its row class.

        ``div.ITWcLb`` rows are buying_guide's unique, stable structural signal,
        so this types the component even when its h2 ("Buying guide: ...") is
        localized or reworded -- cases the English-only "Buying guide" header
        match in ``ClassifyMainHeader`` would miss.
        """
        node: Node = cmpt
        return "buying_guide" if node.css_first("div.ITWcLb") is not None else "unknown"

    @staticmethod
    def finance_panel(cmpt) -> str:
        node: Node = cmpt
        return (
            "knowledge"
            if node.css_first('div[id="knowledge-finance-wholepage__entity-summary"]') is not None
            else "unknown"
        )

    @staticmethod
    def flights(cmpt) -> str:
        node: Node = cmpt
        # The flight-status widget renders its heading as a bare <h2> with no
        # role="heading", so check both.
        heading = node.css_first('[role="heading"]') or node.css_first("h2")
        if heading is not None and (get_text(heading, strip=True) or "").startswith("Flight"):
            return "flights"
        return "unknown"

    @staticmethod
    def general(cmpt) -> str:
        """Classify general components."""
        node: Node = cmpt
        node_id = node.mem_id
        # bs4 distinguished "class" present vs absent via ``"class" in cmpt.attrs``
        # -- preserve that distinction explicitly.
        if "class" in node.attributes:
            cls = class_tokens(node)
            conditions = {
                "format-01": cls == ["g"],
                "format-02": ("g" in cls) and ("Ww4FFb" in cls),
                "format-03": any(s in {"hlcw0c", "MjjYud", "PmEWq"} for s in cls),
                # bs4 ``find("div", {"class": ["g","Ww4FFb"]})`` = OR of tokens.
                "format-04": any(n.mem_id != node_id for n in node.css("div.g, div.Ww4FFb")),
            }
        else:
            conditions = {
                "format-05": all(
                    any(n.mem_id != node_id for n in node.css(f"div.{c}")) for c in ("g", "d4rhi")
                ),
            }
        return "general" if any(conditions.values()) else "unknown"

    @staticmethod
    def election(cmpt) -> str:
        """Classify the live election-results tracker (``eer`` = election results).

        Its ``h2`` ("Election results for the … are updated live …") carries no
        ``role="heading"``, so ``ClassifyMainHeader`` misses it; anchor on the
        stable ``eer-`` masthead/row classes instead. The dates and resources
        panels classify by heading text via ``ClassifyMainHeader``.
        """
        node: Node = cmpt
        if node.css_first('div[id="eer-masthead"]') is not None:
            return "election_results"
        if node.css_first("div.eer-rc-b, div.eer-rc-i") is not None:
            return "election_results"
        return "unknown"

    @staticmethod
    def general_questions(cmpt) -> str:
        node: Node = cmpt
        hybrid = node.css_first("div.ifM9O")
        g_accordion = node.css_first("g-accordion")
        return "general_questions" if hybrid is not None and g_accordion is not None else "unknown"

    @staticmethod
    def img_cards(cmpt) -> str:
        node: Node = cmpt
        if "class" not in node.attributes:
            return "unknown"
        cls = class_tokens(node)
        if not any(s in {"hlcw0c", "MjjYud"} for s in cls):
            return "unknown"
        return "img_cards" if node.css_first("block-component") is not None else "unknown"

    @staticmethod
    def images(cmpt) -> str:
        node: Node = cmpt
        for css in ('div[id="imagebox_bigimages"]', 'div[id="iur"]'):
            if node.css_first(css) is not None:
                return "images"
        return "unknown"

    @staticmethod
    def ai_overview(cmpt) -> str:
        """Classify AI Overview components.

        Skip the sibling "Related Links" expansion that also contains a
        ``Fzsovc`` div -- that surface is a different component (extended
        sources and follow-up sections) and is not parsed here.
        """
        node: Node = cmpt
        h2 = node.css_first("h2")
        h2_text = (get_text(h2, strip=True) or "") if h2 is not None else ""
        if h2_text == "Related Links":
            return "unknown"
        if node.css_first("div.Fzsovc") is not None or h2_text == "AI Overview":
            return "ai_overview"
        return "unknown"

    @staticmethod
    def ai_overview_banner(cmpt) -> str:
        """Classify the standalone AI-overview loading/unavailable banner.

        SERPs serialized mid-generation ("Thinking") or after Google declined
        to synthesize an overview carry the AI overview's ``EYwa3d`` controller
        but none of the ``Fzsovc``/``h2 AI Overview`` markers ``ai_overview``
        gates on. The parser routes these to ``sub_type="unavailable"``.
        """
        node: Node = cmpt
        if node.css_first('div[jscontroller="EYwa3d"]') is not None:
            return "ai_overview"
        return "unknown"

    # Heading texts for knowledge-panel submodules with no structural signal
    # (no data-attrid / custom element). Checked only by the end-of-chain
    # ``knowledge_submodule`` rule, so they cannot steal from earlier
    # classifiers the way a ``header_texts`` registration (position 5) could
    # -- e.g. a local_results restaurant pack that also lists menu highlights.
    _KNOWLEDGE_SUBMODULE_HEADINGS = (
        "Menu highlights",
        "Things to do",
        "Showtimes at",
        "Rooms at",
        # Standalone entity submodules splatted into the main column.
        "Interactive diagrams",
        "Featured events",
        "How to solve your problem",
        "Your math problem",
        "Explore more",
        "Top sights in",
        "Beach destinations",
        "Popular destinations",
        "Surfing destinations",
        "Camping destinations",
    )

    @staticmethod
    def knowledge_submodule(cmpt) -> str:
        """Classify knowledge-panel submodules splatted into the main column.

        Standalone entity-attribute modules (Movies, Played by, Calories, ...)
        carry ``lab/title/*`` / ``lab/content/*`` attrids; core-answer
        breadcrumb modules ("<entity> > <attribute>") carry
        ``CoreAnswerModuleHeader``; sports modules carry ``TLOsrp*`` attrids
        (match lists, standings) or an ``sp-table`` squad table.
        """
        node: Node = cmpt
        if (
            node.css_first(
                '[data-attrid^="lab/title/"], [data-attrid^="lab/content/"], '
                '[data-attrid="CoreAnswerModuleHeader"], [data-attrid^="TLOsrp"]'
            )
            is not None
            or node.css_first("sp-table") is not None
        ):
            return "knowledge"
        # The submodule heading renders at aria-level 2 (most attribute modules,
        # "Rooms at <hotel>") or 3 (inline "Menu highlights"), so check both.
        for heading in node.css(
            '[aria-level="2"][role="heading"], [aria-level="3"][role="heading"]'
        ):
            text = get_text(heading, " ", strip=True) or ""
            if text.startswith(ClassifyMain._KNOWLEDGE_SUBMODULE_HEADINGS):
                return "knowledge"
        return "unknown"

    @staticmethod
    def hotel_carousel(cmpt) -> str:
        """Classify hotel carousels whose heading evades the ``locations`` rule.

        "Similar to <hotel>" / "Popular hotels in <place>" / "More <brand>"
        carousels vary their heading freely, but every card links to
        ``search.google.com/local/places/hotel/`` or pairs a ``/travel/search``
        link with a hotel-name div -- the same structures ``parse_hotels``
        extracts from.
        """
        node: Node = cmpt
        if node.css_first('a[href*="/local/places/hotel/"]') is not None:
            return "locations"
        if (
            node.css_first('a[href*="/travel/search"]') is not None
            and node.css_first("div.sxdlOc, div.BTPx6e") is not None
        ):
            return "locations"
        return "unknown"

    @staticmethod
    def knowledge_block(cmpt) -> str:
        node: Node = cmpt
        if class_tokens(node) != ["ULSxyf"]:
            return "unknown"
        return "knowledge" if node.css_first("block-component") is not None else "unknown"

    @staticmethod
    def knowledge_box(cmpt) -> str:
        """Classify knowledge component types."""
        node: Node = cmpt
        attrs = node.attributes
        condition: dict[str, Any] = {}
        condition["flights"] = (
            attrs.get("jscontroller") == "Z2bSc"
            or node.css_first('div[jscontroller="Z2bSc"]') is not None
        )
        condition["maps"] = attrs.get("data-hveid") == "CAMQAA"
        condition["locations"] = node.css_first("div.zd2Jbb") is not None
        condition["events"] = node.css_first("g-card.URhAHe") is not None
        condition["jobs"] = node.css_first("g-card.cvoI5e") is not None
        # bs4 ``next(iter(cmpt.stripped_strings), None)`` -- first non-blank text
        # fragment in the subtree; ``_iter_text_fragments`` replicates stripped_strings.
        first_text: str | None = None
        for raw in _iter_text_fragments(node):
            stripped = raw.strip()
            if stripped:
                first_text = stripped
                break
        if first_text is not None:
            condition["covid_alert"] = first_text == "COVID-19 alert"
        for condition_type, conditions in condition.items():
            if conditions:
                return condition_type
        return "unknown"

    @staticmethod
    def knowledge_panel(cmpt) -> str:
        node: Node = cmpt
        for css in (
            "h1.VW3apb",
            "div.knowledge-panel, div.knavi, div.kp-blk, div.kp-wholepage-osrp",
            'div[aria-label="Featured results"][role="complementary"]',
            'div[jscontroller="qTdDb"]',
            "div.obcontainer",
            # Knowledge-vertical onebox (e.g. language pronunciation practice
            # widget) surfaced as its own sub-column block on kp-wholepage tabs.
            '[id$="__onebox_content"]',
        ):
            if node.css_first(css) is not None:
                return "knowledge"
        if node.attrs.get("jscontroller") == "qTdDb":
            return "knowledge"
        return "unknown"

    @staticmethod
    def local_results(cmpt) -> str:
        node: Node = cmpt
        for css in ("div.Qq3Lb", "div.VkpGBb"):
            if node.css_first(css) is not None:
                return "local_results"
        return "unknown"

    @staticmethod
    def map_result(cmpt) -> str:
        node: Node = cmpt
        return "map_results" if node.css_first("div.lu_map_section") is not None else "unknown"

    @staticmethod
    def people_also_ask(cmpt) -> str:
        """Secondary check for people also ask (header text is primary)."""
        node: Node = cmpt
        # bs4 ``check_dict_value(cmpt.attrs, "class", ["g","kno-kp","mnr-c","g-blk"])``
        # is EXACT list equality on the class attribute.
        return (
            "people_also_ask"
            if class_tokens(node) == ["g", "kno-kp", "mnr-c", "g-blk"]
            else "unknown"
        )

    @staticmethod
    def products(cmpt) -> str:
        """Classify organic shopping packs that otherwise fall into ``general``."""
        node: Node = cmpt
        if node.css_first('[data-attrid="apg-product-result"]') is not None:
            return "products"
        if (
            node.css_first("product-viewer-group") is not None
            and node.css_first("g-inner-card") is not None
        ):
            return "products"
        # Brands carousel: div.gON1yc cards are the unique structural signal, so
        # the carousel still types as products when its "Explore brands" heading
        # is localized or reworded (header-text match below is English-only).
        if node.css_first("div.gON1yc") is not None:
            return "products"
        heading = node.css_first('[role="heading"]')
        if heading is not None and (get_text(heading, strip=True) or "") == "Explore brands":
            return "products"
        return "unknown"

    @staticmethod
    def promo(cmpt) -> str:
        node: Node = cmpt
        return "promo" if node.css_first("promo-throttler") is not None else "unknown"

    @staticmethod
    def short_videos(cmpt) -> str:
        node: Node = cmpt
        heading = node.css_first('span[role="heading"].IFnjPb')
        if heading is not None and (get_text(heading, strip=True) or "") == "Short videos":
            return "short_videos"
        return "unknown"

    @staticmethod
    def videos(cmpt) -> str:
        """Classify video carousel components."""
        node: Node = cmpt
        return (
            "videos"
            if node.css_first("div.VibNM, div.mLmaBd, div.RzdJxc, div.sHEJob") is not None
            else "unknown"
        )

    @staticmethod
    def knowledge_subcard(cmpt) -> str:
        """Catch knowledge-panel extension subcards by structural pattern."""
        node: Node = cmpt
        if node.css_first("div.JNkvid") is None:
            return "unknown"
        if node.css_first('[role="heading"][aria-level="2"]') is None:
            return "unknown"
        return "knowledge"

    @staticmethod
    def locations(cmpt) -> str:
        """Classify locations components (hotels, etc.)."""
        node: Node = cmpt
        heading = node.css_first('[role="heading"]')
        if heading is not None:
            # Space-join: headings split across spans ("More" + "Hotels")
            # otherwise concatenate to "MoreHotels" and evade the prefix match.
            text = get_text(heading, " ", strip=True) or ""
            if text.startswith("Hotels") or text.startswith("More Hotel"):
                return "locations"
        return "unknown"

    @staticmethod
    def top_stories(cmpt) -> str:
        node: Node = cmpt
        if node.css_first("g-scrolling-carousel") is None:
            return "unknown"
        if node.css_first('div[id="tvcap"]') is None:
            return "unknown"
        return "top_stories"

    @staticmethod
    def news_quotes(cmpt) -> str:
        node: Node = cmpt
        header_div = node.css_first('g-tray-header[role="heading"]')
        text = get_text(header_div, strip=True) if header_div is not None else None
        return "news_quotes" if text == "News quotes" else "unknown"

    @staticmethod
    def twitter(cmpt) -> str:
        node: Node = cmpt
        cmpt_type = "twitter" if node.css_first("div.eejeod") is not None else "unknown"
        return ClassifyMain.twitter_type(node, cmpt_type)

    @staticmethod
    def twitter_type(cmpt, cmpt_type: str = "unknown") -> str:
        """Distinguish twitter types ('twitter_cards', 'twitter_result')."""
        node: Node = cmpt
        if cmpt_type == "twitter" or (get_text(node, strip=True) or "") == "Twitter Results":
            return (
                "twitter_cards"
                if node.css_first("g-scrolling-carousel") is not None
                else "twitter_result"
            )
        return cmpt_type
