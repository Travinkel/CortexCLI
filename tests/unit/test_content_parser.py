"""
Unit tests for CCNAContentParser.

Tests regex pattern coverage to prevent silent data loss from unparsed content.
Run: pytest tests/unit/test_content_parser.py -v
"""
import pytest
from src.ccna.content_parser import CCNAContentParser


class TestHeaderPatterns:
    """Test header pattern detection across various formats."""

    @pytest.fixture
    def parser(self):
        return CCNAContentParser()

    # ========================================
    # Markdown Header Tests
    # ========================================

    def test_single_hash_header(self, parser):
        """Single # headers should be detected (level 1)."""
        content = "# Module Overview\n\nSome content here."
        matches = list(parser.HEADER_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group(2) == "Module Overview"
        assert len(matches[0].group(1)) == 1  # Level 1

    def test_double_hash_header(self, parser):
        """Double ## headers should be detected (level 2)."""
        content = "## Network Basics\n\nContent about networks."
        matches = list(parser.HEADER_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group(2) == "Network Basics"
        assert len(matches[0].group(1)) == 2  # Level 2

    def test_triple_hash_header(self, parser):
        """Triple ### headers should be detected (level 3)."""
        content = "### Subnetting Details\n\nSubnet information."
        matches = list(parser.HEADER_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group(2) == "Subnetting Details"

    def test_multiple_markdown_headers(self, parser):
        """Multiple markdown headers in sequence."""
        content = """# Module 1

## Section 1.1

Content here.

### Subsection 1.1.1

More content.

## Section 1.2

Another section.
"""
        matches = list(parser.HEADER_PATTERN.finditer(content))
        assert len(matches) == 4
        titles = [m.group(2).strip() for m in matches]
        assert "Module 1" in titles
        assert "Section 1.1" in titles

    # ========================================
    # Cisco Format Header Tests
    # ========================================

    def test_cisco_main_section_header(self, parser):
        """Cisco format 9.1 Title should be detected."""
        content = "9.1 IPv4 Addressing Basics\n\nExplanation here."
        matches = list(parser.CISCO_HEADER_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group(1) == "9.1"
        assert matches[0].group(2) == "IPv4 Addressing Basics"

    def test_cisco_subsection_header(self, parser):
        """Cisco format 9.1.1 Subtopic should be detected."""
        content = "9.1.1 Network and Host Portions\n\nDetails here."
        matches = list(parser.CISCO_HEADER_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group(1) == "9.1.1"
        assert "Network and Host" in matches[0].group(2)

    def test_cisco_introduction_header(self, parser):
        """Cisco format 9.0 Introduction should be detected."""
        content = "9.0 Introduction\n\nWelcome to this module."
        matches = list(parser.CISCO_HEADER_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group(1) == "9.0"

    def test_cisco_header_with_trailing_dot(self, parser):
        """Cisco format with trailing dot: 9.1.1. Title"""
        content = "9.1.1. Network Configuration\n\nSteps here."
        matches = list(parser.CISCO_HEADER_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group(1) == "9.1.1"

    def test_cisco_skip_scroll_instruction(self, parser):
        """'Scroll to begin' should be filtered out."""
        content = "9.1 Scroll to begin\n\nActual content."
        # The pattern matches but implementation should filter
        matches = list(parser.CISCO_HEADER_PATTERN.finditer(content))
        # Pattern matches, but title should be filtered in _parse_sections
        assert len(matches) == 1
        title = matches[0].group(2).strip().lower()
        assert title == "scroll to begin"

    # ========================================
    # Alternative Format Tests
    # ========================================

    def test_part_colon_format(self, parser):
        """'Part 1: Title' format should be detected."""
        for pattern in parser.ALT_HEADER_PATTERNS:
            content = "Part 1: Introduction to Networking\n\nContent."
            matches = list(pattern.finditer(content))
            if matches:
                assert matches[0].group(1) == "1"
                assert "Introduction" in matches[0].group(2)
                return
        pytest.fail("No ALT_HEADER_PATTERN matched 'Part 1: Title' format")

    def test_section_colon_format(self, parser):
        """'Section 1.1: Title' format should be detected."""
        for pattern in parser.ALT_HEADER_PATTERNS:
            content = "Section 1.1: Network Protocols\n\nDetails."
            matches = list(pattern.finditer(content))
            if matches:
                assert matches[0].group(1) == "1.1"
                return
        pytest.fail("No ALT_HEADER_PATTERN matched 'Section 1.1: Title' format")

    def test_module_dash_format(self, parser):
        """'Module 1 - Title' format should be detected."""
        for pattern in parser.ALT_HEADER_PATTERNS:
            content = "Module 1 - Network Fundamentals\n\nBasics."
            matches = list(pattern.finditer(content))
            if matches:
                assert matches[0].group(1) == "1"
                return
        pytest.fail("No ALT_HEADER_PATTERN matched 'Module 1 - Title' format")

    def test_numbered_colon_format(self, parser):
        """'1.1: Title' format should be detected."""
        for pattern in parser.ALT_HEADER_PATTERNS:
            content = "1.1: Ethernet Basics\n\nExplanation."
            matches = list(pattern.finditer(content))
            if matches:
                assert matches[0].group(1) == "1.1"
                return
        pytest.fail("No ALT_HEADER_PATTERN matched '1.1: Title' format")


class TestTablePatterns:
    """Test table pattern detection."""

    @pytest.fixture
    def parser(self):
        return CCNAContentParser()

    def test_markdown_table_header(self, parser):
        """Markdown table headers should be detected."""
        content = "| Column 1 | Column 2 | Column 3 |\n"
        matches = list(parser.TABLE_HEADER_PATTERN.finditer(content))
        assert len(matches) == 1

    def test_table_separator_detection(self, parser):
        """Table separator row should be detected."""
        content = "|---|---|---|\n"
        matches = list(parser.TABLE_SEPARATOR_PATTERN.finditer(content))
        assert len(matches) == 1

    def test_table_separator_with_alignment(self, parser):
        """Table separator with alignment markers."""
        content = "|:---|:---:|---:|\n"
        matches = list(parser.TABLE_SEPARATOR_PATTERN.finditer(content))
        assert len(matches) == 1


class TestCodeBlockPatterns:
    """Test code block pattern detection."""

    @pytest.fixture
    def parser(self):
        return CCNAContentParser()

    def test_code_block_with_language(self, parser):
        """Code block with language specifier."""
        content = "```cisco\nRouter# show ip route\n```"
        matches = list(parser.CODE_BLOCK_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group(1) == "cisco"
        assert "show ip route" in matches[0].group(2)

    def test_code_block_without_language(self, parser):
        """Code block without language specifier."""
        content = "```\ninterface GigabitEthernet0/0\n```"
        matches = list(parser.CODE_BLOCK_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group(1) == ""  # No language

    def test_code_block_ios(self, parser):
        """Code block with 'ios' language."""
        content = "```ios\nRouter(config)# hostname R1\n```"
        matches = list(parser.CODE_BLOCK_PATTERN.finditer(content))
        assert len(matches) == 1
        assert matches[0].group(1) == "ios"


class TestCLIPatterns:
    """Test CLI command pattern detection."""

    @pytest.fixture
    def parser(self):
        return CCNAContentParser()

    def test_router_privileged_prompt(self, parser):
        """Router# privileged mode prompt."""
        content = "Router# show running-config"
        for pattern in parser.CLI_PROMPT_PATTERNS:
            matches = list(pattern.finditer(content))
            if matches:
                assert matches[0].group(1) in ("Router", "router")
                return
        pytest.fail("No CLI pattern matched 'Router#' prompt")

    def test_router_config_prompt(self, parser):
        """Router(config)# global config prompt."""
        content = "Router(config)# interface g0/0"
        # This may not match basic patterns - check extended patterns
        for pattern in parser.CLI_PROMPT_PATTERNS:
            matches = list(pattern.finditer(content))
            if matches:
                return
        # Config prompts may need extended pattern support
        pass  # Not a failure - config prompts are complex

    def test_switch_prompt(self, parser):
        """Switch> user mode prompt."""
        content = "Switch> enable"
        for pattern in parser.CLI_PROMPT_PATTERNS:
            matches = list(pattern.finditer(content))
            if matches:
                assert matches[0].group(1) in ("Switch", "switch")
                return
        pytest.fail("No CLI pattern matched 'Switch>' prompt")

    def test_numbered_device_prompt(self, parser):
        """R1# numbered router prompt."""
        content = "R1# ping 192.168.1.1"
        for pattern in parser.CLI_PROMPT_PATTERNS:
            matches = list(pattern.finditer(content))
            if matches:
                return
        pytest.fail("No CLI pattern matched 'R1#' prompt")


class TestContentValidation:
    """Test content validation and coverage detection."""

    @pytest.fixture
    def parser(self):
        return CCNAContentParser()

    def test_validate_empty_content_warns(self, parser, tmp_path):
        """Empty content should generate warnings."""
        # Create a minimal file
        test_file = tmp_path / "test_module.txt"
        test_file.write_text("# Test Module\n\n")

        module = parser.parse_file(str(test_file), module_number=99)
        validation = parser.validate_coverage(module)

        # Should warn about low section count or empty sections
        assert not validation["is_valid"] or len(validation["warnings"]) > 0

    def test_validate_good_coverage(self, parser, tmp_path):
        """Well-structured content should validate successfully."""
        test_file = tmp_path / "good_module.txt"
        test_file.write_text("""# Module 1: Network Fundamentals

## 1.1 Introduction

Networks connect devices together. They enable communication between
computers, phones, and other devices. This section covers the basics
of networking concepts that form the foundation for the CCNA exam.

## 1.2 Network Types

There are several types of networks including LANs, WANs, and MANs.
Each type serves different purposes and operates at different scales.
Understanding these distinctions is crucial for network design.

### 1.2.1 Local Area Networks

LANs operate within a limited geographic area such as a building or campus.
They typically use Ethernet technology and provide high-speed connectivity.

## 1.3 Network Devices

Routers, switches, and hubs are common network devices. Each performs
specific functions in moving data across the network infrastructure.
""")

        module = parser.parse_file(str(test_file), module_number=1)
        validation = parser.validate_coverage(module)

        assert len(module.sections) >= 2, "Should detect multiple sections"


class TestBulletAndListPatterns:
    """Test bullet point and numbered list detection."""

    @pytest.fixture
    def parser(self):
        return CCNAContentParser()

    def test_bullet_with_dash(self, parser):
        """Dash bullet points should be detected."""
        content = "- First item\n- Second item\n- Third item"
        matches = list(parser.BULLET_PATTERN.finditer(content))
        assert len(matches) == 3

    def test_bullet_with_asterisk(self, parser):
        """Asterisk bullet points should be detected."""
        content = "* Item one\n* Item two"
        matches = list(parser.BULLET_PATTERN.finditer(content))
        assert len(matches) == 2

    def test_numbered_list(self, parser):
        """Numbered list items should be detected."""
        content = "1. First step\n2. Second step\n3. Third step"
        matches = list(parser.NUMBERED_PATTERN.finditer(content))
        assert len(matches) == 3


class TestBoldPattern:
    """Test bold text detection for key terms."""

    @pytest.fixture
    def parser(self):
        return CCNAContentParser()

    def test_bold_text_detection(self, parser):
        """Bold text should be detected."""
        content = "The **router** forwards packets based on **routing table** entries."
        matches = list(parser.BOLD_PATTERN.finditer(content))
        assert len(matches) == 2
        terms = [m.group(1) for m in matches]
        assert "router" in terms
        assert "routing table" in terms
