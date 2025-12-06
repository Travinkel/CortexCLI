Feature: Quality Analysis and Grading
  As a learner
  I want my flashcards analyzed for quality issues
  So that I can improve my learning materials and identify cards that need fixing

  Background:
    Given the CardQualityAnalyzer is initialized with version "1.0.0"
    And evidence-based thresholds are configured:
      | Threshold                  | Value |
      | FRONT_WORDS_OPTIMAL        | 15    |
      | FRONT_WORDS_MAX            | 25    |
      | FRONT_CHARS_MAX            | 200   |
      | BACK_WORDS_OPTIMAL         | 5     |
      | BACK_WORDS_MAX             | 15    |
      | BACK_CHARS_MAX             | 120   |
      | CODE_LINES_OPTIMAL         | 5     |
      | CODE_LINES_MAX             | 10    |
      | GRADE_A_MIN                | 90    |
      | GRADE_B_MIN                | 75    |
      | GRADE_C_MIN                | 60    |
      | GRADE_D_MIN                | 40    |

  Scenario: Grade A - Perfect atomic flashcard
    Given a flashcard with:
      | Field | Value                              |
      | Front | What is TCP?                       |
      | Back  | Transmission Control Protocol      |
    When I analyze the card
    Then quality_grade should be "A"
    And quality_score should be 100
    And is_atomic should be true
    And is_verbose should be false
    And needs_split should be false
    And needs_rewrite should be false
    And issues should be empty
    And recommendations should be empty

  Scenario: Grade B - Good card with minor verbosity
    Given a flashcard with:
      | Field | Value                                                               |
      | Front | What protocol ensures reliable delivery of packets over a network?  |
      | Back  | TCP (Transmission Control Protocol) ensures reliable delivery       |
    When I analyze the card
    Then quality_grade should be "B"
    And quality_score should be between 75 and 89
    And is_atomic should be true
    And is_verbose should be true
    And issues should include "BACK_VERBOSE"
    And recommendations should include "Back has"

  Scenario: Grade C - Acceptable but needs improvement
    Given a flashcard with:
      | Field | Value                                                                     |
      | Front | What are the main differences between TCP and UDP?                        |
      | Back  | TCP is connection-oriented and reliable. UDP is connectionless and faster |
    When I analyze the card
    Then quality_grade should be "C"
    And quality_score should be between 60 and 74
    And is_atomic should be false
    And issues should include "MULTIPLE_FACTS"

  Scenario: Grade D - Poor, needs rewrite
    Given a flashcard with:
      | Field | Value                                                                                                             |
      | Front | Explain how the TCP three-way handshake works and why it's necessary for establishing reliable connections        |
      | Back  | The client sends SYN, server responds with SYN-ACK, client sends ACK. This ensures both parties are ready         |
    When I analyze the card
    Then quality_grade should be "D"
    And quality_score should be between 40 and 59
    And is_atomic should be true
    And needs_rewrite should be true
    And issues should include "FRONT_TOO_LONG"
    And issues should include "BACK_TOO_LONG"

  Scenario: Grade F - Fail, block from review
    Given a flashcard with:
      | Field | Value                                                                                                                                   |
      | Front | What are the seven layers of the OSI model and what does each layer do?                                                                 |
      | Back  | 1. Physical - cables and bits. 2. Data Link - MAC addresses. 3. Network - IP routing. 4. Transport - TCP/UDP. 5. Session - connections. |
    When I analyze the card
    Then quality_grade should be "F"
    And quality_score should be less than 40
    And is_atomic should be false
    And needs_split should be true
    And needs_rewrite should be true
    And issues should include "FRONT_TOO_LONG"
    And issues should include "BACK_TOO_LONG"
    And issues should include "ENUMERATION_DETECTED"
    And issues should include "MULTI_SUBQUESTION"
    And recommendations should include "splitting"

  Scenario: Detect FRONT_TOO_LONG issue
    Given a flashcard with front containing 30 words
    When I analyze the card
    Then issues should include "FRONT_TOO_LONG"
    And recommendations should include "Front has 30 words (max: 25)"
    And recommendations should include "simplifying the question"

  Scenario: Detect FRONT_VERBOSE issue
    Given a flashcard with front containing 20 words
    When I analyze the card
    Then issues should include "FRONT_VERBOSE"
    And recommendations should include "Front has 20 words (optimal: ≤15)"
    And recommendations should include "more concise"

  Scenario: Detect BACK_TOO_LONG issue
    Given a flashcard with back containing 20 words
    When I analyze the card
    Then issues should include "BACK_TOO_LONG"
    And recommendations should include "Back has 20 words (max: 15)"
    And recommendations should include "splitting into multiple atomic cards"

  Scenario: Detect BACK_VERBOSE issue
    Given a flashcard with back containing 8 words
    When I analyze the card
    Then issues should include "BACK_VERBOSE"
    And recommendations should include "Back has 8 words (optimal: ≤5)"

  Scenario: Detect FRONT_CHARS_EXCEEDED issue
    Given a flashcard with front containing 250 characters
    When I analyze the card
    Then issues should include "FRONT_CHARS_EXCEEDED"
    And recommendations should include "Front has 250 chars (max: 200)"
    And recommendations should include "Reduce visual complexity"

  Scenario: Detect BACK_CHARS_EXCEEDED issue
    Given a flashcard with back containing 150 characters
    When I analyze the card
    Then issues should include "BACK_CHARS_EXCEEDED"
    And recommendations should include "Back has 150 chars (max: 120)"

  Scenario: Detect CODE_TOO_LONG issue
    Given a flashcard with code block containing 15 lines
    When I analyze the card
    Then issues should include "CODE_TOO_LONG"
    And recommendations should include "Code has 15 lines (max: 10)"
    And recommendations should include "Focus on the key snippet only"

  Scenario: Detect CODE_VERBOSE issue
    Given a flashcard with code block containing 7 lines
    When I analyze the card
    Then issues should include "CODE_VERBOSE"
    And recommendations should include "Code has 7 lines (optimal: ≤5)"

  Scenario: Detect ENUMERATION with bullet points
    Given a flashcard with back:
      """
      - Physical layer
      - Data Link layer
      - Network layer
      - Transport layer
      """
    When I analyze the card
    Then issues should include "ENUMERATION_DETECTED"
    And is_atomic should be false
    And needs_split should be true
    And recommendations should include "splitting into separate cards for each item"

  Scenario: Detect ENUMERATION with numbered list
    Given a flashcard with back:
      """
      1. Physical layer
      2. Data Link layer
      3. Network layer
      """
    When I analyze the card
    Then issues should include "ENUMERATION_DETECTED"
    And is_atomic should be false

  Scenario: Detect ENUMERATION with letter markers
    Given a flashcard with back:
      """
      a) First step
      b) Second step
      c) Third step
      """
    When I analyze the card
    Then issues should include "ENUMERATION_DETECTED"

  Scenario: Detect MULTIPLE_FACTS
    Given a flashcard with back containing 3 sentences
    When I analyze the card
    Then issues should include "MULTIPLE_FACTS"
    And recommendations should include "One atomic fact per card is optimal"

  Scenario: Detect MULTIPLE_FACTS with causal chains
    Given a flashcard with back:
      """
      TCP uses a three-way handshake because it ensures both parties are ready.
      Therefore, connections are reliable since acknowledgments are required.
      """
    When I analyze the card
    Then issues should include "MULTIPLE_FACTS"
    And back should have multiple causal markers: ["because", "therefore", "since"]

  Scenario: Detect MULTI_SUBQUESTION with multiple question marks
    Given a flashcard with front:
      """
      What is TCP? What is UDP? How do they differ?
      """
    When I analyze the card
    Then issues should include "MULTI_SUBQUESTION"
    And recommendations should include "splitting into separate cards"

  Scenario: Detect MULTI_SUBQUESTION with compound questions
    Given a flashcard with front:
      """
      What is TCP and how does it work?
      """
    When I analyze the card
    Then issues should include "MULTI_SUBQUESTION"

  Scenario: Code blocks excluded from word count
    Given a flashcard with back:
      """
      Use this command:
      ```
      git commit -m "message"
      git push origin main
      ```
      This pushes changes.
      """
    When I analyze the card
    Then back_word_count should only count non-code text
    And code_line_count should be 2

  Scenario: Penalty scoring for multiple issues
    Given a flashcard with issues:
      | Issue                  | Penalty |
      | FRONT_TOO_LONG         | -30     |
      | BACK_TOO_LONG          | -30     |
      | ENUMERATION_DETECTED   | -30     |
    When I analyze the card
    Then quality_score should be 10
    And quality_grade should be "F"

  Scenario: Batch analysis updates database
    Given I have 100 cards in stg_anki_cards without quality analysis
    When I run batch analysis on all cards
    Then all 100 cards should have quality_grade set
    And all 100 cards should have quality_score set
    And all 100 cards should have analyzer_version set to "1.0.0"
    And database should be updated in single transaction

  Scenario: Batch analysis with deck filter
    Given I have cards from two decks:
      | Deck Name   | Card Count |
      | CCNA Study  | 500        |
      | Python Quiz | 300        |
    When I run "nls clean analyze --source anki --deck 'CCNA Study'"
    Then only 500 cards from CCNA Study should be analyzed
    And Python Quiz cards should remain unchanged

  Scenario: Batch analysis progress reporting
    Given I have 1000 cards to analyze
    When I run batch analysis
    Then I should see progress updates:
      | Analyzed | Status                     |
      | 100      | Analyzed 100/1000 (10%)    |
      | 500      | Analyzed 500/1000 (50%)    |
      | 1000     | Analyzed 1000/1000 (100%)  |
    And final summary should show grade distribution

  Scenario: Get quality summary
    Given I have analyzed 500 cards from Anki
    When I request "GET /api/quality/summary?source=anki"
    Then I should see:
      | Field               | Value |
      | total_cards         | 500   |
      | grade_a             | 203   |
      | grade_b             | 145   |
      | grade_c             | 75    |
      | grade_d             | 52    |
      | grade_f             | 25    |
      | non_atomic          | 127   |
      | needs_split         | 45    |
      | needs_rewrite       | 77    |
      | avg_score           | 74.2  |

  Scenario: Quality report for individual card
    Given card "NET-042" has been analyzed
    When I request the quality report via API
    Then I should receive QualityReport as JSON:
      """
      {
        "score": 50.0,
        "grade": "D",
        "issues": ["BACK_TOO_LONG", "ENUMERATION_DETECTED"],
        "recommendations": [
          "Back has 42 words (max: 15). Consider splitting into multiple atomic cards.",
          "Enumeration detected in answer. Consider splitting into separate cards for each item."
        ],
        "front_word_count": 18,
        "back_word_count": 42,
        "front_char_count": 125,
        "back_char_count": 287,
        "code_line_count": 0,
        "is_atomic": false,
        "is_verbose": true,
        "needs_split": true,
        "needs_rewrite": true
      }
      """

  Scenario: Re-analyze with updated thresholds
    Given I have cards analyzed with version "1.0.0"
    And I update thresholds to stricter values
    When I run "nls clean analyze --source anki --force"
    Then all cards should be re-analyzed
    And analyzer_version should be updated to "1.1.0"
    And some cards may receive different grades

  Scenario: Quality trends over time
    Given I have imported and analyzed cards on multiple dates:
      | Date       | Grade A | Grade B | Grade C | Grade D | Grade F |
      | 2025-11-01 | 150     | 120     | 100     | 80      | 50      |
      | 2025-12-01 | 180     | 130     | 90      | 60      | 40      |
      | 2025-12-02 | 203     | 145     | 75      | 52      | 25      |
    When I request quality trend analysis
    Then I should see improvement over time
    And Grade A count should show increasing trend
    And Grade F count should show decreasing trend
