from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .parsers import parse_serp

__all__ = ["parse_serp"]


def __getattr__(name: str):
    # Lazy-load parse_serp so importing a leaf submodule (e.g. component_types
    # from classifiers, or component_list from extractors) does not eagerly pull
    # the full parse pipeline (parsers -> extractors -> component -> classifiers)
    # and create a circular import.
    if name == "parse_serp":
        from .parsers import parse_serp

        globals()["parse_serp"] = parse_serp  # cache: __getattr__ runs once
        return parse_serp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(__all__)
