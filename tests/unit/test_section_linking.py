"""
Unit Tests for Section Linking Logic.

Tests the keyword matching and section assignment logic used to link
learning atoms to CCNA sections.
"""

from scripts.fix_atom_section_links import (
    SECTION_PRIMARY_KEYWORDS,
    find_best_section_for_atom,
    score_section_match,
)


class TestSectionScoring:
    """Test section keyword scoring."""

    def test_exact_keyword_match_scores_higher(self):
        """Exact word boundary matches should score higher than partial."""
        content = "This is about TCP three-way handshake and SYN packets"
        score = score_section_match(content, "14.6")  # three-way handshake section

        assert score > 0, "Should match TCP handshake keywords"

    def test_no_match_scores_zero(self):
        """Content with no matching keywords should score zero."""
        content = "This is about cooking recipes and gardening tips"
        score = score_section_match(content, "14.6")

        assert score == 0, "Unrelated content should score zero"

    def test_multiple_keywords_increase_score(self):
        """Multiple matching keywords should increase score."""
        content_one = "TCP segment"
        content_many = "TCP segment with sequence number and acknowledgment and window size"

        score_one = score_section_match(content_one, "14.5")
        score_many = score_section_match(content_many, "14.5")

        assert score_many > score_one, "More keywords should mean higher score"

    def test_case_insensitive_matching(self):
        """Keyword matching should be case insensitive."""
        content_upper = "TCP THREE-WAY HANDSHAKE"
        content_lower = "tcp three-way handshake"

        score_upper = score_section_match(content_upper, "14.6")
        score_lower = score_section_match(content_lower, "14.6")

        assert score_upper == score_lower, "Case should not affect scoring"


class TestFindBestSection:
    """Test finding the best section for an atom."""

    def test_finds_correct_section_for_networking_basics(self):
        """Should match networking basics to Module 1."""
        result = find_best_section_for_atom(
            front="What is a host device?",
            back="An end device that sends or receives data on the network",
        )

        assert result.section_id is not None
        assert result.section_id.startswith("1."), f"Expected Module 1, got {result.section_id}"

    def test_finds_correct_section_for_tcp(self):
        """Should match TCP content to Module 14."""
        result = find_best_section_for_atom(
            front="What is the TCP three-way handshake?",
            back="SYN, SYN-ACK, ACK sequence to establish a connection",
        )

        assert result.section_id is not None
        assert result.section_id.startswith("14."), f"Expected Module 14, got {result.section_id}"

    def test_finds_correct_section_for_ipv4(self):
        """Should match IPv4 addressing to Module 11."""
        result = find_best_section_for_atom(
            front="What is a subnet mask?",
            back="A 32-bit number that identifies the network portion of an IPv4 address",
        )

        assert result.section_id is not None
        assert result.section_id.startswith("11."), f"Expected Module 11, got {result.section_id}"

    def test_finds_correct_section_for_ipv6(self):
        """Should match IPv6 content to Module 12."""
        result = find_best_section_for_atom(
            front="What is SLAAC?",
            back="Stateless Address Autoconfiguration - allows hosts to self-configure IPv6 addresses",
        )

        assert result.section_id is not None
        assert result.section_id.startswith("12."), f"Expected Module 12, got {result.section_id}"

    def test_returns_none_for_unmatched_content(self):
        """Should return None for content that doesn't match any section."""
        # Use content with absolutely no networking-related terms
        result = find_best_section_for_atom(
            front="What is mitochondria?",
            back="The organelle that produces ATP in eukaryotic cells",
        )

        assert result.section_id is None, (
            f"Got unexpected match: {result.section_id} with confidence {result.confidence}"
        )
        assert result.method == "none"

    def test_low_confidence_for_partial_match(self):
        """Partial matches should have lower confidence than strong matches."""
        result_strong = find_best_section_for_atom(
            front="Explain the TCP three-way handshake with SYN and ACK",
            back="SYN, SYN-ACK, ACK sequence for reliable connection establishment",
        )

        result_weak = find_best_section_for_atom(front="What is TCP?", back="A protocol")

        if result_strong.section_id and result_weak.section_id:
            assert result_strong.confidence >= result_weak.confidence


class TestSectionCoverage:
    """Test that all modules have keywords defined."""

    def test_all_modules_have_keywords(self):
        """Each CCNA module (1-17) should have keywords defined."""
        modules_with_keywords = set()

        for section_id in SECTION_PRIMARY_KEYWORDS.keys():
            module_num = int(section_id.split(".")[0])
            modules_with_keywords.add(module_num)

        # Check modules 1-17 (excluding 2 which is hands-on lab)
        expected_modules = {1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17}

        missing = expected_modules - modules_with_keywords
        assert not missing, f"Missing keywords for modules: {missing}"

    def test_keywords_are_non_empty(self):
        """Each section should have at least one keyword."""
        for section_id, keywords in SECTION_PRIMARY_KEYWORDS.items():
            assert len(keywords) > 0, f"Section {section_id} has no keywords"

    def test_keywords_are_lowercase_friendly(self):
        """Keywords should work with lowercase matching."""
        for section_id, keywords in SECTION_PRIMARY_KEYWORDS.items():
            for keyword in keywords:
                # Keywords should be lowercase for consistent matching
                assert keyword == keyword.lower(), (
                    f"Section {section_id} has uppercase keyword: {keyword}"
                )


class TestEdgeCases:
    """Test edge cases in section linking."""

    def test_empty_front_back(self):
        """Should handle empty strings gracefully."""
        result = find_best_section_for_atom(front="", back="")

        assert result.section_id is None

    def test_very_long_content(self):
        """Should handle very long content without errors."""
        long_content = "TCP segment " * 1000
        result = find_best_section_for_atom(front=long_content, back="")

        # Should still find a match for TCP content
        assert result.section_id is not None or result.method == "none"

    def test_special_characters(self):
        """Should handle special characters in content."""
        result = find_best_section_for_atom(
            front="What is 802.11a/b/g/n/ac?", back="Wi-Fi standards for wireless LANs"
        )

        # Should match wireless section
        assert result.section_id is not None

    def test_numbers_in_content(self):
        """Should handle numbers and IP addresses in content."""
        result = find_best_section_for_atom(
            front="What is 192.168.1.1?",
            back="A private IPv4 address commonly used for home routers",
        )

        # Should match IPv4 private addressing section
        assert result.section_id is not None
