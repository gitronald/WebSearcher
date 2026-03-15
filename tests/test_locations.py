"""Tests for protobuf encoding and UULE generation"""

from WebSearcher.locations import (
    convert_canonical_name_to_uule,
    decode_protobuf_string,
    encode_protobuf_string,
)


def test_encode_decode_roundtrip_integers():
    fields = {1: 2, 2: 32}
    encoded = encode_protobuf_string(fields)
    decoded = decode_protobuf_string(encoded)
    assert decoded == fields


def test_encode_decode_roundtrip_string():
    fields = {1: 2, 4: "Boston,Massachusetts,United States"}
    encoded = encode_protobuf_string(fields)
    decoded = decode_protobuf_string(encoded)
    assert decoded == fields


def test_encode_decode_roundtrip_mixed():
    fields = {1: 2, 2: 32, 4: "New York,New York,United States"}
    encoded = encode_protobuf_string(fields)
    decoded = decode_protobuf_string(encoded)
    assert decoded == fields


def test_encode_decode_unicode():
    fields = {1: 0, 4: "Zurich,Zurich,Switzerland"}
    encoded = encode_protobuf_string(fields)
    decoded = decode_protobuf_string(encoded)
    assert decoded == fields


def test_uule_starts_with_prefix():
    result = convert_canonical_name_to_uule("Boston,Massachusetts,United States")
    assert result.startswith("w+")


def test_uule_deterministic():
    name = "New York,New York,United States"
    assert convert_canonical_name_to_uule(name) == convert_canonical_name_to_uule(name)


def test_uule_different_locations_differ():
    a = convert_canonical_name_to_uule("Boston,Massachusetts,United States")
    b = convert_canonical_name_to_uule("New York,New York,United States")
    assert a != b


def test_uule_encodes_expected_fields():
    """UULE should encode fields {1: 2, 2: 32, 4: canon_name}"""
    name = "Austin,Texas,United States"
    uule = convert_canonical_name_to_uule(name)
    encoded = uule[2:]  # strip "w+" prefix
    decoded = decode_protobuf_string(encoded)
    assert decoded[1] == 2
    assert decoded[2] == 32
    assert decoded[4] == name
