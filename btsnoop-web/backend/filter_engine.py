"""
Filter engine for btsnoop packet filtering.

Supports Wireshark-style filter expressions:
  - "hci.type == command"
  - "l2cap.cid == 0x40"
  - "direction == sent"
  - "protocol == L2CAP"
  - "index > 100"
  - Compound: "hci.type == acl && l2cap.cid == 0x40"
  - Compound: "direction == sent || direction == received"
  - Parentheses: "(hci.type == command) || (hci.type == event)"

Grammar (recursive descent):
  expr       -> or_expr
  or_expr    -> and_expr ('||' and_expr)*
  and_expr   -> primary ('&&' primary)*
  primary    -> '(' expr ')' | comparison
  comparison -> field_path operator value
  field_path -> identifier ('.' identifier)*
  operator   -> '==' | '!=' | '>' | '<' | '>=' | '<='
  value      -> string | number | hex_number
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

from parser.models import PacketSummary, Direction


class TokenType(Enum):
    FIELD = "FIELD"
    OP = "OP"
    VALUE = "VALUE"
    AND = "AND"
    OR = "OR"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    EOF = "EOF"


@dataclass
class Token:
    type: TokenType
    value: str
    pos: int


class FilterParseError(Exception):
    """Raised when a filter expression cannot be parsed."""
    pass


class Tokenizer:
    """Lexer for filter expressions."""

    # Pattern for tokens
    TOKEN_PATTERNS = [
        (r"\s+", None),  # skip whitespace
        (r"&&", TokenType.AND),
        (r"\|\|", TokenType.OR),
        (r"\(", TokenType.LPAREN),
        (r"\)", TokenType.RPAREN),
        (r"==|!=|>=|<=|>|<", TokenType.OP),
        (r"0x[0-9a-fA-F]+", TokenType.VALUE),  # hex numbers
        (r"\d+", TokenType.VALUE),  # decimal numbers
        (r'"[^"]*"', TokenType.VALUE),  # quoted strings
        (r"'[^']*'", TokenType.VALUE),  # single-quoted strings
        (r"[a-zA-Z_][a-zA-Z0-9_.]*", TokenType.FIELD),  # field names or bare values
    ]

    def __init__(self, expression: str):
        self._expr = expression
        self._pos = 0
        self._tokens: list[Token] = []
        self._tokenize()

    def _tokenize(self):
        pos = 0
        while pos < len(self._expr):
            matched = False
            for pattern, token_type in self.TOKEN_PATTERNS:
                m = re.match(pattern, self._expr[pos:])
                if m:
                    if token_type is not None:
                        self._tokens.append(
                            Token(type=token_type, value=m.group(), pos=pos)
                        )
                    pos += m.end()
                    matched = True
                    break
            if not matched:
                raise FilterParseError(
                    f"Unexpected character at position {pos}: '{self._expr[pos]}'"
                )
        self._tokens.append(Token(type=TokenType.EOF, value="", pos=pos))

    @property
    def tokens(self) -> list[Token]:
        return self._tokens


class FilterNode:
    """Base class for filter AST nodes."""
    pass


@dataclass
class ComparisonNode(FilterNode):
    """A single comparison: field op value."""
    field_path: str
    operator: str
    value: str


@dataclass
class AndNode(FilterNode):
    """Logical AND of children."""
    children: list[FilterNode]


@dataclass
class OrNode(FilterNode):
    """Logical OR of children."""
    children: list[FilterNode]


class FilterParser:
    """Recursive descent parser for filter expressions."""

    def __init__(self, tokens: list[Token]):
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> Token:
        return self._tokens[self._pos]

    def _advance(self) -> Token:
        t = self._tokens[self._pos]
        self._pos += 1
        return t

    def _expect(self, token_type: TokenType) -> Token:
        t = self._peek()
        if t.type != token_type:
            raise FilterParseError(
                f"Expected {token_type.value} at position {t.pos}, got {t.type.value} '{t.value}'"
            )
        return self._advance()

    def parse(self) -> FilterNode:
        """Parse the complete expression."""
        node = self._parse_or_expr()
        if self._peek().type != TokenType.EOF:
            t = self._peek()
            raise FilterParseError(
                f"Unexpected token at position {t.pos}: '{t.value}'"
            )
        return node

    def _parse_or_expr(self) -> FilterNode:
        """or_expr -> and_expr ('||' and_expr)*"""
        children = [self._parse_and_expr()]
        while self._peek().type == TokenType.OR:
            self._advance()
            children.append(self._parse_and_expr())
        if len(children) == 1:
            return children[0]
        return OrNode(children=children)

    def _parse_and_expr(self) -> FilterNode:
        """and_expr -> primary ('&&' primary)*"""
        children = [self._parse_primary()]
        while self._peek().type == TokenType.AND:
            self._advance()
            children.append(self._parse_primary())
        if len(children) == 1:
            return children[0]
        return AndNode(children=children)

    def _parse_primary(self) -> FilterNode:
        """primary -> '(' expr ')' | comparison"""
        if self._peek().type == TokenType.LPAREN:
            self._advance()
            node = self._parse_or_expr()
            self._expect(TokenType.RPAREN)
            return node
        return self._parse_comparison()

    def _parse_comparison(self) -> FilterNode:
        """comparison -> field_path operator value"""
        field_token = self._expect(TokenType.FIELD)
        op_token = self._expect(TokenType.OP)

        # Value can be a VALUE token or a FIELD token (bare word like "command", "sent")
        val_token = self._peek()
        if val_token.type in (TokenType.VALUE, TokenType.FIELD):
            self._advance()
        else:
            raise FilterParseError(
                f"Expected value at position {val_token.pos}, got {val_token.type.value} '{val_token.value}'"
            )

        return ComparisonNode(
            field_path=field_token.value,
            operator=op_token.value,
            value=val_token.value,
        )


def _parse_value(raw: str) -> Any:
    """
    Parse a value string into a typed Python value.
    - Hex numbers (0x...) -> int
    - Decimal numbers -> int
    - Quoted strings -> str (unquoted)
    - Bare words -> str (lowercased)
    """
    # Remove quotes
    if (raw.startswith('"') and raw.endswith('"')) or (
        raw.startswith("'") and raw.endswith("'")
    ):
        return raw[1:-1]
    # Hex
    if raw.startswith("0x") or raw.startswith("0X"):
        return int(raw, 16)
    # Decimal
    if raw.isdigit():
        return int(raw)
    # Bare word - keep as lowercase string
    return raw.lower()


def _get_field_value(summary: PacketSummary, raw_data: bytes, field_path: str) -> Any:
    """
    Extract a field value from packet summary/data by dotted path.

    Supported fields:
      - direction: "sent" or "received"
      - protocol: top-level protocol name
      - index: packet index
      - length: raw_length
      - hci.type: HCI packet type
      - l2cap.cid: L2CAP channel ID (from layers)
      - l2cap.psm: L2CAP PSM (from layers)
      - Any field in layers: <protocol>.<field_name>
    """
    path = field_path.lower()

    # Top-level fields
    if path == "direction":
        return summary.direction.value
    if path == "protocol":
        return summary.protocol.lower()
    if path == "index":
        return summary.index
    if path in ("length", "raw_length"):
        return summary.raw_length
    if path in ("included_length", "incl_length"):
        return summary.included_length

    # Dotted field path: protocol.field_name
    parts = path.split(".", 1)
    if len(parts) == 2:
        proto, field_name = parts
        # Search layers for matching protocol
        for layer in summary.layers:
            if layer.protocol.lower() == proto:
                for f in layer.fields:
                    if f.name.lower() == field_name:
                        return f.value
                # Also check sublayers
                for sublayer in layer.sublayers:
                    for f in sublayer.fields:
                        if f.name.lower() == field_name:
                            return f.value

    return None


def _compare(field_val: Any, op: str, target_val: Any) -> bool:
    """Compare a field value against a target using the given operator."""
    if field_val is None:
        return False

    # Normalize for string comparison
    if isinstance(field_val, str) and isinstance(target_val, str):
        field_val = field_val.lower()
        target_val = target_val.lower()
    elif isinstance(field_val, str) and isinstance(target_val, int):
        # Try to parse field as int
        try:
            field_val = int(field_val, 0)
        except (ValueError, TypeError):
            return False
    elif isinstance(field_val, int) and isinstance(target_val, str):
        # Try to parse target as int
        try:
            target_val = int(target_val, 0)
        except (ValueError, TypeError):
            target_val = str(target_val)
            field_val = str(field_val)

    try:
        if op == "==":
            return field_val == target_val
        elif op == "!=":
            return field_val != target_val
        elif op == ">":
            return field_val > target_val
        elif op == "<":
            return field_val < target_val
        elif op == ">=":
            return field_val >= target_val
        elif op == "<=":
            return field_val <= target_val
    except TypeError:
        return False

    return False


def _evaluate(node: FilterNode, summary: PacketSummary, raw_data: bytes) -> bool:
    """Evaluate a filter AST node against a packet."""
    if isinstance(node, ComparisonNode):
        field_val = _get_field_value(summary, raw_data, node.field_path)
        target_val = _parse_value(node.value)
        return _compare(field_val, node.operator, target_val)
    elif isinstance(node, AndNode):
        return all(_evaluate(child, summary, raw_data) for child in node.children)
    elif isinstance(node, OrNode):
        return any(_evaluate(child, summary, raw_data) for child in node.children)
    return False


FilterFunc = Callable[[PacketSummary, bytes], bool]


def compile_filter(expression: str) -> FilterFunc:
    """
    Compile a filter expression string into a callable filter function.

    Args:
        expression: Wireshark-style filter expression.

    Returns:
        A function (PacketSummary, bytes) -> bool that returns True
        if the packet matches the filter.

    Raises:
        FilterParseError: If the expression cannot be parsed.
    """
    expression = expression.strip()
    if not expression:
        # Empty filter matches everything
        return lambda summary, raw: True

    tokenizer = Tokenizer(expression)
    parser = FilterParser(tokenizer.tokens)
    ast = parser.parse()

    def filter_func(summary: PacketSummary, raw_data: bytes) -> bool:
        return _evaluate(ast, summary, raw_data)

    return filter_func


def validate_filter(expression: str) -> Optional[str]:
    """
    Validate a filter expression without compiling it.

    Returns None if valid, or an error message string if invalid.
    """
    try:
        compile_filter(expression)
        return None
    except FilterParseError as e:
        return str(e)
