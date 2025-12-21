Feature: Anki Deck Import and Quality Analysis
  As a learner with an existing Anki deck
  I want to import my cards and have them analyzed for quality
  So that I can identify which cards need improvement

  Background:
    Given I have an Anki deck with 500 flashcards
    And some cards have prerequisite tags like "tag:prereq:ccna:layer1:ipv4"
    And some cards are non-atomic (multiple concepts, too long)
    And Anki is running with AnkiConnect add-on on port 8765

  Scenario: Import Anki deck successfully
    When I run "nls anki import --deck 'CCNA Study'"
    Then all 500 cards should be imported to stg_anki_cards
    And prerequisite tags should be parsed into structured format
    And FSRS stats should be extracted (stability, difficulty, retrievability)
    And I should see a summary: "Imported 500 cards, 127 need splitting"
    And import batch ID should be generated
    And import should be logged in anki_import_log table

  Scenario: Import with dry-run mode
    When I run "nls anki import --deck 'CCNA Study' --dry-run"
    Then cards should be fetched but not written to database
    And I should see: "Preview: 500 cards would be imported"
    And no records should appear in stg_anki_cards

  Scenario: Import without quality analysis
    When I run "nls anki import --deck 'CCNA Study' --no-quality"
    Then cards should be imported to stg_anki_cards
    But quality_grade should be NULL
    And quality_issues should be empty
    And needs_split should be NULL

  Scenario: Quality analysis identifies non-atomic cards
    Given cards have been imported from Anki
    When I run "nls clean analyze --source anki"
    Then each card should be graded A-F based on atomicity thresholds
    And cards with BACK_TOO_LONG should be flagged
    And cards with ENUMERATION_DETECTED should be flagged
    And I should see: "Grade A: 203, B: 145, C: 75, D: 52, F: 25"
    And database should be updated with quality_grade for all cards

  Scenario: View quality report for a specific card
    Given card "NET-001" was imported with grade D
    When I request "GET /api/cards/NET-001/quality"
    Then I should see:
      | Field              | Value                               |
      | quality_grade      | D                                   |
      | quality_score      | 50                                  |
      | is_atomic          | false                               |
      | issues             | ["BACK_TOO_LONG", "MULTIPLE_FACTS"] |
      | front_word_count   | 18                                  |
      | back_word_count    | 42                                  |
      | front_char_count   | 125                                 |
      | back_char_count    | 287                                 |
      | needs_split        | true                                |
      | needs_rewrite      | true                                |
      | recommendations    | [array of strings]                  |

  Scenario: Import preserves FSRS scheduling data
    Given an Anki card has FSRS stats:
      | Field                | Value |
      | fsrs_stability_days  | 45.2  |
      | fsrs_difficulty      | 0.63  |
      | fsrs_retrievability  | 0.85  |
      | fsrs_last_review     | 2025-11-15 |
      | fsrs_due_date        | 2025-12-30 |
    When I import the deck
    Then the card in stg_anki_cards should have:
      | Field                | Value |
      | fsrs_stability_days  | 45.2  |
      | fsrs_difficulty      | 0.63  |
      | fsrs_retrievability  | 0.85  |
      | fsrs_last_review     | 2025-11-15 |
      | fsrs_due_date        | 2025-12-30 |

  Scenario: Parse prerequisite tag hierarchy
    Given an Anki card has tags: ["ccna", "tag:prereq:ccna:layer1:ipv4", "networking"]
    When I import the card
    Then prerequisite_tags should contain: ["tag:prereq:ccna:layer1:ipv4"]
    And prerequisite_hierarchy should be:
      | Field     | Value      |
      | domain    | ccna       |
      | topic     | layer1     |
      | subtopic  | ipv4       |
      | path      | ccna/layer1/ipv4 |

  Scenario: Handle cards without prerequisites
    Given an Anki card has tags: ["networking", "basics"]
    When I import the card
    Then prerequisite_tags should be empty array
    And prerequisite_hierarchy should be NULL
    And has_prerequisites should be false

  Scenario: View import statistics by batch ID
    Given I imported a deck with batch ID "abc-123-def-456"
    When I request "GET /api/anki/import/stats/abc-123-def-456"
    Then I should see:
      | Field                        | Value |
      | import_batch_id              | abc-123-def-456 |
      | deck_name                    | CCNA Study |
      | started_at                   | 2025-12-02T10:30:00Z |
      | completed_at                 | 2025-12-02T10:32:15Z |
      | status                       | completed |
      | cards_imported               | 500 |
      | cards_with_fsrs              | 432 |
      | cards_with_prerequisites     | 127 |
      | cards_needing_split          | 45 |
      | grade_a_count                | 203 |
      | grade_b_count                | 145 |
      | grade_c_count                | 75 |
      | grade_d_count                | 52 |
      | grade_f_count                | 25 |

  Scenario: Get latest import statistics
    Given I have imported 3 decks at different times
    When I request "GET /api/anki/import/latest"
    Then I should receive statistics for the most recent import
    And the response should include the latest batch ID

  Scenario: View quality distribution for entire deck
    Given I have imported a deck with 500 cards
    When I request "GET /api/anki/cards/quality"
    Then I should see:
      | Field              | Value |
      | total_cards        | 500   |
      | needs_split_count  | 45    |
      | non_atomic_count   | 127   |
    And distribution should show:
      | Grade | Count | Percentage |
      | A     | 203   | 40.6       |
      | B     | 145   | 29.0       |
      | C     | 75    | 15.0       |
      | D     | 52    | 10.4       |
      | F     | 25    | 5.0        |

  Scenario: View prerequisite statistics
    Given I have imported a deck with prerequisite tags
    When I request "GET /api/anki/cards/prerequisites"
    Then I should see:
      | Field                        | Value |
      | cards_with_prerequisites     | 127   |
      | cards_without_prerequisites  | 373   |
    And unique_domains should include: ["cs", "ccna"]
    And unique_topics should include: ["networking", "security"]
    And prerequisite_hierarchy should show card counts per domain/topic

  Scenario: Import fails if AnkiConnect is not running
    Given Anki is not running
    When I run "nls anki import --deck 'CCNA Study'"
    Then I should see error: "Failed to connect to AnkiConnect"
    And the command should exit with code 1
    And helpful message should suggest starting Anki with AnkiConnect

  Scenario: Import fails if deck does not exist
    Given Anki is running but deck "NonExistentDeck" does not exist
    When I run "nls anki import --deck 'NonExistentDeck'"
    Then I should see error: "Deck not found: NonExistentDeck"
    And the command should exit with code 1
    And available decks should be listed

  Scenario: Batch analysis with filters
    Given I have imported cards with various grades
    When I run "nls clean analyze --source anki --min-grade D"
    Then only cards with grade D and F should be analyzed
    And I should see: "Analyzed 77 cards (52 D, 25 F)"
    And cards with grades A, B, C should remain unchanged

  Scenario: Re-import updates existing cards
    Given I have previously imported a deck
    And I have modified cards in Anki
    When I run "nls anki import --deck 'CCNA Study'"
    Then existing cards should be updated (not duplicated)
    And anki_note_id should be used as unique identifier
    And updated_at timestamp should be refreshed
    And previous quality analysis should be preserved unless --force-reanalyze is used

  # ============================================================================
  # Batch Import and Performance Scenarios
  # ============================================================================

  Scenario: Batch import with progress indicator
    Given I have a deck with 5,000 cards
    When I run "nls anki import --deck 'Large Deck'"
    Then I should see progress updates every 100 cards:
      | Imported | Status                                |
      | 100      | Importing cards: 100/5000 (2%)        |
      | 500      | Importing cards: 500/5000 (10%)       |
      | 2500     | Importing cards: 2500/5000 (50%)      |
      | 5000     | Importing cards: 5000/5000 (100%)     |
    And progress bar should be displayed in CLI
    And final import time should be reported

  Scenario: Batch import with transaction batching
    Given I have a deck with 10,000 cards
    When I run "nls anki import --deck 'Huge Deck' --batch-size 500"
    Then cards should be inserted in batches of 500
    And each batch should be committed separately
    And if batch 5 fails, batches 1-4 should remain committed
    And import should continue with batch 6 after error handling
    And I should see: "Imported 10,000 cards in 20 batches (18 succeeded, 2 failed)"

  Scenario: Import failure recovery with resume
    Given I started importing a deck with 5,000 cards
    And import failed after 2,500 cards
    When I run "nls anki import --deck 'CCNA Study' --resume"
    Then only remaining 2,500 cards should be imported
    And previously imported cards should be skipped
    And I should see: "Resuming import from card 2501/5000"

  Scenario: Import failure recovery without resume flag
    Given I started importing a deck with 5,000 cards
    And import failed after 2,500 cards
    When I run "nls anki import --deck 'CCNA Study'"
    Then system should detect partial import
    And I should be prompted: "Partial import detected. Resume? (y/n)"
    And if I answer "y", import should resume from card 2501
    And if I answer "n", import should start from beginning

  Scenario: Large deck optimization with streaming
    Given I have a deck with 50,000 cards
    When I run "nls anki import --deck 'Medical Terminology'"
    Then cards should be fetched in chunks from AnkiConnect
    And cards should be processed in streaming fashion
    And memory usage should remain below 500 MB
    And I should see: "Imported 50,000 cards (peak memory: 387 MB)"

  Scenario: Memory management with card batching
    Given I have a deck with 20,000 cards
    When I run "nls anki import --deck 'Large Deck'"
    Then cards should be released from memory after each batch
    And garbage collection should be triggered periodically
    And memory should not grow linearly with deck size
    And import should complete without OutOfMemory errors

  Scenario: Concurrent import handling - first import wins
    Given user A starts importing "Deck A" at 10:00:00
    And user B starts importing "Deck A" at 10:00:05
    When both imports are running
    Then user B should see warning: "Import already in progress for Deck A"
    And user B's import should wait or be rejected
    And after user A completes, user B's import should proceed

  Scenario: Import timeout for unresponsive AnkiConnect
    Given AnkiConnect is slow to respond
    When I run "nls anki import --deck 'CCNA Study' --timeout 120"
    And AnkiConnect doesn't respond within 120 seconds
    Then import should timeout
    And I should see error: "AnkiConnect timeout after 120 seconds"
    And partial data should be rolled back
    And I should see suggestion: "Check if Anki is frozen or restart AnkiConnect"

  Scenario: Import with connection retry logic
    Given AnkiConnect connection is unstable
    When I run "nls anki import --deck 'CCNA Study'"
    And connection fails on request 5
    Then import should retry request 5 up to 3 times
    And retry should use exponential backoff (1s, 2s, 4s)
    And if retry succeeds, import should continue
    And if all retries fail, import should abort with error

  Scenario: Import performance benchmarking
    Given I have a deck with 1,000 cards
    When I run "nls anki import --deck 'Test Deck' --benchmark"
    Then I should see performance metrics:
      | Metric                     | Value          |
      | Total time                 | 45.2 seconds   |
      | AnkiConnect fetch time     | 12.3 seconds   |
      | Quality analysis time      | 18.5 seconds   |
      | Database insert time       | 10.2 seconds   |
      | Overhead                   | 4.2 seconds    |
      | Cards per second           | 22.1           |
      | Memory peak                | 156 MB         |

  Scenario: Import with database transaction isolation
    Given I have two decks importing simultaneously
    When "Deck A" and "Deck B" imports run concurrently
    Then each import should use separate database transactions
    And imports should not deadlock each other
    And both imports should complete successfully
    And final counts should be: Deck A cards + Deck B cards

  Scenario: Import handles database constraint violations gracefully
    Given I have a card with duplicate anki_note_id in database
    When I import a deck containing that card
    Then duplicate card should be updated (not cause error)
    And ON CONFLICT clause should handle upsert correctly
    And import should continue for remaining cards
    And I should see: "Updated 1 existing card, imported 499 new cards"

  Scenario: Import with validation before database insert
    Given I have a deck with some invalid cards:
      | Card ID | Issue                          |
      | 123     | Missing front text             |
      | 456     | Missing back text              |
      | 789     | Invalid FSRS difficulty (1.5)  |
    When I run "nls anki import --deck 'Test Deck' --validate"
    Then invalid cards should be identified before insert
    And I should see warnings:
      - "Card 123: Missing front text (skipped)"
      - "Card 456: Missing back text (skipped)"
      - "Card 789: Invalid FSRS difficulty 1.5 > 1.0 (skipped)"
    And only 497 valid cards should be imported
    And validation report should be saved to disk

  Scenario: Import generates detailed import log
    Given I have imported a deck
    When I check the import log file
    Then log should contain:
      - Import batch ID
      - Deck name
      - Start and end timestamps
      - Count of cards imported/updated/skipped
      - List of skipped card IDs with reasons
      - Quality analysis summary
      - Performance metrics
      - Any errors or warnings
    And log should be saved to: logs/anki_import_{batch_id}.log

  Scenario: Import with export to CSV for review
    Given I want to review import results
    When I run "nls anki import --deck 'CCNA Study' --export-csv"
    Then a CSV file should be generated with columns:
      | Column Name        | Description                |
      | anki_note_id       | Anki note identifier       |
      | front              | Question text              |
      | back               | Answer text                |
      | tags               | Comma-separated tags       |
      | quality_grade      | A-F quality grade          |
      | quality_score      | 0-100 quality score        |
      | needs_split        | Boolean flag               |
      | needs_rewrite      | Boolean flag               |
    And CSV should be saved to: exports/anki_import_{batch_id}.csv
    And I should see: "Exported import results to anki_import_abc123.csv"

  Scenario: Import statistics aggregation
    Given I have imported 5 decks over time
    When I request "GET /api/anki/import/statistics"
    Then I should see aggregate statistics:
      | Metric                     | Value  |
      | Total imports              | 5      |
      | Total cards imported       | 2,450  |
      | Total with FSRS            | 2,100  |
      | Total with prerequisites   | 850    |
      | Average import time        | 52 sec |
      | Average cards per import   | 490    |
      | Success rate               | 100%   |

  Scenario: Import with post-import cleanup
    Given I have imported a deck
    When import completes successfully
    Then temporary files should be cleaned up
    And memory should be released
    And database connections should be closed
    And AnkiConnect connection should be closed
    And I should see: "Import completed. Cleaned up temporary resources."
