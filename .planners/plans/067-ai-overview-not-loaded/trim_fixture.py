"""Plan 067: trim a capture down to its AI overview component, as a test fixture.

Classifies the capture's components the way ``parse_serp`` does, takes the
first ``ai_overview`` component, drops its ``script``/``style`` elements, and
writes its HTML.

    uv run python .planners/plans/067-ai-overview-not-loaded/trim_fixture.py \
        data/plan-066/timeline-2-html/python-list-comprehension.first.html \
        tests/fixtures/ai_overview_not_loaded.html
"""

import sys
from pathlib import Path

from WebSearcher import Extractor, utils


def main() -> None:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    extractor = Extractor(utils.make_soup(src.read_text()))
    extractor.extract_components()
    for cmpt in extractor.components:
        cmpt.classify_component()
        if cmpt.type == "ai_overview":
            for node in cmpt.elem.css("script, style"):
                node.decompose()
            dst.write_text(cmpt.elem.html + "\n")
            print(f"wrote {dst} ({dst.stat().st_size} bytes)")
            return
    sys.exit(f"no ai_overview component in {src}")


if __name__ == "__main__":
    main()
