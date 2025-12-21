Feature: Cleaning Pipeline Orchestration
  As a system administrator
  I want to run an automated cleaning pipeline on imported content
  So that staging data is transformed into clean, canonical learning content

  Background:
    Given staging tables contain imported data from Notion and Anki
    And canonical tables are ready to receive clean data
    And CardQualityAnalyzer is configured with evidence-based thresholds
    And DuplicateDetector is initialized
    And AIRewriter is connected to Gemini 2.0 Flash
    And CleaningPipeline orchestrator is ready

  # ============================================================================
  # Full Pipeline Scenarios
  # ============================================================================

  Scenario: Run full cleaning pipeline
    Given I have 500 cards in staging tables
    When I run "nls clean run"
    Then pipeline should execute in order:
      | Stage                  | Action                                    |
      | 1. Transform           | Copy staging → canonical with mappings    |
      | 2. Quality Analysis    | Grade all cards A-F                       |
      | 3. Duplicate Detection | Find exact and fuzzy duplicates           |
      | 4. Summary             | Generate pipeline report                  |
    And I should see summary:
      | Metric                 | Value |
      | Cards transformed      | 500   |
      | Quality grades assigned| 500   |
      | Duplicates detected    | 12    |
      | Total time             | 45 sec|
    And all stages should complete successfully

  Scenario: Run pipeline with AI rewriting enabled
    Given I have 500 cards in staging tables
    And 77 cards have grade D or F
    When I run "nls clean run --rewrite"
    Then pipeline should execute with additional stage:
      | Stage                  | Action                                    |
      | 1. Transform           | Copy staging → canonical                  |
      | 2. Quality Analysis    | Grade all cards                           |
      | 3. Duplicate Detection | Find duplicates                           |
      | 4. AI Rewriting        | Queue grade D/F cards for AI rewriting    |
      | 5. Summary             | Generate report                           |
    And 77 cards should be queued in review_queue
    And I should see: "Queued 77 cards for AI rewriting (52 D, 25 F)"

  Scenario: Run pipeline with specific minimum grade
    Given I have cards with various grades
    When I run "nls clean run --rewrite --min-grade F"
    Then only grade F cards should be queued for rewriting
    And grade D cards should be skipped
    And I should see: "Queued 25 F-grade cards for rewriting"

  Scenario: Run pipeline in dry-run mode
    Given I have 500 cards in staging tables
    When I run "nls clean run --dry-run"
    Then all stages should be simulated without database writes
    And I should see preview:
      | Stage                  | Action                         |
      | 1. Transform           | Would transform 500 cards      |
      | 2. Quality Analysis    | Would grade 500 cards          |
      | 3. Duplicate Detection | Would detect ~12 duplicates    |
    And canonical tables should remain unchanged
    And I should see: "Dry-run complete. No changes made."

  # ============================================================================
  # Transformation Stage
  # ============================================================================

  Scenario: Transform staging to canonical (flashcards)
    Given stg_anki_cards contains 500 records
    When transformation stage runs
    Then each staging record should be mapped to clean_atoms:
      | Staging Field          | Canonical Field    | Transformation         |
      | anki_note_id           | source_id          | Direct copy            |
      | front                  | front_content      | Direct copy            |
      | back                   | back_content       | Direct copy            |
      | tags                   | tags               | JSON array             |
      | fsrs_stability_days    | fsrs_stability     | Direct copy            |
      | prerequisite_tags      | prerequisite_tags  | JSON array             |
    And 500 records should be inserted into clean_atoms
    And source field should be set to "anki"

  Scenario: Transform Notion flashcards to canonical
    Given stg_notion_flashcards contains 200 records
    When transformation stage runs
    Then Notion pages should be transformed to clean_atoms
    And front/back should be extracted from properties JSONB
    And notion_page_id should map to source_id
    And source field should be set to "notion"

  Scenario: Transform with deduplication during insert
    Given clean_atoms already contains 100 cards
    And stg_anki_cards contains 120 cards (20 duplicates)
    When transformation stage runs
    Then only 20 new cards should be inserted
    And 100 existing cards should be updated
    And I should see: "Transformed 120 cards (20 new, 100 updated)"

  Scenario: Transform handles missing fields gracefully
    Given a staging card has NULL back_content
    When transformation stage runs
    Then card should be skipped with warning
    And I should see: "Skipped 1 card with missing required fields"
    And remaining 499 cards should be transformed

  Scenario: Transform rollback on constraint violation
    Given transformation is processing 500 cards
    When card 250 violates a database constraint
    Then all 249 previous inserts should be rolled back
    And canonical table should remain in pre-transform state
    And I should see error: "Transformation failed: constraint violation"
    And detailed error message should explain which constraint

  # ============================================================================
  # Quality Analysis Stage
  # ============================================================================

  Scenario: Quality analysis grades all cards
    Given clean_atoms contains 500 cards
    And all cards have NULL quality_grade
    When quality analysis stage runs
    Then all 500 cards should be analyzed
    And quality_grade should be set for all cards
    And quality_score should be calculated
    And quality_issues should be populated
    And I should see grade distribution:
      | Grade | Count | Percentage |
      | A     | 203   | 40.6       |
      | B     | 145   | 29.0       |
      | C     | 75    | 15.0       |
      | D     | 52    | 10.4       |
      | F     | 25    | 5.0        |

  Scenario: Quality analysis sets action flags
    Given clean_atoms contains cards with quality issues
    When quality analysis stage runs
    Then needs_split flag should be set for cards with ENUMERATION_DETECTED
    And needs_rewrite flag should be set for grade D/F cards
    And is_atomic flag should be false for cards with MULTIPLE_FACTS
    And is_verbose flag should be true for cards with BACK_VERBOSE
    And I should see: "Flagged 45 for split, 77 for rewrite"

  Scenario: Quality analysis updates existing grades
    Given clean_atoms contains cards already graded with version "1.0.0"
    And analyzer has been updated to version "1.1.0"
    When quality analysis stage runs with --force
    Then all cards should be re-analyzed
    And quality_check_version should be updated to "1.1.0"
    And some grades may change due to updated thresholds

  Scenario: Quality analysis batch processing
    Given clean_atoms contains 10,000 cards
    When quality analysis stage runs
    Then cards should be processed in batches of 500
    And I should see progress:
      | Analyzed  | Status                           |
      | 500       | Analyzing quality: 500/10000     |
      | 5000      | Analyzing quality: 5000/10000    |
      | 10000     | Analyzing quality: 10000/10000   |
    And memory usage should remain stable

  # ============================================================================
  # Duplicate Detection Stage
  # ============================================================================

  Scenario: Detect exact duplicates
    Given clean_atoms contains 2 cards with identical front and back
    When duplicate detection stage runs with method "exact"
    Then duplicate group should be created linking the 2 cards
    And detection_method should be "exact"
    And similarity_score should be 1.0
    And I should see: "Found 1 duplicate group (exact match)"

  Scenario: Detect fuzzy duplicates
    Given clean_atoms contains similar cards:
      | Card ID | Front                      | Back   |
      | A-001   | What is TCP?               | Proto  |
      | A-002   | What is TCP                | Proto  |
      | A-003   | What's TCP?                | Proto  |
    When duplicate detection stage runs with method "fuzzy" and threshold 0.85
    Then 1 duplicate group should be created containing all 3 cards
    And detection_method should be "fuzzy"
    And similarity_scores should be > 0.85
    And I should see: "Found 1 duplicate group (3 cards, fuzzy match)"

  Scenario: Detect semantic duplicates (deferred to Phase 2.5)
    Given clean_atoms contains semantically similar cards:
      | Card ID | Front                                    | Back         |
      | A-001   | What is TCP?                             | Protocol     |
      | A-002   | Define Transmission Control Protocol     | TCP          |
    When duplicate detection stage runs with method "semantic"
    Then I should see warning: "Semantic detection requires embeddings (Phase 2.5)"
    And semantic detection should be skipped
    And I should fall back to fuzzy detection

  Scenario: Duplicate detection excludes resolved groups
    Given I have previously resolved a duplicate group
    When duplicate detection stage runs
    Then resolved groups should not be re-detected
    And only new duplicates should be reported
    And I should see: "Found 5 new duplicate groups (12 previously resolved)"

  Scenario: Duplicate detection with custom threshold
    Given I want stricter duplicate matching
    When I run "nls clean duplicates --threshold 0.95"
    Then only very similar cards should be flagged
    And fewer false positives should be detected
    And I should see similarity scores > 0.95 for all groups

  Scenario: Duplicate detection performance with large dataset
    Given clean_atoms contains 50,000 cards
    When duplicate detection stage runs
    Then duplicate detection should complete within 5 minutes
    And memory usage should stay below 1 GB
    And I should see: "Analyzed 50,000 cards for duplicates in 4 min 23 sec"

  # ============================================================================
  # AI Rewriting Stage
  # ============================================================================

  Scenario: Queue grade D cards for rewriting
    Given clean_atoms contains 52 grade D cards
    When AI rewriting stage runs
    Then 52 cards should be queued in review_queue
    And rewrite_type should be "improve"
    And AI prompts should include quality issues from quality_grade
    And status should be "pending"
    And I should see: "Queued 52 grade D cards for AI rewriting"

  Scenario: Queue grade F cards for splitting
    Given clean_atoms contains 25 grade F cards with ENUMERATION_DETECTED
    When AI rewriting stage runs
    Then 25 cards should be queued with rewrite_type "split"
    And AI prompts should request splitting into atomic cards
    And split_suggestions field should be populated by AI
    And I should see: "Queued 25 grade F cards for splitting"

  Scenario: AI rewriter generates improvement suggestions
    Given a grade D card has issues: ["BACK_TOO_LONG", "BACK_VERBOSE"]
    When AI rewriting processes the card
    Then suggested_front should be optimized version
    And suggested_back should be < 15 words
    And quality_improvement_estimate should be calculated
    And I should see estimated new grade: "B or C"

  Scenario: AI rewriter generates split suggestions
    Given a grade F card has ENUMERATION_DETECTED
    And back content is:
      """
      1. Physical layer
      2. Data Link layer
      3. Network layer
      """
    When AI rewriting processes the card
    Then split_suggestions should contain 3 atomic cards:
      | Split ID | Front                         | Back          |
      | 1        | What is Layer 1 of OSI?       | Physical      |
      | 2        | What is Layer 2 of OSI?       | Data Link     |
      | 3        | What is Layer 3 of OSI?       | Network       |
    And each split should have quality grade A or B

  Scenario: AI rewriter respects batch limits
    Given I have 200 grade D/F cards
    When I run "nls clean rewrite --limit 50"
    Then only 50 worst cards should be queued
    And cards should be sorted by quality_score ASC
    And I should see: "Queued 50 cards (limited from 200 candidates)"

  Scenario: AI rewriter dry-run mode
    Given I have 77 grade D/F cards
    When I run "nls clean rewrite --dry-run"
    Then AI should not be called
    And no records should be added to review_queue
    And I should see preview:
      | Grade | Count | Would Queue |
      | D     | 52    | 52          |
      | F     | 25    | 25          |
    And estimated AI API costs should be shown

  Scenario: AI rewriter error handling
    Given Gemini API is unavailable
    When AI rewriting stage runs
    Then stage should fail gracefully
    And cards should remain in queue with status "error"
    And I should see error: "AI API unavailable"
    And pipeline should continue with remaining stages

  # ============================================================================
  # Review Queue Workflow
  # ============================================================================

  Scenario: List pending reviews
    Given review_queue contains 77 pending items
    When I run "nls review list"
    Then I should see table of pending reviews:
      | ID      | Source Atom | Type    | Original Quality | Estimated New |
      | abc-123 | NET-042     | improve | D (50)           | B (78)        |
      | abc-124 | NET-089     | split   | F (25)           | A (95)        |
      | ...     | ...         | ...     | ...              | ...           |
    And list should be sorted by quality_improvement_estimate DESC

  Scenario: View review details
    Given review_queue contains item "abc-123"
    When I run "nls review show abc-123"
    Then I should see:
      - Original front/back
      - Suggested front/back
      - Quality issues list
      - Quality improvement estimate
      - AI model used
      - Created timestamp
    And I should be prompted: "Approve? (y/n/edit)"

  Scenario: Approve review and apply changes
    Given review_queue contains approved rewrite for card "NET-042"
    When I run "nls review approve abc-123"
    Then clean_atoms card NET-042 should be updated:
      - front_content = suggested_front
      - back_content = suggested_back
    And quality analysis should re-run for updated card
    And new quality_grade should be set
    And review_queue status should be "approved"
    And reviewed_at timestamp should be set
    And I should see: "Approved rewrite abc-123. Card NET-042 updated. New grade: B"

  Scenario: Reject review without applying changes
    Given review_queue contains item "abc-123"
    When I run "nls review reject abc-123 --reason 'Too verbose'"
    Then clean_atoms card should remain unchanged
    And review_queue status should be "rejected"
    And reviewed_at timestamp should be set
    And rejection reason should be logged
    And I should see: "Rejected rewrite abc-123. Original card preserved."

  Scenario: Edit review before approving
    Given review_queue contains item "abc-123"
    When I run "nls review edit abc-123"
    Then I should be prompted to edit suggested_front and suggested_back
    And I can modify the AI suggestions
    When I save changes
    Then review_queue should be updated with my edits
    And I can then approve or reject
    And I should see: "Edited review abc-123. Review again to approve."

  Scenario: Batch approve multiple reviews
    Given review_queue contains 20 high-quality rewrites
    When I run "nls review approve --min-improvement 25 --auto-approve"
    Then all reviews with improvement > 25% should be approved automatically
    And corresponding clean_atoms cards should be updated
    And I should see: "Auto-approved 20 reviews (avg improvement: 32%)"

  Scenario: Apply split suggestions
    Given review_queue contains split for card "NET-042" with 3 splits
    When I run "nls review approve abc-123"
    Then original card NET-042 should be marked as superseded
    And 3 new atomic cards should be created in clean_atoms
    And each new card should have source "ai_generated"
    And each new card should have parent_atom_id = NET-042
    And I should see: "Applied split abc-123. Created 3 atomic cards."

  # ============================================================================
  # Pipeline Error Handling
  # ============================================================================

  Scenario: Pipeline continues after non-fatal errors
    Given quality analysis fails for 5 cards due to malformed data
    When pipeline runs
    Then 5 cards should be skipped with warnings
    And remaining 495 cards should be processed
    And pipeline should complete with status "completed_with_warnings"
    And I should see: "Completed with 5 warnings (see logs)"

  Scenario: Pipeline stops on fatal errors
    Given database connection is lost during transformation
    When pipeline runs
    Then pipeline should stop at transformation stage
    And no subsequent stages should run
    And status should be "failed"
    And I should see error: "Fatal error: Database connection lost"

  Scenario: Pipeline rollback on transaction failure
    Given transformation succeeds
    And quality analysis succeeds
    But duplicate detection causes deadlock
    When pipeline runs
    Then all changes should be rolled back
    And canonical tables should remain in pre-pipeline state
    And I should see: "Pipeline failed. All changes rolled back."

  Scenario: Pipeline recovery after partial failure
    Given pipeline failed at duplicate detection stage
    When I run "nls clean run --resume"
    Then transformation and quality analysis should be skipped
    And pipeline should resume from duplicate detection
    And I should see: "Resuming from stage 3: Duplicate Detection"

  # ============================================================================
  # Pipeline Performance and Monitoring
  # ============================================================================

  Scenario: Pipeline progress reporting
    Given I have 10,000 cards to clean
    When I run "nls clean run"
    Then I should see real-time progress:
      | Stage              | Progress                     |
      | Transformation     | Transforming: 5000/10000     |
      | Quality Analysis   | Analyzing: 2500/10000        |
      | Duplicate Detection| Checking: 7500/10000         |
    And overall progress percentage should be displayed
    And estimated time remaining should be shown

  Scenario: Pipeline generates detailed summary report
    When pipeline completes
    Then I should see summary report:
      ```
      ================================================================================
      Cleaning Pipeline Summary
      ================================================================================
      Status: Completed successfully
      Total time: 3 minutes 45 seconds

      Stage 1: Transformation
        - Cards transformed: 500
        - Time: 12 seconds

      Stage 2: Quality Analysis
        - Cards analyzed: 500
        - Grade A: 203 (40.6%)
        - Grade B: 145 (29.0%)
        - Grade C: 75 (15.0%)
        - Grade D: 52 (10.4%)
        - Grade F: 25 (5.0%)
        - Time: 98 seconds

      Stage 3: Duplicate Detection
        - Duplicate groups: 12
        - Cards affected: 28
        - Time: 45 seconds

      Actions Required:
        - Review 12 duplicate groups
        - Consider rewriting 77 grade D/F cards

      ================================================================================
      ```

  Scenario: Pipeline with verbose logging
    When I run "nls clean run --verbose"
    Then I should see detailed logs for each stage:
      - SQL queries executed
      - Card IDs processed
      - Quality issues detected per card
      - Duplicate match details
      - Timing for each operation

  Scenario: Pipeline API endpoint
    When I send "POST /api/clean/run" with body:
      """
      {
        "enable_rewrite": true,
        "min_grade": "D",
        "dry_run": false
      }
      """
    Then pipeline should start asynchronously
    And I should receive response with pipeline_id
    And I can check status with "GET /api/clean/status/{pipeline_id}"

  Scenario: Pipeline metrics collection
    Given I have run pipeline 10 times
    When I request "GET /api/clean/metrics"
    Then I should see aggregate metrics:
      | Metric                     | Value      |
      | Total runs                 | 10         |
      | Success rate               | 90%        |
      | Average cards processed    | 523        |
      | Average time               | 3.8 min    |
      | Average duplicates found   | 14         |
      | Total cards cleaned        | 5,230      |
