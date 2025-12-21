# Learning Atom Type Taxonomy

## Overview

This document catalogs all 100+ learning atom types supported by Cortex-CLI, organized by cognitive subsystem and classified using modern learning science frameworks.

## Classification System

### ICAP Framework (Chi & Wylie, 2014)

Replaces Bloom's Taxonomy with behaviorally-measurable engagement modes:

- **Interactive**: Co-creates knowledge with system (highest retention)
- **Constructive**: Generates output beyond presented material
- **Active**: Manipulates content without adding new information
- **Passive**: Receives information (lowest retention)

### Element Interactivity (Cognitive Load Theory)

Measures intrinsic complexity:

- **Low (0.0-0.3)**: Elements learned in isolation
- **Medium (0.4-0.7)**: Some element interaction required
- **High (0.8-1.0)**: Multiple elements must be held simultaneously in working memory

### Knowledge Dimension (Krathwohl, 2002)

- **Factual**: Basic facts, terminology
- **Conceptual**: Relationships, principles
- **Procedural**: How-to knowledge, algorithms
- **Metacognitive**: Self-awareness, strategies

## Database Schema Mapping

Each atom type maps to database fields:

```sql
-- src/db/migrations/030_skill_graph.sql (updated)
CREATE TABLE skills (
    -- ... existing fields ...

    -- ICAP Framework level (Chi, 2014)
    engagement_mode VARCHAR(20) CHECK (
        engagement_mode IN ('passive', 'active', 'constructive', 'interactive')
    ),

    -- Cognitive Load Theory: Element interaction complexity
    element_interactivity NUMERIC(3,2) CHECK (
        element_interactivity BETWEEN 0.0 AND 1.0
    ),

    -- Knowledge type (Krathwohl, 2002)
    knowledge_dimension VARCHAR(20) CHECK (
        knowledge_dimension IN ('factual', 'conceptual', 'procedural', 'metacognitive')
    )
);
```

---

## I. Discrimination & Perception (10 types)

**Cognitive System:** Visual cortex, auditory cortex, pattern matching

### 1. visual_hotspot

**Description:** Click specific region on diagram/image

**ICAP:** Active
**Element Interactivity:** 0.2 (low)
**Knowledge:** Factual

**Example:** "Click the Layer 3 header in this packet diagram"

**Grading Logic:**
```json
{
  "type": "coordinate_match",
  "hotspots": [
    {"x": 120, "y": 45, "radius": 15, "correct": true},
    {"x": 200, "y": 45, "radius": 15, "correct": false}
  ],
  "tolerance_px": 10
}
```

### 2. visual_search

**Description:** Find all instances of target pattern in high-resolution image

**ICAP:** Active
**Element Interactivity:** 0.4 (medium)
**Knowledge:** Procedural

**Example:** "Find all syntax errors in this code screenshot"

**Grading Logic:** Count of correct identifications vs false positives

### 3. audio_discrimination

**Description:** Identify specific audio characteristics

**ICAP:** Active
**Element Interactivity:** 0.3 (low-medium)
**Knowledge:** Factual

**Example:** "Which network protocol produces this packet timing pattern?"

### 4. pitch_matching

**Description:** Reproduce heard tone (music/language learning)

**ICAP:** Constructive
**Element Interactivity:** 0.2 (low)
**Knowledge:** Procedural

**Example:** "Repeat the IP address pronunciation"

### 5. color_grading

**Description:** Adjust RGB sliders to match target color

**ICAP:** Active
**Element Interactivity:** 0.5 (medium)
**Knowledge:** Conceptual

**Example:** "Adjust subnetting visualization to show /24 network"

### 6. 3d_rotation

**Description:** Rotate 3D object to match target view

**ICAP:** Active
**Element Interactivity:** 0.6 (medium-high)
**Knowledge:** Conceptual

**Example:** "Rotate network topology to show switch-router connections"

### 7. waveform_alignment

**Description:** Adjust phase/frequency to cancel noise

**ICAP:** Active
**Element Interactivity:** 0.7 (high)
**Knowledge:** Procedural

**Example:** "Align clock signals to eliminate jitter"

### 8. reaction_time_check

**Description:** Press key when stimulus changes (cognitive fatigue probe)

**ICAP:** Active
**Element Interactivity:** 0.1 (very low)
**Knowledge:** Metacognitive

**Example:** "Press spacebar when port state changes to UP"

### 9. fuzzy_pattern_match

**Description:** Classify graph/chart pattern

**ICAP:** Active
**Element Interactivity:** 0.4 (medium)
**Knowledge:** Conceptual

**Example:** "Does this bandwidth graph show linear or exponential growth?"

### 10. error_highlighting

**Description:** Mark all errors in text block

**ICAP:** Active
**Element Interactivity:** 0.5 (medium)
**Knowledge:** Procedural

**Example:** "Highlight all ACL syntax errors"

---

## II. Declarative Memory (12 types)

**Cognitive System:** Hippocampus (fact storage)

### 11. flashcard

**Description:** Term ↔ Definition retrieval

**ICAP:** Active (recall mode), Passive (recognition mode)
**Element Interactivity:** 0.1 (very low)
**Knowledge:** Factual

**Implementation:** Already implemented in `src/cortex/atoms/flashcard.py`

### 12. reverse_flashcard

**Description:** Definition ↔ Term (harder than standard)

**ICAP:** Active
**Element Interactivity:** 0.15 (low)
**Knowledge:** Factual

**Example:** "This protocol operates at Layer 4 and provides reliable delivery" → "TCP"

### 13. image_to_term

**Description:** Image → Label

**ICAP:** Active
**Element Interactivity:** 0.2 (low)
**Knowledge:** Factual

**Example:** [Network diagram] → "Star topology"

### 14. audio_to_term

**Description:** Sound → Meaning

**ICAP:** Active
**Element Interactivity:** 0.2 (low)
**Knowledge:** Factual

**Example:** [Modem handshake sound] → "V.90 connection negotiation"

### 15. cloze_deletion

**Description:** Fill in the blank (text)

**ICAP:** Active
**Element Interactivity:** 0.3 (low-medium)
**Knowledge:** Factual/Conceptual

**Implementation:** Already implemented in `src/cortex/atoms/cloze.py`

**Example:** "The default gateway for 192.168.1.0/24 is typically ___"

### 16. cloze_dropdown

**Description:** Select from list (lower difficulty than free entry)

**ICAP:** Active
**Element Interactivity:** 0.2 (low)
**Knowledge:** Factual

**Example:** "HTTP uses port [80 | 443 | 8080 | 3389]"

### 17. cloze_bank

**Description:** Drag word from bank into blank

**ICAP:** Active
**Element Interactivity:** 0.25 (low)
**Knowledge:** Factual

**Example:** "Drag: [OSPF | RIP | EIGRP] is a link-state protocol"

### 18. symbolic_cloze

**Description:** Formula/equation completion

**ICAP:** Active
**Element Interactivity:** 0.4 (medium)
**Knowledge:** Procedural

**Example:** "Subnet mask calculation: 2^(32 - ___) - 2 = usable hosts"

### 19. short_answer_exact

**Description:** String match (case-sensitive)

**ICAP:** Constructive
**Element Interactivity:** 0.3 (low-medium)
**Knowledge:** Factual

**Example:** "What command shows active network connections?" → "netstat"

### 20. short_answer_regex

**Description:** Pattern match (accepts typos/variations)

**ICAP:** Constructive
**Element Interactivity:** 0.3 (low-medium)
**Knowledge:** Factual

**Example:** "Configure static route" → Accept: "ip route ...", "route add ..."

### 21. list_recall

**Description:** Name all items (order independent)

**ICAP:** Constructive
**Element Interactivity:** 0.5 (medium)
**Knowledge:** Factual

**Example:** "List all OSI layers" (any order accepted)

### 22. ordered_list_recall

**Description:** Name items in specific sequence

**ICAP:** Constructive
**Element Interactivity:** 0.6 (medium-high)
**Knowledge:** Procedural

**Example:** "List OSI layers from Physical to Application"

---

## III. Procedural & Sequential (11 types)

**Cognitive System:** Basal ganglia, prefrontal cortex (steps and flows)

### 23. parsons_problem

**Description:** Reorder code lines to form working program

**ICAP:** Constructive
**Element Interactivity:** 0.7 (high)
**Knowledge:** Procedural

**Implementation:** Already implemented in `src/cortex/atoms/parsons.py`

**Grading Logic:** Sequence matching with partial credit for subsequences

### 24. faded_parsons

**Description:** Reorder lines + fill in 1-2 blanks

**ICAP:** Constructive
**Element Interactivity:** 0.8 (high)
**Knowledge:** Procedural

**Example:** Mix of provided blocks and blank lines requiring code entry

### 25. distractor_parsons

**Description:** Reorder lines, discard fake lines

**ICAP:** Constructive
**Element Interactivity:** 0.75 (high)
**Knowledge:** Procedural

**Misconception Tagging:** Each distractor linked to specific error type

### 26. 2d_parsons

**Description:** Arrange blocks with indentation (Python structure)

**ICAP:** Constructive
**Element Interactivity:** 0.85 (very high)
**Knowledge:** Procedural

**Example:** Reconstruct nested if/else with correct indentation

### 27. timeline_ordering

**Description:** Drag historical events into chronological order

**ICAP:** Active
**Element Interactivity:** 0.4 (medium)
**Knowledge:** Factual

**Example:** "Order these network protocol developments: TCP/IP, Ethernet, HTTP, IPv6"

### 28. process_flow

**Description:** Connect boxes in flowchart (Start → Decision → End)

**ICAP:** Constructive
**Element Interactivity:** 0.7 (high)
**Knowledge:** Conceptual

**Example:** "Complete the packet routing decision flowchart"

### 29. gantt_adjustment

**Description:** Drag dependencies to fix delayed schedule

**ICAP:** Constructive
**Element Interactivity:** 0.9 (very high)
**Knowledge:** Procedural

**Example:** "Project delayed 2 days. Adjust network migration timeline"

### 30. circuit_routing

**Description:** Connect wires to complete logical circuit

**ICAP:** Constructive
**Element Interactivity:** 0.8 (high)
**Knowledge:** Procedural

**Example:** "Wire up NAT router connections"

### 31. molecule_assembly

**Description:** Drag atoms to form valid structure (chemistry analog)

**ICAP:** Constructive
**Element Interactivity:** 0.8 (high)
**Knowledge:** Conceptual

**CS Analog:** "Assemble OSI protocol stack layers"

### 32. equation_balancing

**Description:** Adjust coefficients to balance reaction

**ICAP:** Constructive
**Element Interactivity:** 0.7 (high)
**Knowledge:** Procedural

**CS Analog:** "Balance load across server pool (round-robin weights)"

### 33. sql_query_builder

**Description:** Drag blocks (SELECT, FROM, WHERE) to form query

**ICAP:** Constructive
**Element Interactivity:** 0.75 (high)
**Knowledge:** Procedural

**Example:** "Build query to find all devices on subnet 192.168.1.0/24"

---

## IV. Diagnosis & Reasoning (9 types)

**Cognitive System:** Causal reasoning, abductive logic

### 34. script_concordance_test

**Description:** If X, does diagnosis Y become more/less/unchanged likely?

**ICAP:** Constructive
**Element Interactivity:** 0.9 (very high)
**Knowledge:** Conceptual

**Medical Gold Standard**, adapted for networking troubleshooting

**Example:** "If ping fails but traceroute succeeds, is the issue more/less/equally likely to be a routing problem?"

**Grading:** Compare to expert panel distribution

### 35. key_feature_problem

**Description:** Select 3 most critical steps to take immediately (prioritization)

**ICAP:** Constructive
**Element Interactivity:** 0.85 (very high)
**Knowledge:** Metacognitive

**Example:** "Network outage detected. Select top 3 diagnostic steps"

### 36. fault_isolation

**Description:** Probe test points to find break

**ICAP:** Interactive
**Element Interactivity:** 0.9 (very high)
**Knowledge:** Procedural

**Example:** "Broken circuit. Test points A, B, C. Where is the fault?"

### 37. debugging_spot

**Description:** Highlight line causing crash

**ICAP:** Active
**Element Interactivity:** 0.7 (high)
**Knowledge:** Procedural

**Implementation:** Already implemented as error_spotting in handlers

### 38. debugging_fix

**Description:** Edit code to pass unit test

**ICAP:** Constructive
**Element Interactivity:** 0.9 (very high)
**Knowledge:** Procedural

**Grading:** Run unit tests against submitted code

### 39. differential_diagnosis

**Description:** Input symptoms → output 3 likely causes

**ICAP:** Constructive
**Element Interactivity:** 0.8 (high)
**Knowledge:** Conceptual

**Example:** "Connection timeout. List 3 possible causes"

### 40. what_if_simulation

**Description:** Predict outcome of parameter change

**ICAP:** Constructive
**Element Interactivity:** 0.7 (high)
**Knowledge:** Conceptual

**Example:** "If MTU increases to 9000, what happens to fragmentation?"

### 41. boundary_value_analysis

**Description:** Enter input values that would crash function

**ICAP:** Constructive
**Element Interactivity:** 0.8 (high)
**Knowledge:** Procedural

**Example:** "Enter IP address that would fail validation"

### 42. logic_gate_truth_table

**Description:** Fill in outputs for boolean circuit

**ICAP:** Constructive
**Element Interactivity:** 0.6 (medium-high)
**Knowledge:** Procedural

**Example:** "Complete truth table for NAND gate"

---

## V. Generative & Creative (8 types)

**Cognitive System:** Highest cognitive load—synthesis

### 43. sandboxed_code

**Description:** Write full function to pass hidden test cases

**ICAP:** Constructive
**Element Interactivity:** 1.0 (maximum)
**Knowledge:** Procedural

**Greenlight Integration:** Requires runtime execution environment

**Grading:** Unit test pass rate + code quality metrics

### 44. ui_construction

**Description:** Drag widgets to build UI matching spec

**ICAP:** Constructive
**Element Interactivity:** 0.85 (very high)
**Knowledge:** Procedural

**Example:** "Build network monitoring dashboard layout"

### 45. essay_ai_graded

**Description:** Write 3 paragraphs, graded on semantic key points

**ICAP:** Constructive
**Element Interactivity:** 0.9 (very high)
**Knowledge:** Conceptual

**Grading:** AI extracts key concepts and scores against rubric

### 46. diagram_drawing

**Description:** Draw free body diagram / network topology

**ICAP:** Constructive
**Element Interactivity:** 0.9 (very high)
**Knowledge:** Conceptual

**Example:** "Draw the network topology for a dual-homed server"

### 47. graph_plotting

**Description:** Plot points to represent equation

**ICAP:** Constructive
**Element Interactivity:** 0.7 (high)
**Knowledge:** Procedural

**Example:** "Plot bandwidth utilization over time"

### 48. audio_recording

**Description:** Record spoken explanation (STT analysis)

**ICAP:** Constructive
**Element Interactivity:** 0.8 (high)
**Knowledge:** Conceptual

**Example:** "Explain subnetting to a 5-year-old"

### 49. refactoring

**Description:** Rewrite O(n²) code to O(n)

**ICAP:** Constructive
**Element Interactivity:** 1.0 (maximum)
**Knowledge:** Procedural

**Grading:** Complexity analysis + test pass

### 50. translation

**Description:** Translate sentence English → Spanish (or code language-to-language)

**ICAP:** Constructive
**Element Interactivity:** 0.7 (high)
**Knowledge:** Procedural

**CS Example:** "Translate Python list comprehension to Java stream"

---

## VI. Data & Analysis (5 types)

**Cognitive System:** Statistical reasoning

### 51. data_classification

**Description:** Is this variable nominal, ordinal, or interval?

**ICAP:** Active
**Element Interactivity:** 0.3 (low-medium)
**Knowledge:** Conceptual

### 52. chart_interpretation

**Description:** What is the trend in Q3?

**ICAP:** Active
**Element Interactivity:** 0.4 (medium)
**Knowledge:** Conceptual

### 53. regression_line_fit

**Description:** Drag line to best fit scatter plot

**ICAP:** Active
**Element Interactivity:** 0.6 (medium-high)
**Knowledge:** Procedural

### 54. table_completion

**Description:** Fill in missing cells in spreadsheet

**ICAP:** Constructive
**Element Interactivity:** 0.7 (high)
**Knowledge:** Procedural

### 55. query_prediction

**Description:** What will this SQL query return?

**ICAP:** Constructive
**Element Interactivity:** 0.8 (high)
**Knowledge:** Procedural

---

## VII. Metacognitive & Affective (5 types)

**Cognitive System:** Self-regulation

### 56. confidence_slider

**Description:** How sure are you? (0-100%)

**ICAP:** Metacognitive
**Element Interactivity:** 0.1 (very low)
**Knowledge:** Metacognitive

**Critical for Hypercorrection Effect detection**

### 57. jol_judgment_of_learning

**Description:** Will you remember this tomorrow?

**ICAP:** Metacognitive
**Element Interactivity:** 0.2 (low)
**Knowledge:** Metacognitive

**Used for calibration training**

### 58. effort_rating

**Description:** How hard did you have to think?

**ICAP:** Metacognitive
**Element Interactivity:** 0.1 (very low)
**Knowledge:** Metacognitive

**Detects cognitive overload**

### 59. interest_check

**Description:** Do you want more practice on this topic?

**ICAP:** Metacognitive
**Element Interactivity:** 0.1 (very low)
**Knowledge:** Metacognitive

**Drives personalization**

### 60. strategy_selection

**Description:** Which formula should you use here? (before solving)

**ICAP:** Metacognitive
**Element Interactivity:** 0.5 (medium)
**Knowledge:** Metacognitive

**Promotes planning**

---

## VIII. Gamified & Speed (4 types)

**Cognitive System:** Automaticity—fluency

### 61. speed_match

**Description:** Match pairs as fast as possible

**ICAP:** Active
**Element Interactivity:** 0.2 (low)
**Knowledge:** Factual

**Fluency building**

### 62. falling_words

**Description:** Type word before it hits ground

**ICAP:** Active
**Element Interactivity:** 0.2 (low)
**Knowledge:** Procedural

**Command memorization drill**

### 63. rhythm_tap

**Description:** Tap spacebar to beat of code execution

**ICAP:** Active
**Element Interactivity:** 0.3 (low-medium)
**Knowledge:** Procedural

**Timing/sequencing practice**

### 64. mental_math_sprint

**Description:** 10 arithmetic problems in 30 seconds

**ICAP:** Active
**Element Interactivity:** 0.2 (low)
**Knowledge:** Procedural

**CS Analog:** Subnet calculations sprint

---

## IX. CS-Specific Extensions (20 types)

### 65. output_prediction

**Description:** Trace execution, predict output

**ICAP:** Constructive
**Element Interactivity:** 0.8 (high)
**Knowledge:** Procedural

**Implementation:** Partially in src/cortex/atoms/ (needs expansion)

### 66. bug_identification

**Description:** Find the bug in this code

**ICAP:** Active
**Element Interactivity:** 0.7 (high)
**Knowledge:** Procedural

### 67. root_cause_analysis

**Description:** Explain why this bug occurs

**ICAP:** Constructive
**Element Interactivity:** 0.9 (very high)
**Knowledge:** Conceptual

### 68. minimal_fix

**Description:** Smallest code change to fix bug

**ICAP:** Constructive
**Element Interactivity:** 0.9 (very high)
**Knowledge:** Procedural

### 69. trade_off_analysis

**Description:** Pick best approach under constraints

**ICAP:** Constructive
**Element Interactivity:** 0.9 (very high)
**Knowledge:** Metacognitive

### 70. failure_mode_prediction

**Description:** What breaks first if load increases?

**ICAP:** Constructive
**Element Interactivity:** 0.85 (very high)
**Knowledge:** Conceptual

### 71. component_responsibility

**Description:** Which component handles X?

**ICAP:** Active
**Element Interactivity:** 0.5 (medium)
**Knowledge:** Conceptual

### 72. scalability_reasoning

**Description:** How does this scale to 1M users?

**ICAP:** Constructive
**Element Interactivity:** 0.9 (very high)
**Knowledge:** Conceptual

### 73. security_boundary_identification

**Description:** Where is the trust boundary?

**ICAP:** Active
**Element Interactivity:** 0.7 (high)
**Knowledge:** Conceptual

### 74. api_contract_verification

**Description:** Does this implementation match spec?

**ICAP:** Active
**Element Interactivity:** 0.6 (medium-high)
**Knowledge:** Procedural

### 75. state_transition_validation

**Description:** Is this state machine transition valid?

**ICAP:** Active
**Element Interactivity:** 0.7 (high)
**Knowledge:** Conceptual

### 76. concurrency_hazard_detection

**Description:** Find the race condition

**ICAP:** Active
**Element Interactivity:** 0.95 (very high)
**Knowledge:** Procedural

### 77. resource_leak_identification

**Description:** Where is memory/connection not freed?

**ICAP:** Active
**Element Interactivity:** 0.8 (high)
**Knowledge:** Procedural

### 78. configuration_ordering

**Description:** Order these config steps correctly

**ICAP:** Constructive
**Element Interactivity:** 0.6 (medium-high)
**Knowledge:** Procedural

### 79. dependency_injection_selection

**Description:** Which dependency should be injected?

**ICAP:** Active
**Element Interactivity:** 0.7 (high)
**Knowledge:** Conceptual

### 80. interface_segregation

**Description:** Split this interface into focused contracts

**ICAP:** Constructive
**Element Interactivity:** 0.85 (very high)
**Knowledge:** Conceptual

### 81. test_case_generation

**Description:** Generate boundary test cases for function

**ICAP:** Constructive
**Element Interactivity:** 0.9 (very high)
**Knowledge:** Procedural

### 82. mock_object_design

**Description:** Design mocks for this component

**ICAP:** Constructive
**Element Interactivity:** 0.85 (very high)
**Knowledge:** Procedural

### 83. assertion_selection

**Description:** Which assertion best validates this?

**ICAP:** Active
**Element Interactivity:** 0.6 (medium-high)
**Knowledge:** Procedural

### 84. edge_case_identification

**Description:** List edge cases for this algorithm

**ICAP:** Constructive
**Element Interactivity:** 0.8 (high)
**Knowledge:** Metacognitive

---

## X. Advanced Structural (16 types)

### 85. matching_pairs

**Description:** Connect left/right columns

**ICAP:** Active
**Element Interactivity:** 0.4 (medium)
**Knowledge:** Factual/Conceptual

**Implementation:** Already in src/cortex/atoms/matching.py

### 86. categorization

**Description:** Drag items into categories

**ICAP:** Active
**Element Interactivity:** 0.5 (medium)
**Knowledge:** Conceptual

### 87. hierarchy_construction

**Description:** Build tree structure from concepts

**ICAP:** Constructive
**Element Interactivity:** 0.8 (high)
**Knowledge:** Conceptual

### 88. dependency_mapping

**Description:** Draw dependency graph

**ICAP:** Constructive
**Element Interactivity:** 0.85 (very high)
**Knowledge:** Conceptual

### 89. prerequisite_identification

**Description:** Which concepts must be learned first?

**ICAP:** Active
**Element Interactivity:** 0.6 (medium-high)
**Knowledge:** Metacognitive

### 90. analogical_reasoning

**Description:** A:B :: C:?

**ICAP:** Constructive
**Element Interactivity:** 0.7 (high)
**Knowledge:** Conceptual

### 91. constraint_satisfaction

**Description:** Arrange items meeting all constraints

**ICAP:** Constructive
**Element Interactivity:** 0.9 (very high)
**Knowledge:** Procedural

### 92. optimization_problem

**Description:** Maximize X while minimizing Y

**ICAP:** Constructive
**Element Interactivity:** 1.0 (maximum)
**Knowledge:** Procedural

### 93. proof_construction

**Description:** Order proof steps correctly

**ICAP:** Constructive
**Element Interactivity:** 0.95 (very high)
**Knowledge:** Procedural

### 94. counterexample_generation

**Description:** Find input that breaks this claim

**ICAP:** Constructive
**Element Interactivity:** 0.9 (very high)
**Knowledge:** Conceptual

### 95. invariant_identification

**Description:** What property always holds?

**ICAP:** Constructive
**Element Interactivity:** 0.85 (very high)
**Knowledge:** Conceptual

### 96. abstraction_level_selection

**Description:** Choose appropriate abstraction for task

**ICAP:** Active
**Element Interactivity:** 0.7 (high)
**Knowledge:** Metacognitive

### 97. design_pattern_application

**Description:** Which pattern fits this problem?

**ICAP:** Active
**Element Interactivity:** 0.75 (high)
**Knowledge:** Conceptual

### 98. architecture_critique

**Description:** Identify flaws in system design

**ICAP:** Constructive
**Element Interactivity:** 0.9 (very high)
**Knowledge:** Conceptual

### 99. load_balancing_strategy

**Description:** Distribute work across resources

**ICAP:** Constructive
**Element Interactivity:** 0.85 (very high)
**Knowledge:** Procedural

### 100. caching_policy_selection

**Description:** Choose cache eviction strategy

**ICAP:** Active
**Element Interactivity:** 0.7 (high)
**Knowledge:** Conceptual

---

## Implementation Priority Tiers

### Tier 1 (High Value, Medium Complexity)

Already implemented or in progress:
- flashcard, cloze_deletion, mcq, true_false, numeric, matching, parsons

**Next to implement** (Batch 3a-3c):
- cloze_dropdown, short_answer_exact, short_answer_regex
- faded_parsons, distractor_parsons
- output_prediction, bug_identification
- confidence_slider, effort_rating

### Tier 2 (High Value, High Complexity)

Requires Greenlight integration:
- sandboxed_code, debugging_fix, refactoring

Requires advanced UI:
- diagram_drawing, graph_plotting, ui_construction

### Tier 3 (Specialized Domains)

Domain-specific atoms:
- script_concordance_test (medical → networking troubleshooting)
- gantt_adjustment (project management)
- circuit_routing (electrical → network wiring)

### Tier 4 (Research Extensions)

Cutting-edge types:
- essay_ai_graded (requires LLM integration)
- audio_recording (requires STT)
- interactive simulation atoms

## Grading Logic Patterns

### Pattern 1: Exact Match

```json
{
  "type": "exact_match",
  "correct_answer": "192.168.1.1",
  "case_sensitive": false
}
```

### Pattern 2: Regex Match

```json
{
  "type": "regex_match",
  "pattern": "^(ip route|route add) .+",
  "flags": "i"
}
```

### Pattern 3: Unit Tests (Greenlight)

```json
{
  "type": "unit_test",
  "test_cases": [
    {"input": [5, 3], "expected_output": 8},
    {"input": [0, 0], "expected_output": 0}
  ],
  "timeout_ms": 5000
}
```

### Pattern 4: Rubric-Based

```json
{
  "type": "rubric",
  "criteria": [
    {"name": "mentions_tcp", "points": 2, "required": true},
    {"name": "explains_handshake", "points": 3, "required": true},
    {"name": "diagrams_sequence", "points": 2, "required": false}
  ],
  "min_pass_score": 5
}
```

### Pattern 5: Expert Concordance

```json
{
  "type": "expert_concordance",
  "expert_distribution": {
    "more_likely": 0.70,
    "unchanged": 0.20,
    "less_likely": 0.10
  },
  "scoring": "aggregate_agreement"
}
```

## Misconception Linking

Every distractor must link to a cognitive error:

```json
{
  "options": [
    {"id": "A", "text": "TCP", "correct": true},
    {
      "id": "B",
      "text": "UDP",
      "correct": false,
      "misconception_id": "confusing_tcp_udp_reliability"
    },
    {
      "id": "C",
      "text": "ICMP",
      "correct": false,
      "misconception_id": "confusing_layers_3_and_4"
    }
  ]
}
```

## Related Documentation

- [BDD Testing Strategy](../explanation/bdd-testing-strategy.md): How to test these atoms
- [CI/CD Pipeline](../explanation/ci-cd-pipeline.md): Automated validation
- [Database Schema Critique](../explanation/schema-migration-plan.md): Moving from front/back to JSONB

## Scientific References

- **ICAP Framework:** Chi, M. T., & Wylie, R. (2014). The ICAP framework. *Educational Psychologist*
- **Cognitive Load Theory:** Sweller, J. (1988). Cognitive load during problem solving
- **Bloom's Taxonomy (Revised):** Krathwohl, D. R. (2002). A revision of Bloom's taxonomy
- **Parsons Problems:** Parsons, D., & Haden, P. (2006). Parson's programming puzzles
- **Script Concordance Testing:** Charlin, B., et al. (2000). The script concordance test
