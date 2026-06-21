from selectolax.lexbor import LexborNode as Node

from .component import Component


def _last_descendant(elem: Node) -> Node:
    """The last element of ``elem.css('*')`` (self + descendants, pre-order)
    without materializing the whole subtree.

    The last node a pre-order walk visits is reached by repeatedly descending to
    the last *element* child (selectolax pseudo-nodes -- text/comment -- carry a
    ``-``-prefixed or empty tag and are excluded from ``css('*')``, so they are
    skipped here too). Returns ``elem`` itself when it has no element children,
    matching ``elem.css('*')[-1]`` for a leaf.
    """
    node = elem
    while True:
        last: Node | None = None
        for ch in node.iter(include_text=False):
            if ch.tag and not ch.tag.startswith("-"):
                last = ch
        if last is None:
            return node
        node = last


class ComponentList:
    def __init__(self):
        self.components = []
        self.cmpt_rank_counter = 0
        self.serp_rank_counter = 0

    def __iter__(self):
        yield from self.components

    def add_component(self, elem, section="unknown", type="unknown", cmpt_rank=None):
        """Add a component to the list of components"""
        cmpt_rank = self.cmpt_rank_counter if cmpt_rank is None else cmpt_rank
        component = Component(elem, section, type, cmpt_rank)

        self.components.append(component)
        self.cmpt_rank_counter += 1

    def reorder_by_dom_position(self, positions):
        """Reorder components by DOM position within each section.

        ``positions`` maps ``mem_id -> pre-order index`` for every element in
        the document. End ranges for main components are derived on demand from
        the last descendant (``_last_descendant``, the last node a pre-order walk
        of the subtree visits -- its index is the end of the subtree). When a
        component's range contains another component's start, the ancestor's
        effective position shifts to the first direct child positioned after the
        nested subtree.
        """
        section_order = {"header": 0, "main": 1, "footer": 2, "rhs": 3}
        main_components = [c for c in self.components if c.section == "main"]

        def _range(elem):
            start = positions.get(elem.mem_id)
            if start is None:
                return None
            # The last descendant's index is the end of the subtree. Find it via
            # a right-spine descent rather than materializing the whole subtree
            # (``elem.css('*')``) only to read its last entry.
            end = positions.get(_last_descendant(elem).mem_id, start)
            return start, end

        ranges = {id(c): _range(c.elem) for c in main_components}

        def _effective_pos(cmpt):
            rng = ranges[id(cmpt)]
            if rng is None:
                return float("inf")
            start, end = rng
            for other in main_components:
                if other is cmpt:
                    continue
                other_rng = ranges[id(other)]
                if other_rng is None:
                    continue
                o_start, o_end = other_rng
                if start <= o_start <= end:
                    # cmpt.elem is an ancestor of other.elem -- find the first
                    # direct child positioned after the nested subtree.
                    best = float("inf")
                    for ch in cmpt.elem.iter(include_text=False):
                        ch_start = positions.get(ch.mem_id)
                        if ch_start is not None and o_end < ch_start < best:
                            best = ch_start
                    if best != float("inf"):
                        return best
            return start

        def sort_key(cmpt):
            section_idx = section_order.get(cmpt.section, 1)
            if cmpt.section == "main":
                return (section_idx, _effective_pos(cmpt))
            return (section_idx, cmpt.cmpt_rank)

        self.components.sort(key=sort_key)
        for i, cmpt in enumerate(self.components):
            cmpt.cmpt_rank = i
        self.cmpt_rank_counter = len(self.components)

    def export_component_results(self):
        """Export the results of all components"""
        results = []
        for cmpt in self.components:
            for result in cmpt.export_results():
                result["serp_rank"] = self.serp_rank_counter
                results.append(result)
                self.serp_rank_counter += 1
        return results

    def to_records(self):
        return [cmpt.to_dict() for cmpt in self.components]
