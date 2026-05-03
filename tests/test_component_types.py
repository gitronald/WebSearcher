"""Structural tests for the component type registry.

These tests guard the invariants that bind the registry, the parser dispatch
table, and the classifier — so drift between them surfaces at CI time
instead of at runtime.
"""

import pytest

from WebSearcher.component_parsers import (
    PARSERS,
    footer_parser_dict,
    footer_parser_labels,
    header_parser_dict,
    header_parser_labels,
    main_parser_dict,
    main_parser_labels,
)
from WebSearcher.component_types import (
    COMPONENT_TYPES,
    TYPES_BY_NAME,
    header_text_to_type,
    types_in_section,
)

VALID_SECTIONS = {"header", "main", "footer"}


def test_type_names_are_unique():
    names = [t.name for t in COMPONENT_TYPES]
    duplicates = {n for n in names if names.count(n) > 1}
    assert not duplicates, f"duplicate names in registry: {duplicates}"


def test_types_by_name_is_complete():
    assert set(TYPES_BY_NAME) == {t.name for t in COMPONENT_TYPES}


@pytest.mark.parametrize("ct", COMPONENT_TYPES, ids=lambda t: t.name)
def test_sections_are_valid(ct):
    invalid = set(ct.sections) - VALID_SECTIONS
    assert not invalid, f"{ct.name} has invalid sections: {invalid}"


def test_every_parser_has_registry_entry():
    """Every key in the PARSERS dispatch map must exist in the registry."""
    missing = set(PARSERS) - set(TYPES_BY_NAME)
    assert not missing, f"parsers without registry entries: {missing}"


def test_every_parser_type_has_a_section():
    """A parser registered for an unsectioned type can never be dispatched."""
    unsectioned = [name for name in PARSERS if not TYPES_BY_NAME[name].sections]
    assert not unsectioned, f"parsers with no section: {unsectioned}"


@pytest.mark.parametrize("section", sorted(VALID_SECTIONS))
def test_dispatch_dict_matches_registry(section):
    """Per-section dispatch dicts equal the set of registered types with parsers."""
    expected = {t.name for t in types_in_section(section) if t.name in PARSERS}
    dispatch = {
        "header": header_parser_dict,
        "main": main_parser_dict,
        "footer": footer_parser_dict,
    }[section]
    assert set(dispatch) == expected


@pytest.mark.parametrize("section", sorted(VALID_SECTIONS))
def test_label_dict_matches_registry(section):
    """Per-section label dicts equal the registry's type labels."""
    expected = {t.name: t.label for t in types_in_section(section) if t.name in PARSERS}
    labels = {
        "header": header_parser_labels,
        "main": main_parser_labels,
        "footer": footer_parser_labels,
    }[section]
    assert labels == expected


@pytest.mark.parametrize("level", [2, 3])
def test_header_texts_have_no_collisions(level):
    """No two types should share a header text at the same level."""
    text_to_types: dict[str, list[str]] = {}
    for t in COMPONENT_TYPES:
        for text in t.header_texts.get(level, ()):
            text_to_types.setdefault(text, []).append(t.name)
    collisions = {text: types for text, types in text_to_types.items() if len(types) > 1}
    assert not collisions, f"H{level} text collisions: {collisions}"


@pytest.mark.parametrize("level", [2, 3])
def test_header_text_to_type_returns_known_types(level):
    """Every value returned by header_text_to_type must be a registered type."""
    for text, name in header_text_to_type(level).items():
        assert name in TYPES_BY_NAME, f"H{level} text {text!r} maps to unknown type {name!r}"
