"""
Tests for filter engine (filter_engine.py).

Tests:
  - Simple equality: "hci.type == command"
  - Hex values: "l2cap.cid == 0x0040"
  - Compound: "direction == sent && protocol == HCI"
  - Invalid syntax returns error
  - Parentheses grouping
"""

from __future__ import annotations

import struct

import pytest

from filter_engine import (
    compile_filter,
    validate_filter,
    FilterParseError,
    Tokenizer,
    FilterParser,
    TokenType,
    ComparisonNode,
    AndNode,
    OrNode,
)
from parser.models import PacketSummary, DecodedLayer, DecodedField, Direction


def make_packet_summary(
    index: int = 0,
    direction: Direction = Direction.SENT,
    protocol: str = "HCI_CMD",
    summary: str = "Reset",
    layers: list = None,
    raw_length: int = 10,
) -> PacketSummary:
    """Helper to create a PacketSummary for testing."""
    if layers is None:
        layers = [
            DecodedLayer(
                protocol="HCI_CMD",
                summary="Reset (0x0C03) plen=0",
                fields=[
                    DecodedField("opcode", "0x0C03"),
                    DecodedField("name", "Reset"),
                ],
            )
        ]
    return PacketSummary(
        index=index,
        timestamp_us=0,
        timestamp_str="00:00:00.000",
        direction=direction,
        protocol=protocol,
        summary=summary,
        layers=layers,
        raw_length=raw_length,
        included_length=raw_length,
    )


def make_acl_packet_summary(cid: int = 0x0040, psm_name: str = "") -> PacketSummary:
    """Helper to create an ACL + L2CAP PacketSummary."""
    l2cap_fields = [
        DecodedField("length", 10),
        DecodedField("cid", f"0x{cid:04X}"),
    ]
    if psm_name:
        l2cap_fields.append(DecodedField("psm_name", psm_name))

    layers = [
        DecodedLayer(
            protocol="ACL",
            summary=f"handle=0x0040 len=14",
            fields=[DecodedField("handle", "0x0040")],
        ),
        DecodedLayer(
            protocol="L2CAP",
            summary=f"ATT len=10",
            fields=l2cap_fields,
        ),
        DecodedLayer(
            protocol="ATT",
            summary="EXCHANGE_MTU_REQ mtu=517",
            fields=[DecodedField("opcode", "0x02")],
        ),
    ]
    return PacketSummary(
        index=1,
        timestamp_us=1000,
        timestamp_str="00:00:00.001",
        direction=Direction.SENT,
        protocol="ATT",
        summary="EXCHANGE_MTU_REQ mtu=517",
        layers=layers,
        raw_length=20,
        included_length=20,
    )


class TestSimpleEquality:
    """Tests for simple equality filters."""

    def test_direction_sent(self):
        """Filter 'direction == sent' matches sent packets."""
        f = compile_filter("direction == sent")
        pkt = make_packet_summary(direction=Direction.SENT)
        assert f(pkt, b"") is True

    def test_direction_received(self):
        """Filter 'direction == sent' rejects received packets."""
        f = compile_filter("direction == sent")
        pkt = make_packet_summary(direction=Direction.RECEIVED)
        assert f(pkt, b"") is False

    def test_direction_received_match(self):
        """Filter 'direction == received' matches received packets."""
        f = compile_filter("direction == received")
        pkt = make_packet_summary(direction=Direction.RECEIVED)
        assert f(pkt, b"") is True

    def test_protocol_match(self):
        """Filter 'protocol == HCI_CMD' matches HCI command packets."""
        f = compile_filter("protocol == HCI_CMD")
        pkt = make_packet_summary(protocol="HCI_CMD")
        assert f(pkt, b"") is True

    def test_protocol_case_insensitive(self):
        """Protocol comparison is case-insensitive."""
        f = compile_filter("protocol == hci_cmd")
        pkt = make_packet_summary(protocol="HCI_CMD")
        assert f(pkt, b"") is True

    def test_index_equality(self):
        """Filter 'index == 5' matches packet at index 5."""
        f = compile_filter("index == 5")
        pkt = make_packet_summary(index=5)
        assert f(pkt, b"") is True

    def test_index_inequality(self):
        """Filter 'index == 5' rejects packet at index 3."""
        f = compile_filter("index == 5")
        pkt = make_packet_summary(index=3)
        assert f(pkt, b"") is False


class TestHexValues:
    """Tests for hex value comparisons."""

    def test_l2cap_cid_hex(self):
        """Filter 'l2cap.cid == 0x0040' matches L2CAP CID."""
        f = compile_filter("l2cap.cid == 0x0040")
        pkt = make_acl_packet_summary(cid=0x0040)
        assert f(pkt, b"") is True

    def test_l2cap_cid_hex_no_match(self):
        """Filter 'l2cap.cid == 0x0040' rejects different CID."""
        f = compile_filter("l2cap.cid == 0x0040")
        pkt = make_acl_packet_summary(cid=0x0004)
        assert f(pkt, b"") is False

    def test_l2cap_cid_att(self):
        """Filter for ATT CID."""
        f = compile_filter("l2cap.cid == 0x0004")
        pkt = make_acl_packet_summary(cid=0x0004)
        assert f(pkt, b"") is True


class TestCompoundFilters:
    """Tests for compound (AND/OR) filters."""

    def test_and_both_true(self):
        """AND filter matches when both conditions are true."""
        f = compile_filter("direction == sent && protocol == HCI_CMD")
        pkt = make_packet_summary(direction=Direction.SENT, protocol="HCI_CMD")
        assert f(pkt, b"") is True

    def test_and_one_false(self):
        """AND filter rejects when one condition is false."""
        f = compile_filter("direction == sent && protocol == ATT")
        pkt = make_packet_summary(direction=Direction.SENT, protocol="HCI_CMD")
        assert f(pkt, b"") is False

    def test_or_first_true(self):
        """OR filter matches when first condition is true."""
        f = compile_filter("direction == sent || direction == received")
        pkt = make_packet_summary(direction=Direction.SENT)
        assert f(pkt, b"") is True

    def test_or_second_true(self):
        """OR filter matches when second condition is true."""
        f = compile_filter("protocol == ATT || protocol == HCI_CMD")
        pkt = make_packet_summary(protocol="HCI_CMD")
        assert f(pkt, b"") is True

    def test_or_neither_true(self):
        """OR filter rejects when neither condition is true."""
        f = compile_filter("protocol == ATT || protocol == SMP")
        pkt = make_packet_summary(protocol="HCI_CMD")
        assert f(pkt, b"") is False

    def test_complex_and_or(self):
        """Complex filter with multiple AND and OR."""
        f = compile_filter("direction == sent && protocol == HCI_CMD || protocol == ATT")
        # This should be (direction==sent && protocol==HCI_CMD) || (protocol==ATT)
        pkt_cmd = make_packet_summary(direction=Direction.SENT, protocol="HCI_CMD")
        pkt_att = make_packet_summary(direction=Direction.RECEIVED, protocol="ATT")
        pkt_other = make_packet_summary(direction=Direction.RECEIVED, protocol="SMP")
        assert f(pkt_cmd, b"") is True
        assert f(pkt_att, b"") is True
        assert f(pkt_other, b"") is False


class TestParentheses:
    """Tests for parenthesized filter expressions."""

    def test_simple_parens(self):
        """Parentheses group expressions."""
        f = compile_filter("(direction == sent)")
        pkt = make_packet_summary(direction=Direction.SENT)
        assert f(pkt, b"") is True

    def test_parens_change_precedence(self):
        """Parentheses change AND/OR precedence."""
        # Without parens: "a && b || c" = "(a && b) || c"
        # With parens: "a && (b || c)" = a must be true AND (b OR c must be true)
        f = compile_filter("direction == sent && (protocol == ATT || protocol == HCI_CMD)")
        pkt_sent_cmd = make_packet_summary(direction=Direction.SENT, protocol="HCI_CMD")
        pkt_recv_cmd = make_packet_summary(direction=Direction.RECEIVED, protocol="HCI_CMD")
        assert f(pkt_sent_cmd, b"") is True
        assert f(pkt_recv_cmd, b"") is False

    def test_nested_parens(self):
        """Nested parentheses work."""
        f = compile_filter("((direction == sent))")
        pkt = make_packet_summary(direction=Direction.SENT)
        assert f(pkt, b"") is True


class TestInvalidSyntax:
    """Tests for invalid filter expressions."""

    def test_missing_operator(self):
        """Invalid: missing operator."""
        error = validate_filter("direction sent")
        assert error is not None

    def test_missing_value(self):
        """Invalid: missing value after operator."""
        error = validate_filter("direction ==")
        assert error is not None

    def test_unmatched_paren(self):
        """Invalid: unmatched opening parenthesis."""
        error = validate_filter("(direction == sent")
        assert error is not None

    def test_unexpected_char(self):
        """Invalid: unexpected character."""
        error = validate_filter("direction == sent #")
        assert error is not None

    def test_double_operator(self):
        """Invalid: double operator."""
        error = validate_filter("direction == == sent")
        assert error is not None

    def test_empty_is_valid(self):
        """Empty filter is valid (matches everything)."""
        error = validate_filter("")
        assert error is None

    def test_empty_matches_all(self):
        """Empty filter matches all packets."""
        f = compile_filter("")
        pkt = make_packet_summary()
        assert f(pkt, b"") is True

    def test_whitespace_only_valid(self):
        """Whitespace-only filter is valid."""
        error = validate_filter("   ")
        assert error is None

    def test_compile_filter_raises_on_invalid(self):
        """compile_filter raises FilterParseError on invalid syntax."""
        with pytest.raises(FilterParseError):
            compile_filter("!! invalid")


class TestOperators:
    """Tests for comparison operators."""

    def test_not_equal(self):
        """Filter with != operator."""
        f = compile_filter("protocol != ATT")
        pkt = make_packet_summary(protocol="HCI_CMD")
        assert f(pkt, b"") is True

    def test_greater_than(self):
        """Filter with > operator."""
        f = compile_filter("index > 5")
        assert f(make_packet_summary(index=10), b"") is True
        assert f(make_packet_summary(index=3), b"") is False

    def test_less_than(self):
        """Filter with < operator."""
        f = compile_filter("index < 10")
        assert f(make_packet_summary(index=5), b"") is True
        assert f(make_packet_summary(index=15), b"") is False

    def test_greater_equal(self):
        """Filter with >= operator."""
        f = compile_filter("index >= 5")
        assert f(make_packet_summary(index=5), b"") is True
        assert f(make_packet_summary(index=4), b"") is False

    def test_less_equal(self):
        """Filter with <= operator."""
        f = compile_filter("index <= 5")
        assert f(make_packet_summary(index=5), b"") is True
        assert f(make_packet_summary(index=6), b"") is False


class TestTokenizer:
    """Tests for the filter tokenizer."""

    def test_simple_expression(self):
        """Tokenize a simple comparison."""
        t = Tokenizer("direction == sent")
        tokens = t.tokens
        # Should have FIELD, OP, FIELD (bare word value), EOF
        assert tokens[0].type == TokenType.FIELD
        assert tokens[0].value == "direction"
        assert tokens[1].type == TokenType.OP
        assert tokens[1].value == "=="
        assert tokens[2].type == TokenType.FIELD  # bare word
        assert tokens[2].value == "sent"
        assert tokens[3].type == TokenType.EOF

    def test_hex_value(self):
        """Tokenize hex value."""
        t = Tokenizer("l2cap.cid == 0x0040")
        tokens = t.tokens
        assert tokens[2].type == TokenType.VALUE
        assert tokens[2].value == "0x0040"

    def test_and_or_tokens(self):
        """Tokenize AND and OR operators."""
        t = Tokenizer("a == b && c == d || e == f")
        types = [tok.type for tok in t.tokens]
        assert TokenType.AND in types
        assert TokenType.OR in types

    def test_parentheses_tokens(self):
        """Tokenize parentheses."""
        t = Tokenizer("(a == b)")
        assert t.tokens[0].type == TokenType.LPAREN
        assert t.tokens[4].type == TokenType.RPAREN

    def test_quoted_string(self):
        """Tokenize quoted string value."""
        t = Tokenizer('name == "hello world"')
        assert t.tokens[2].type == TokenType.VALUE
        assert t.tokens[2].value == '"hello world"'


class TestDottedFieldPath:
    """Tests for dotted field path resolution."""

    def test_layer_field_access(self):
        """Access a field within a specific protocol layer."""
        f = compile_filter("hci_cmd.name == Reset")
        pkt = make_packet_summary()
        assert f(pkt, b"") is True

    def test_layer_field_no_match(self):
        """Dotted path returns no match when field doesn't exist."""
        f = compile_filter("att.opcode == 0x02")
        pkt = make_packet_summary()  # Has HCI_CMD layer, not ATT
        assert f(pkt, b"") is False

    def test_length_field(self):
        """Access raw_length top-level field."""
        f = compile_filter("length == 10")
        pkt = make_packet_summary(raw_length=10)
        assert f(pkt, b"") is True
