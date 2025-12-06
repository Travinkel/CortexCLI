Feature: Notion Database Synchronization
  As a learner managing content in Notion
  I want to sync my Notion databases to PostgreSQL
  So that I can have a clean, canonical source of learning content

  Background:
    Given Notion is accessible with valid API credentials
    And 18 Notion databases are configured in settings:
      | Database Type      | Purpose                           |
      | Flashcards         | Learning atoms (questions/answers)|
      | Concepts           | L2 atomic knowledge units         |
      | Concept Clusters   | L1 thematic groupings             |
      | Concept Areas      | L0 top-level domains              |
      | Programs           | Degree/certification paths        |
      | Tracks             | Course sequences                  |
      | Modules            | Week/chapter units                |
      | Activities         | Practice sessions                 |
      | Sessions           | Activity instances                |
      | Quizzes            | Assessment items                  |
      | Critical Skills    | Key competencies                  |
      | Resources          | Learning materials                |
      | Mental Models      | Conceptual frameworks             |
      | Evidence           | Research backing                  |
      | Brain Regions      | Neuroscience mapping              |
      | Training Protocols | Practice methods                  |
      | Practice Logs      | Session records                   |
      | Assessments        | Evaluation results                |
    And PostgreSQL staging tables exist for all 18 databases

  Scenario: Full sync of all databases
    Given I have content in all 18 Notion databases
    When I run "nls sync notion --full"
    Then all 18 databases should be queried
    And all pages should be fetched with pagination
    And all records should be written to staging tables with JSONB properties
    And I should see a summary:
      | Database Type      | Created | Updated | Total |
      | Flashcards         | 150     | 50      | 200   |
      | Concepts           | 80      | 20      | 100   |
      | Concept Clusters   | 15      | 5       | 20    |
      | ...                | ...     | ...     | ...   |
    And sync run should be logged with "completed" status
    And total sync time should be reported

  Scenario: Incremental sync using last_edited_time
    Given I have previously synced all databases
    And last sync was at "2025-12-01T10:00:00Z"
    And some Notion pages have been edited since last sync
    When I run "nls sync notion --incremental"
    Then only pages with last_edited_time > "2025-12-01T10:00:00Z" should be fetched
    And sync should be faster than full sync
    And I should see: "Fetched 45 updated pages (skipped 2,500 unchanged)"
    And sync checkpoint should be updated to current timestamp

  Scenario: Incremental sync is default behavior
    Given I have previously synced databases
    When I run "nls sync notion"
    Then incremental sync should be performed by default
    And only changed pages since last successful sync should be fetched

  Scenario: Database-specific sync
    Given I want to sync only flashcards
    When I run "nls sync notion --database flashcards"
    Then only flashcards database should be queried
    And other 17 databases should be skipped
    And I should see: "Synced 1 database: Flashcards (150 created, 50 updated)"

  Scenario: Multiple database sync
    Given I want to sync flashcards and concepts
    When I run "nls sync notion --database flashcards,concepts"
    Then only flashcards and concepts databases should be synced
    And 16 other databases should be skipped
    And summary should show results for both databases

  Scenario: Dry-run mode preview
    When I run "nls sync notion --dry-run"
    Then Notion API should be queried for page counts
    But no records should be written to staging tables
    And I should see preview:
      | Database Type      | Pages to Sync | Estimate |
      | Flashcards         | 200           | ~5 sec   |
      | Concepts           | 100           | ~3 sec   |
      | ...                | ...           | ...      |
    And total estimated time should be shown
    And no sync run should be logged

  Scenario: Progress reporting for large syncs
    Given I have 5,000 flashcards in Notion
    When I run "nls sync notion --database flashcards"
    Then I should see progress updates:
      | Fetched | Status                         |
      | 100     | Syncing flashcards: 100/5000   |
      | 500     | Syncing flashcards: 500/5000   |
      | 2500    | Syncing flashcards: 2500/5000  |
      | 5000    | Syncing flashcards: 5000/5000  |
    And progress should be updated in real-time
    And final summary should show total time and throughput

  Scenario: Handle deleted Notion pages
    Given I have previously synced a page with ID "abc-123"
    And the page has been deleted from Notion
    When I run "nls sync notion --incremental"
    Then the page should no longer appear in query results
    And existing record in staging table should be marked as deleted
    Or existing record should be removed if not referenced elsewhere
    And I should see: "Removed 3 deleted pages"

  Scenario: Sync with rate limiting
    Given Notion API rate limit is 3 requests per second
    When I run "nls sync notion --full"
    Then requests should be automatically throttled to 3 req/sec
    And I should not receive 429 (Too Many Requests) errors
    And sync should complete successfully with delays between requests

  Scenario: Retry logic with exponential backoff
    Given Notion API returns 503 (Service Unavailable) on 2nd request
    When I run "nls sync notion"
    Then first request should succeed
    And second request should fail with 503
    And third request should be retried after 1 second delay
    And fourth request should be retried after 2 seconds if still failing
    And sync should eventually succeed or fail after 3 retries

  Scenario: Handle network timeout gracefully
    Given Notion API is slow to respond
    When I run "nls sync notion" with 30 second timeout
    And a request takes longer than 30 seconds
    Then the request should timeout
    And I should see error: "Request timeout after 30s"
    And sync run should be marked as "failed"
    And partial data should not be committed (transaction rollback)

  Scenario: Transaction rollback on error
    Given I am syncing flashcards database
    When sync succeeds for 100 pages
    But fails on page 101 due to database constraint violation
    Then all 100 previous inserts should be rolled back
    And staging table should remain in pre-sync state
    And sync run should be marked as "failed"
    And error message should explain the constraint violation

  Scenario: Get sync status from last run
    Given I have completed a sync at "2025-12-02T10:30:00Z"
    When I request "GET /api/sync/status"
    Then I should see:
      | Field              | Value                    |
      | last_sync_time     | 2025-12-02T10:30:00Z     |
      | status             | completed                |
      | records_created    | 250                      |
      | records_updated    | 75                       |
      | duration_seconds   | 45                       |
      | error_message      | null                     |

  Scenario: Get sync status when no sync has run
    Given no sync has been performed yet
    When I request "GET /api/sync/status"
    Then I should see:
      | Field              | Value |
      | last_sync_time     | null  |
      | status             | never_run |
      | message            | No sync has been performed yet |

  Scenario: Get sync history
    Given I have performed 5 syncs over the past week
    When I request "GET /api/sync/history?limit=5"
    Then I should receive 5 most recent sync runs
    And each entry should include:
      | Field              |
      | id                 |
      | started_at         |
      | completed_at       |
      | status             |
      | records_created    |
      | records_updated    |
      | duration_seconds   |
      | error_message      |
    And entries should be ordered by started_at DESC

  Scenario: Filter sync history by status
    Given I have had 3 successful syncs and 2 failed syncs
    When I request "GET /api/sync/history?status=failed"
    Then I should receive only the 2 failed sync runs
    And error messages should be included

  Scenario: Filter sync history by date range
    Given I have syncs from November and December
    When I request "GET /api/sync/history?start_date=2025-12-01&end_date=2025-12-31"
    Then I should receive only syncs from December 2025

  Scenario: Sync with PROTECT_NOTION=true prevents writes
    Given PROTECT_NOTION setting is enabled (true)
    When I attempt to run any sync command
    Then sync should proceed normally (reads are allowed)
    And I should not see any write-related warnings
    But if I try to update a Notion page via API
    Then I should see error: "Write protection enabled"

  Scenario: Parallel sync for multiple databases
    Given I have 18 databases to sync
    When I run "nls sync notion --full --parallel"
    Then multiple databases should be synced concurrently
    And I should see progress for multiple databases simultaneously
    And total sync time should be less than sequential sync
    And results should be merged correctly

  Scenario: Sync checkpoint tracking per database
    Given I have synced flashcards at "2025-12-01T10:00:00Z"
    And I have synced concepts at "2025-12-01T15:00:00Z"
    When I request sync checkpoints
    Then I should see:
      | Database Type | Last Sync Time       | Last Success         | Consecutive Failures |
      | Flashcards    | 2025-12-01T10:00:00Z | 2025-12-01T10:00:00Z | 0                    |
      | Concepts      | 2025-12-01T15:00:00Z | 2025-12-01T15:00:00Z | 0                    |
      | ...           | null                 | null                 | 0                    |

  Scenario: Consecutive failure tracking
    Given flashcards sync has failed 2 times in a row
    When I run "nls sync notion --database flashcards"
    And it fails again
    Then consecutive_failures should be incremented to 3
    And I should see warning: "Flashcards sync has failed 3 consecutive times"
    And alert should suggest checking Notion API credentials or database schema

  Scenario: Reset consecutive failures on success
    Given flashcards sync has failed 2 times
    When I run "nls sync notion --database flashcards"
    And it succeeds
    Then consecutive_failures should be reset to 0
    And last_success timestamp should be updated

  Scenario: API endpoint for triggering sync
    When I send "POST /api/sync/notion" with body:
      """
      {
        "incremental": true,
        "databases": ["flashcards", "concepts"],
        "dry_run": false
      }
      """
    Then sync should start asynchronously
    And I should receive response:
      """
      {
        "success": true,
        "message": "Sync started",
        "sync_id": "abc-123-def-456"
      }
      """
    And I can check status with sync_id

  Scenario: Get running sync status
    Given a sync is currently in progress with ID "abc-123"
    When I request "GET /api/sync/status/abc-123"
    Then I should see:
      | Field              | Value              |
      | sync_id            | abc-123            |
      | status             | running            |
      | started_at         | 2025-12-02T10:30:00Z |
      | progress_percent   | 45                 |
      | current_database   | flashcards         |
      | records_processed  | 2250/5000          |

  Scenario: Cancel running sync
    Given a sync is currently in progress with ID "abc-123"
    When I send "POST /api/sync/abc-123/cancel"
    Then the sync should be gracefully terminated
    And current transaction should be rolled back
    And sync run should be marked as "cancelled"
    And I should see: "Sync abc-123 cancelled successfully"

  Scenario: Sync fails if API credentials are missing
    Given NOTION_API_KEY is not set
    When I run "nls sync notion"
    Then I should see error: "Notion API credentials missing"
    And helpful message should say: "Set NOTION_API_KEY in .env file"
    And command should exit with code 1

  Scenario: Sync fails if database ID is not configured
    Given flashcards_db_id is not set in config
    When I run "nls sync notion --database flashcards"
    Then I should see error: "Flashcards database ID not configured"
    And helpful message should say: "Set flashcards_db_id in config.py"
    And command should exit with code 1

  Scenario: Sync handles JSONB property storage
    Given a Notion page has properties:
      | Property Name | Type         | Value                |
      | Front         | title        | What is TCP?         |
      | Back          | rich_text    | Transmission Control |
      | Tags          | multi_select | ["networking", "tcp"]|
      | Status        | select       | Active               |
    When I sync the page
    Then staging table should have:
      | Column              | Value                                           |
      | notion_page_id      | page-id-123                                     |
      | properties          | {JSON object with all Notion properties}        |
      | notion_last_edited  | 2025-12-02T10:30:00Z                            |
      | notion_created      | 2025-11-01T08:00:00Z                            |
    And properties JSONB should be queryable with JSON operators

  Scenario: Sync large databases with pagination
    Given flashcards database has 3,500 pages
    And Notion API returns 100 pages per request
    When I run "nls sync notion --database flashcards"
    Then sync should make 35 API requests
    And all 3,500 pages should be fetched
    And pagination cursors should be handled correctly
    And I should see: "Fetched 3,500 flashcards in 35 batches"

  Scenario: Estimate sync duration before running
    When I run "nls sync notion --estimate"
    Then Notion API should be queried for page counts only
    And estimated duration should be calculated as:
      | Database Type | Pages | Estimate   |
      | Flashcards    | 5000  | ~120 sec   |
      | Concepts      | 1000  | ~30 sec    |
      | Total         | 10000 | ~5 minutes |
    And no actual sync should be performed

  Scenario: Sync with verbose logging
    When I run "nls sync notion --verbose"
    Then I should see detailed logs:
      - Each API request URL and parameters
      - Response sizes and pagination info
      - Each record being inserted/updated
      - Database transaction boundaries
      - Timing for each operation

  Scenario: Sync with quiet mode
    When I run "nls sync notion --quiet"
    Then only errors and final summary should be displayed
    And progress updates should be suppressed
    And the output should be minimal for scripting

  Scenario: Sync creates audit trail
    When I run "nls sync notion"
    Then a sync_run record should be created with:
      | Field            | Value                    |
      | id               | UUID                     |
      | started_at       | timestamp                |
      | completed_at     | timestamp                |
      | status           | completed                |
      | records_created  | count                    |
      | records_updated  | count                    |
      | error_message    | null                     |
      | incremental      | true/false               |
    And sync_checkpoints table should be updated per database

  Scenario: Query audit trail for debugging
    Given I have a failed sync at "2025-12-02T10:30:00Z"
    When I request "GET /api/sync/runs?status=failed&limit=1"
    Then I should see the failed sync run
    And error_message should explain what went wrong
    And I can use this information to debug the issue
