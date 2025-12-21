# Feature: Prerequisite Management with Soft/Hard Gating
#
# Prerequisite Types:
#   - soft: Warning shown but access allowed
#   - hard: Access blocked until mastery threshold met
#
# Mastery Thresholds (from right-learning research):
#   - foundation: 0.40 (basic exposure sufficient)
#   - integration: 0.65 (solid understanding required) - DEFAULT
#   - mastery: 0.85 (expert level required)
#
# Prerequisite Origins:
#   - explicit: Manually defined by instructor/admin
#   - tag: Parsed from Anki tag (tag:prereq:domain:topic:subtopic)
#   - inferred: AI-suggested and accepted (from semantic similarity)
#   - imported: From external source (CSV, Notion)
#
# See: enhanced-cognition/right-learning/features/prerequisites.feature for full scenarios

Feature: Prerequisite Management with Soft/Hard Gating

  As a learner, I want to understand what concepts I need to master
  before advancing to complex topics, so I build solid foundations.

  As an instructor, I want to define prerequisite relationships
  with appropriate gating, so learners follow structured learning paths.

  As the system, I want to prevent circular dependencies and detect gaps,
  so learning pathways remain valid and learners get appropriate guidance.

  Background:
    Given a PostgreSQL database with clean_concepts and clean_atoms
    And test concepts with the following hierarchy:
      | Concept                 | Domain      | Prerequisites       | Mastery Type |
      | TCP Fundamentals        | Networking  | None                | foundation   |
      | IP Addressing           | Networking  | None                | foundation   |
      | TCP Handshake           | Networking  | TCP Fundamentals    | integration  |
      | HTTP Protocol           | Networking  | TCP Handshake       | integration  |
      | HTTPS/TLS               | Networking  | HTTP Protocol       | mastery      |
      | REST API Design         | Development | HTTP Protocol       | integration  |

  # ========================================
  # SOFT GATING SCENARIOS
  # ========================================

  Scenario: Create soft-gating prerequisite (warning shown, access allowed)
    Given concept "TCP Handshake" exists
    And concept "TCP Fundamentals" exists
    When I create a prerequisite:
      | source_concept | TCP Handshake      |
      | target_concept | TCP Fundamentals   |
      | gating_type    | soft               |
      | mastery_threshold | 0.65            |
    Then the prerequisite is created successfully
    And gating_type should be "soft"
    And status should be "active"

    When user with mastery 0.50 on "TCP Fundamentals" attempts "TCP Handshake"
    Then access status should be "warning"
    And can_access should be true
    And warnings should include "Recommended prerequisite not met"
    And message should include "have 50%, need 65%"

  Scenario: Soft-gated prerequisite allows access with recommendation
    Given soft prerequisite: "HTTP Protocol" requires "TCP Handshake" at 0.65
    And user has mastery 0.55 on "TCP Handshake" (below threshold)
    When user requests access to "HTTP Protocol" flashcards
    Then access is allowed with warning:
      """
      Recommended prerequisite not met: TCP Handshake (have 55%, need 65%)
      """
    And user can proceed to study "HTTP Protocol"
    And system logs the warning for analytics

  # ========================================
  # HARD GATING SCENARIOS
  # ========================================

  Scenario: Create hard-gating prerequisite (access blocked)
    Given concept "HTTPS/TLS" exists
    And concept "HTTP Protocol" exists
    When I create a prerequisite:
      | source_concept    | HTTPS/TLS        |
      | target_concept    | HTTP Protocol    |
      | gating_type       | hard             |
      | mastery_type      | mastery          |
      | mastery_threshold | 0.85             |
    Then the prerequisite is created successfully
    And gating_type should be "hard"
    And mastery_threshold should be 0.85

  Scenario: Hard-gated prerequisite blocks access until mastery
    Given hard prerequisite: "HTTPS/TLS" requires "HTTP Protocol" at 0.85
    And user has mastery 0.70 on "HTTP Protocol"
    When user attempts to access "HTTPS/TLS" quiz
    Then access status should be "blocked"
    And can_access should be false
    And message should be:
      """
      Access blocked: Must master 'HTTP Protocol' (need 85%, have 70%)
      """
    And blocking_prerequisites should contain:
      | target_concept_name | HTTP Protocol |
      | required_mastery    | 0.85          |
      | current_mastery     | 0.70          |
      | mastery_gap         | 0.15          |

    When user improves mastery to 0.86 on "HTTP Protocol"
    And user attempts to access "HTTPS/TLS" quiz again
    Then access status should be "allowed"
    And can_access should be true
    And message should be "All prerequisites met"

  # ========================================
  # ANKI TAG PARSING
  # ========================================

  Scenario: Parse prerequisite from Anki tag format
    Given the tag "tag:prereq:networking:tcp:handshake"
    When I parse the prerequisite tag
    Then parsed result should have:
      | domain   | networking |
      | topic    | tcp        |
      | subtopic | handshake  |
      | full_path| networking:tcp:handshake |

  Scenario: Parse multiple prerequisite tags from Anki card
    Given an Anki card with tags:
      | tag:prereq:networking:tcp:fundamentals |
      | tag:prereq:networking:ip:addressing    |
      | study:ccna                             |
      | deck:network_basics                    |
    When I parse all prerequisite tags
    Then I should get 2 parsed prerequisites
    And non-prerequisite tags should be ignored

  Scenario: Sync prerequisites from Anki tags to database
    Given atom "NET-042" has Anki tags:
      | tag:prereq:networking:tcp:fundamentals |
    And concept "TCP Fundamentals" exists with domain "networking"
    When I sync prerequisites from Anki tags for atom "NET-042"
    Then an explicit prerequisite is created:
      | source_atom_id    | NET-042              |
      | target_concept_id | TCP Fundamentals     |
      | origin            | tag                  |
      | anki_tag          | tag:prereq:networking:tcp:fundamentals |
      | gating_type       | soft                 |

  Scenario: Export prerequisite to Anki tag format
    Given explicit prerequisite linking atom to "TCP Fundamentals"
    And "TCP Fundamentals" has domain "networking"
    When I export the prerequisite to Anki tag
    Then the result should be "tag:prereq:networking:tcp_fundamentals"

  # ========================================
  # CIRCULAR DEPENDENCY DETECTION
  # ========================================

  Scenario: Detect circular dependency (A -> B -> C -> A)
    Given existing prerequisites:
      | Source      | Target         |
      | Concept A   | Concept B      |
      | Concept B   | Concept C      |
    When I attempt to create prerequisite:
      | source_concept | Concept C |
      | target_concept | Concept A |
      | gating_type    | hard      |
    Then creation should fail with error:
      """
      Adding this prerequisite would create a circular dependency
      """

  Scenario: Detect all circular dependencies in graph
    Given a prerequisite graph with circular dependencies
    When I run circular dependency detection
    Then I should receive a list of CircularDependencyError objects
    And each error should include:
      | chain         | [UUID array of concepts in cycle] |
      | concept_names | [Human-readable names]            |
      | message       | Circular dependency: A -> B -> C -> A |

  Scenario: Valid prerequisite chain is allowed
    Given existing prerequisites:
      | Source          | Target           |
      | TCP Handshake   | TCP Fundamentals |
      | HTTP Protocol   | TCP Handshake    |
    When I create prerequisite:
      | source_concept | HTTPS/TLS     |
      | target_concept | HTTP Protocol |
      | gating_type    | hard          |
    Then the prerequisite is created successfully
    And no circular dependency error occurs

  # ========================================
  # PREREQUISITE CHAIN RESOLUTION
  # ========================================

  Scenario: Resolve multi-level prerequisite chain
    Given prerequisite chain:
      | Level | Concept       | Prerequisite     | Mastery Type |
      | 1     | HTTP Protocol | TCP Handshake    | integration  |
      | 2     | TCP Handshake | TCP Fundamentals | integration  |
      | 3     | HTTPS/TLS     | HTTP Protocol    | mastery      |
    When I request prerequisite chain for "HTTPS/TLS"
    Then I should receive nodes in order of depth:
      | depth | concept_name     | mastery_threshold |
      | 1     | HTTP Protocol    | 0.85              |
      | 2     | TCP Handshake    | 0.65              |
      | 3     | TCP Fundamentals | 0.65              |

  Scenario: Prerequisite roadmap for user with partial mastery
    Given user has mastery:
      | Concept          | Mastery |
      | TCP Fundamentals | 0.90    |
      | TCP Handshake    | 0.40    |
      | HTTP Protocol    | 0.00    |
    And prerequisite chain for "HTTPS/TLS"
    When I evaluate access for user to "HTTPS/TLS"
    Then the roadmap should show:
      """
      ✓ TCP Fundamentals: 90% (met)
      ✗ TCP Handshake: 40% (need 65%)
      🔒 HTTP Protocol: 0% (need 65%)
      🔒 HTTPS/TLS: Blocked
      """

  # ========================================
  # PREREQUISITE WAIVERS
  # ========================================

  Scenario: Grant instructor waiver for prior knowledge
    Given hard prerequisite: "REST API Design" requires "HTTP Protocol" at 0.65
    And user has mastery 0.40 on "HTTP Protocol"
    When instructor grants waiver:
      | prerequisite_id | (REST -> HTTP prereq)  |
      | waiver_type     | instructor             |
      | granted_by      | instructor@example.com |
      | evidence_type   | assessment             |
      | notes           | Student has web dev background |
    Then waiver is created successfully
    And when user attempts "REST API Design"
    Then access status should be "waived"
    And can_access should be true
    And waiver_applied should be true

  Scenario: Grant challenge waiver for high performer
    Given hard prerequisite at 0.85 threshold
    And user performs at 95% on prerequisite concept
    When system evaluates challenge eligibility
    Then eligibility should be true
    When system grants challenge waiver:
      | waiver_type   | challenge   |
      | score         | 0.95        |
      | granted_by    | system      |
    Then waiver is created with evidence:
      """
      {
        "score": 0.95,
        "challenge_passed": true
      }
      """

  Scenario: Waiver expires after set date
    Given a waiver with expires_at = "2025-12-01"
    When current date is "2025-12-02"
    And I validate the waiver
    Then is_active should be false
    And is_expired should be true
    And access evaluation should ignore expired waiver

  # ========================================
  # MASTERY THRESHOLDS BY TYPE
  # ========================================

  Scenario: Foundation threshold (0.40) for basic prerequisites
    When I get mastery threshold for type "foundation"
    Then threshold should be 0.40

  Scenario: Integration threshold (0.65) for standard prerequisites
    When I get mastery threshold for type "integration"
    Then threshold should be 0.65

  Scenario: Mastery threshold (0.85) for advanced prerequisites
    When I get mastery threshold for type "mastery"
    Then threshold should be 0.85

  Scenario: Prerequisite uses correct threshold based on mastery_type
    Given prerequisite with mastery_type "foundation"
    When I retrieve the default threshold
    Then it should return 0.40

  # ========================================
  # UPGRADE INFERRED TO EXPLICIT
  # ========================================

  Scenario: Upgrade AI-inferred prerequisite to explicit
    Given inferred prerequisite:
      | source_atom_id    | atom-123       |
      | target_concept_id | concept-456    |
      | similarity_score  | 0.82           |
      | confidence        | high           |
      | status            | suggested      |
    When I upgrade the inferred prerequisite:
      | gating_type | soft                    |
      | approved_by | reviewer@example.com    |
    Then an explicit prerequisite is created:
      | origin      | inferred   |
      | gating_type | soft       |
      | approved_by | reviewer@example.com |
      | notes       | Upgraded from inferred (similarity: 0.82) |
    And the inferred prerequisite status becomes "applied"
    And reviewed_at is set

  # ========================================
  # API ENDPOINTS FOR RIGHT-LEARNING
  # ========================================

  Scenario: Check prerequisites via API for right-learning
    Given prerequisites exist for concept "HTTPS/TLS"
    And user mastery data is provided:
      | HTTP Protocol | 0.75 |
    When I call "GET /api/prerequisites/check/{concept_id}"
    Then response should include:
      | status              | warning or blocked |
      | can_access          | boolean            |
      | blocking_prerequisites | list of blockers |
      | mastery_gap         | map of gaps        |

  Scenario: Get prerequisite chain via API
    Given prerequisite chain exists for "HTTPS/TLS"
    When I call "GET /api/prerequisites/chain/{concept_id}"
    Then response should include ordered chain:
      | depth | concept_name  | gating_type | mastery_threshold |
      | 1     | HTTP Protocol | hard        | 0.85              |
      | 2     | TCP Handshake | soft        | 0.65              |

  # ========================================
  # PREREQUISITE BLOCKING QUIZ ACCESS
  # ========================================

  Scenario: Quiz blocked by prerequisite
    Given quiz "HTTPS Assessment" has requires_prerequisites = true
    And quiz is linked to concept "HTTPS/TLS"
    And hard prerequisite: "HTTPS/TLS" requires "HTTP Protocol" at 0.85
    And user has mastery 0.60 on "HTTP Protocol"
    When user attempts to start quiz "HTTPS Assessment"
    Then quiz access is denied
    And error code should be "PREREQUISITE_NOT_MET"
    And message should include:
      """
      Must master HTTP Protocol (0.85) before attempting this quiz
      """
    And suggestion should be "Master the prerequisite first"

  # ========================================
  # BATCH OPERATIONS
  # ========================================

  Scenario: Batch prerequisite import from CSV
    Given CSV file with prerequisites:
      """
      source_concept,target_concept,gating_type,mastery_threshold
      TCP Handshake,TCP Fundamentals,soft,0.65
      HTTP Protocol,TCP Handshake,soft,0.65
      HTTPS/TLS,HTTP Protocol,hard,0.85
      """
    When I import prerequisites from CSV
    Then 3 prerequisites should be created
    And circular dependency check should pass
    And summary should show "3 created, 0 conflicts"

  Scenario: Validate prerequisites before batch import
    Given CSV with circular dependency:
      """
      source_concept,target_concept,gating_type
      A,B,hard
      B,C,hard
      C,A,hard
      """
    When I validate the batch
    Then validation should fail
    And error should indicate circular dependency in row 3
