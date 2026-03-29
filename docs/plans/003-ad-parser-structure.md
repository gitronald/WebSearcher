---
status: done
branch: dev
created: 2026-02-22T12:56:12-08:00
completed: 2026-02-05T13:38:09-08:00
pr: https://github.com/gitronald/WebSearcher/pull/94
---

# Ad Parser Structure

Each ad parser should follow this nested function pattern:

```python
def parse_ad_<type>(cmpt: bs4.element.Tag) -> list:

    def _parse_ad_<type>(cmpt: bs4.element.Tag) -> list:
        subs = cmpt.find_all(...)
        return [_parse_ad_<type>_sub(sub, sub_rank) for sub_rank, sub in enumerate(subs)]

    def _parse_ad_<type>_sub(sub: bs4.element.Tag, sub_rank: int) -> dict:
        return BaseResult(
            type='ad',
            sub_type='<type>',
            sub_rank=sub_rank,
            title=_parse_ad_<type>_sub_title(sub),
            url=_parse_ad_<type>_sub_url(sub),
            cite=_parse_ad_<type>_sub_cite(sub),
            text=_parse_ad_<type>_sub_text(sub),
            details=_parse_ad_<type>_sub_details(sub)
        )

    def _parse_ad_<type>_sub_title(sub: bs4.element.Tag) -> str:
        ...

    def _parse_ad_<type>_sub_url(sub: bs4.element.Tag) -> str:
        ...

    def _parse_ad_<type>_sub_cite(sub: bs4.element.Tag) -> str:
        ...

    def _parse_ad_<type>_sub_text(sub: bs4.element.Tag) -> str:
        ...

    def _parse_ad_<type>_sub_details(sub: bs4.element.Tag) -> list:
        ...

    return _parse_ad_<type>(cmpt)
```

See `parse_ad_secondary` in `WebSearcher/component_parsers/ads.py` for the canonical implementation.
