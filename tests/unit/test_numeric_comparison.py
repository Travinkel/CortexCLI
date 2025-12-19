"""
Unit tests for numeric comparison functions in Cortex CLI.

Tests the hardened numeric normalization and comparison that handles:
- Binary values (0b1010, 10101010)
- Hexadecimal values (0xFF, FFh)
- IP addresses (192.168.1.0)
- CIDR notation (/24)
- Decimal values with tolerance

Run: pytest tests/unit/test_numeric_comparison.py -v
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.cli.cortex import _compare_numeric_answers, _normalize_numeric


class TestNormalizeNumeric:
    """Test _normalize_numeric function."""

    # ========================================
    # Binary Value Tests
    # ========================================

    def test_binary_with_0b_prefix(self):
        """Binary with 0b prefix should return int."""
        result = _normalize_numeric("0b1010")
        assert result == 10
        assert isinstance(result, int)

    def test_binary_without_prefix_short(self):
        """Short binary string may not be detected as binary."""
        # "101" is only 3 chars, too short to auto-detect as binary
        result = _normalize_numeric("101")
        assert result == 101  # Treated as decimal

    def test_binary_without_prefix_long(self):
        """Long binary string (4+ chars) should be detected."""
        result = _normalize_numeric("1010")
        assert result == 10  # 0b1010 = 10

    def test_binary_8bit(self):
        """8-bit binary string."""
        result = _normalize_numeric("11111111")
        assert result == 255

    def test_binary_subnet_mask(self):
        """Binary subnet mask (32 bits)."""
        result = _normalize_numeric("11111111111111111111111100000000")
        assert result == 0xFFFFFF00

    def test_binary_with_underscores(self):
        """Binary with visual separators should work."""
        result = _normalize_numeric("1111_1111")
        assert result == 255

    # ========================================
    # Hexadecimal Value Tests
    # ========================================

    def test_hex_with_0x_prefix(self):
        """Hex with 0x prefix should return int."""
        result = _normalize_numeric("0xFF")
        assert result == 255
        assert isinstance(result, int)

    def test_hex_with_h_suffix(self):
        """Hex with h suffix should return int."""
        result = _normalize_numeric("FFh")
        assert result == 255

    def test_hex_lowercase(self):
        """Lowercase hex should work."""
        result = _normalize_numeric("0xff")
        assert result == 255

    def test_hex_large_value(self):
        """Large hex values should preserve precision."""
        result = _normalize_numeric("0xFFFFFFFF")
        assert result == 4294967295
        assert isinstance(result, int)

    # ========================================
    # IP Address Tests
    # ========================================

    def test_ip_address_basic(self):
        """IP address should return normalized string."""
        result = _normalize_numeric("192.168.1.0")
        assert result == "192.168.1.0"
        assert isinstance(result, str)

    def test_ip_address_with_leading_zeros(self):
        """IP with leading zeros should normalize."""
        result = _normalize_numeric("192.168.001.010")
        assert result == "192.168.1.10"

    def test_ip_address_all_zeros(self):
        """All-zeros IP address."""
        result = _normalize_numeric("0.0.0.0")
        assert result == "0.0.0.0"

    def test_ip_address_broadcast(self):
        """Broadcast address."""
        result = _normalize_numeric("255.255.255.255")
        assert result == "255.255.255.255"

    def test_invalid_ip_octet(self):
        """IP with invalid octet should not be treated as IP."""
        # 256 is invalid in IP
        result = _normalize_numeric("192.168.256.1")
        # Should not match IP pattern, returns as-is
        assert result == "192.168.256.1"

    # ========================================
    # CIDR Notation Tests
    # ========================================

    def test_cidr_notation(self):
        """CIDR notation should return string."""
        result = _normalize_numeric("/24")
        assert result == "/24"
        assert isinstance(result, str)

    def test_cidr_notation_full(self):
        """Full CIDR notation."""
        result = _normalize_numeric("/32")
        assert result == "/32"

    # ========================================
    # Decimal Value Tests
    # ========================================

    def test_integer(self):
        """Plain integer should return int."""
        result = _normalize_numeric("42")
        assert result == 42
        assert isinstance(result, int)

    def test_float(self):
        """Float value should return float."""
        result = _normalize_numeric("3.14")
        assert result == 3.14
        assert isinstance(result, float)

    def test_negative_integer(self):
        """Negative integer."""
        result = _normalize_numeric("-10")
        assert result == -10

    def test_scientific_notation(self):
        """Scientific notation should return float."""
        result = _normalize_numeric("1e6")
        assert result == 1000000.0

    # ========================================
    # Edge Cases
    # ========================================

    def test_whitespace_handling(self):
        """Whitespace should be stripped."""
        result = _normalize_numeric("  42  ")
        assert result == 42

    def test_non_numeric_returns_string(self):
        """Non-numeric input should return original string."""
        result = _normalize_numeric("hello")
        assert result == "hello"
        assert isinstance(result, str)


class TestCompareNumericAnswers:
    """Test _compare_numeric_answers function."""

    # ========================================
    # Integer Comparison Tests
    # ========================================

    def test_integer_exact_match(self):
        """Integers should match exactly."""
        assert _compare_numeric_answers(255, 255) is True

    def test_integer_mismatch(self):
        """Different integers should not match."""
        assert _compare_numeric_answers(255, 256) is False

    def test_binary_comparison(self):
        """Binary values (as int) should match."""
        # Both normalized from binary
        user = _normalize_numeric("0b11111111")
        correct = _normalize_numeric("255")
        assert _compare_numeric_answers(user, correct) is True

    def test_hex_comparison(self):
        """Hex values should match decimal equivalent."""
        user = _normalize_numeric("0xFF")
        correct = _normalize_numeric("255")
        assert _compare_numeric_answers(user, correct) is True

    # ========================================
    # String Comparison Tests
    # ========================================

    def test_ip_address_match(self):
        """IP addresses should match as strings."""
        assert _compare_numeric_answers("192.168.1.0", "192.168.1.0") is True

    def test_ip_address_mismatch(self):
        """Different IPs should not match."""
        assert _compare_numeric_answers("192.168.1.0", "192.168.1.1") is False

    def test_cidr_match(self):
        """CIDR notation should match."""
        assert _compare_numeric_answers("/24", "/24") is True

    def test_string_case_insensitive(self):
        """String comparison should be case-insensitive."""
        assert _compare_numeric_answers("HELLO", "hello") is True

    # ========================================
    # Float Comparison Tests
    # ========================================

    def test_float_exact_match(self):
        """Floats should match exactly when no tolerance."""
        assert _compare_numeric_answers(3.14, 3.14, tolerance=0) is True

    def test_float_with_tolerance(self):
        """Floats within tolerance should match."""
        assert _compare_numeric_answers(10.0, 10.5, tolerance=0.1) is True

    def test_float_outside_tolerance(self):
        """Floats outside tolerance should not match."""
        assert _compare_numeric_answers(10.0, 12.0, tolerance=0.1) is False

    # ========================================
    # Mixed Type Comparison Tests
    # ========================================

    def test_int_vs_float(self):
        """Int and float with same value should match."""
        assert _compare_numeric_answers(255, 255.0) is True

    def test_string_vs_int(self):
        """String and int comparison should use string comparison."""
        # This tests the fallback behavior
        assert _compare_numeric_answers("255", 255) is False  # Different types
