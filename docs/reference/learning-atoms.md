# Universal Taxonomy of Learning Atoms

**Purpose:** This document defines the complete taxonomy of learning atom types for Cortex-CLI, designed to rival DARPA Digital Tutor and Knewton-class adaptive engines.

**Design Philosophy:** These are not UI widgets—they are **cognitive interaction primitives**. Each atom type maps to a specific mental operation required for mastery.

---

## Routing: cortex-cli vs Greenlight

`cortex-cli` remains the terminal-native study client; Greenlight is the IDE/workbench integration. Atom families route as follows:

- **Greenlight-owned (runtime/IDE atoms):** code submission with tests/perf gates, debugging/fault isolation, diff review and “minimal fix” tasks, code understanding/trace, code construction/skeleton fill, config/CLI sequencing with terminal emulator, project-scale tasks with branches/worktrees and git guidance, architecture/trade-off reasoning tied to a codebase, testing/verification on real code, state/puzzle manipulation, interactive parameter sliders.
- **cortex-cli-owned (terminal atoms):** recognition/recall (binary choice, MCQ variants, cloze, short answer, numeric), structural drills (matching, sequencing, Parsons, associations), light meta-cognitive prompts, comparison/explanation/creative text atoms, error-spotting without runtime execution.
- **Shared wrappers:** confidence/difficulty ratings, reflection/self-correction flows, error tagging. Runtime atoms can return results back to cortex-cli for display when invoked from the terminal.

## Shared Atom Schema (cortex-cli <> Greenlight)

Common envelope fields to support routing and grading:

- `owner`: `cortex` | `greenlight` (who presents/executes the atom)
- `grading_mode`: `static` | `runtime` | `human` | `hybrid`
- `runner` (for runtime): `language`, `entrypoint`, `tests` (path or inline), `time_limit_ms`, `memory_limit_mb`, `sandbox_policy`
- `diff_context` (optional): `base_path`, `patch`, `review_rubric`, `assertions/tests`
- `git_guidance` (optional): whether to suggest/apply git commands (branch, worktree, stash, cherry-pick)
- `attachments` (optional): allowed inputs (file, audio, image)
- `meta_wrappers`: `collect_confidence`, `collect_difficulty`, `allow_self_correction`, `error_tagging`

See `docs/reference/atom-envelope.schema.json` for the JSON Schema and `docs/reference/greenlight-handoff.openapi.yaml` for the handoff contract used when routing runtime atoms to Greenlight.

Example envelope:

```json
{
  "atom_type": "code_submission",
  "owner": "greenlight",
  "grading_mode": "runtime",
  "runner": {
    "language": "python",
    "entrypoint": "main.py",
    "tests": "tests/test_main.py",
    "time_limit_ms": 3000,
    "memory_limit_mb": 256,
    "sandbox_policy": "isolated"
  },
  "meta_wrappers": {
    "collect_confidence": true,
    "collect_difficulty": true,
    "allow_self_correction": true,
    "error_tagging": true
  }
}
```

---

## Implementation Status

### Currently Implemented (7 atom types)

Cortex-CLI has **7 production-ready handlers** as of 2025-12:

| Atom Type | Category | Handler | Status | Notes |
|-----------|----------|---------|--------|-------|
| **flashcard** | Recall & Entry | `FlashcardHandler` | ✓ Production | Simple front/back with self-evaluation |
| **cloze** | Recall & Entry | `ClozeHandler` | ✓ Production | Fill-in-the-blank with progressive hints |
| **mcq** | Recognition & Discrimination | `MCQHandler` | ✓ Production | Single/multi-select with JSON/legacy format support |
| **true_false** | Recognition & Discrimination | `TrueFalseHandler` | ✓ Production | Binary choice with LLM error explanations |
| **numeric** | Recall & Entry | `NumericHandler` | ✓ Production | Supports decimal, binary, hex, IP, CIDR with tolerance |
| **matching** | Structural & Relational | `MatchingHandler` | ✓ Production | Term-definition pairing with partial credit |
| **parsons** | Structural & Relational | `ParsonsHandler` | ✓ Production | Code/step ordering with LLM error analysis |

**Coverage:** ~12% of taxonomy (7 of 60+ atom types)

### Missing Atom Types by Priority

#### High Priority (High ROI, Terminal-Compatible)
- [ ] **Short Answer** (exact/fuzzy/multi-acceptable) - Active recall, high retention
- [ ] **Advanced Cloze** (dropdown, hints, progressive reveal) - Scaffolded learning
- [ ] **Numeric Extensions** (units, tolerance, scientific notation) - CCNA calculations
- [ ] **MCQ Variants** (best-answer, least-incorrect, negative) - Deeper discrimination
- [ ] **Error-Spotting** (highlight incorrect parts) - Debugging foundation

#### Medium Priority (Structural Understanding)
- [ ] **Sequencing** (timeline/process ordering) - Procedural knowledge
- [ ] **Association** (bucket sorting, grouping) - Category understanding
- [ ] **Hotspot** (ASCII region selection or Greenlight handoff) - Visual identification
- [ ] **Graph Construction** (text DSL: "A->B, B->C") - Systems thinking

#### Meta-Cognitive Wrappers (Enhances All Types)
- [ ] **Confidence Rating** (pre/post) - Calibration, misconception detection
- [ ] **Difficulty Rating** - Adaptive difficulty
- [ ] **Reflection Prompts** (why/how) - Metacognition
- [ ] **Self-Correction Retry** with hints - Hypercorrection effect

#### Greenlight-Delegated (Runtime Required)
These are designed for Greenlight IDE integration:
- **Code Submission** with test execution
- **Debugging** (interactive debugger)
- **Code Understanding** (output/state tracing)
- **Code Construction** (fill line/function)
- **CLI Emulator** (terminal with state)
- **Diff Review** (side-by-side with annotations)
- **Project-Scale** (git workflows, multi-file)

See [Greenlight Integration](../explanation/greenlight-integration.md) for runtime atom details.

---

## TUI Widget Requirements by Atom Family

### Terminal-Compatible Widgets (Cortex-CLI)

| Atom Family | Widget Type | Input Method | Example |
|-------------|-------------|--------------|---------|
| **Recognition** (MCQ, T/F) | Rich Table with numbered rows | Number selection (single/multi) | "1" or "1 3 5" |
| **Recall** (Cloze, Short Answer) | Text Prompt with validation | Free-form text | "192.168.1.0" |
| **Numeric** | Text Prompt with parsers | Number/IP/Binary/Hex | "0b11000000" |
| **Matching** | Dual-column table | Pair notation | "1A 2B 3C" |
| **Sequencing** | Numbered list | Index ordering | "3 1 2 4" |
| **Parsons** | Numbered code blocks | Index ordering | "3 1 2 4" |
| **Error-Spot** | Numbered lines | Line number selection | "2 5 7" |
| **Hotspot** (text-based) | Labeled regions | Letter/number selection | "C" or "3" |
| **Association** | Multi-column buckets | Drag notation | "A:1,2 B:3,4" |

**Design Pattern:** Keyboard-first, no mouse required, works over SSH.

### IDE-Required Widgets (Greenlight Handoff)

| Atom Family | Widget Type | Why IDE Needed |
|-------------|-------------|----------------|
| **Code Submission** | Editor + Test Console | Syntax highlighting, test runner, compilation |
| **Debugging** | Interactive Debugger | Breakpoints, variable inspection, step execution |
| **Diff Review** | Side-by-side Diff Viewer | Visual diff, annotation, patch application |
| **CLI Emulator** | Full Terminal Emulator | Stateful shell, command history, completion |
| **Graph Construction** (visual) | Graph Editor Canvas | Node/edge dragging, layout algorithms |
| **Diagram Drawing** | Canvas Widget | UML/network topology visual editing |

**Design Pattern:** Mouse/keyboard hybrid, requires GUI for visualization.

---

## Visual Taxonomy Hierarchy

```
Learning Atom Taxonomy (60+ types across 11 categories)
═══════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────┐
│                    COGNITIVE OPERATION                      │
│           Recognition → Recall → Construction               │
│                  → Application → Synthesis                  │
└─────────────────────────────────────────────────────────────┘

┌────────────────────┐
│  I. Recognition &  │ ─────┐
│   Discrimination   │  6   │  Binary Choice, MCQ, Multi-Select,
└────────────────────┘      │  Hotspot, Error-Spotting
                             │  ✓ Implemented: 2/6 (MCQ, T/F)
┌────────────────────┐      │
│ II. Recall & Entry │ ─────┤
└────────────────────┘  8   │  Short Answer, Cloze, Numeric, Formula
                             │  ✓ Implemented: 3/8 (Flashcard, Cloze, Numeric)
┌────────────────────┐      │
│ III. Structural &  │ ─────┤
│    Relational      │  7   │  Matching, Association, Sequencing, Parsons, Graph
└────────────────────┘      │  ✓ Implemented: 2/7 (Matching, Parsons)
                             │
┌────────────────────┐      │
│ IV. Production &   │ ─────┤
│   Generative       │  5   │  Free Text, Code Submission, Diagram, Audio, File Upload
└────────────────────┘      │  ✓ Implemented: 0/5 (Greenlight-delegated)
                             │
┌────────────────────┐      │
│ V. Simulation &    │ ──────  4 types: Sliders, CLI Emulator, Dialogue, State Puzzles
│    Dynamic         │         ✓ Implemented: 0/4 (Greenlight-delegated)
└────────────────────┘

┌────────────────────┐
│ VI. Meta-Cognitive │ ───────  5 types: Confidence, Difficulty, Reflection,
└────────────────────┘          Self-Correction, Error Tagging
                                ✓ Implemented: 0/5 (Wrappers pending)

┌────────────────────┐
│ VII. CS-Specific   │ ───────  7 subtypes: Code Understanding, Construction,
└────────────────────┘          Debugging, Config/CLI, Architecture, Algorithms, Testing
                                ✓ Implemented: 0/7 (Greenlight-delegated)

┌────────────────────┐
│ VIII. Error-Focused│ ───────  2 types: Error ID, Error Correction
└────────────────────┘          ✓ Implemented: 0/2 (Partial: Parsons has error analysis)

┌────────────────────┐
│ IX. Comparison &   │ ───────  6 types: Compare A vs B, Similarities, Differences,
│   Discrimination   │          Trade-offs, When-to-use, Boundary Cases
└────────────────────┘          ✓ Implemented: 0/6 (Text-based possible)

┌────────────────────┐
│ X. Explanation &   │ ───────  6 types: Own words, Teach-back, Why/Why-not,
│   Elaboration      │          Mechanism, Causal Chain
└────────────────────┘          ✓ Implemented: 0/6 (Free-text requires LLM grading)

┌────────────────────┐
│ XI. Creative &     │ ───────  6 types: Generate example/counterexample/analogy,
│    Generative      │          Test case, Design, Propose alternative
└────────────────────┘          ✓ Implemented: 0/6 (Expert-level, LLM grading)

═══════════════════════════════════════════════════════════════════

Total Coverage: 7 of 60+ types (12%)
Terminal-Ready Backlog: ~15 high-priority types
Greenlight-Delegated: ~20 runtime-dependent types
Meta-Wrappers: 5 cross-cutting enhancements
```

**Legend:**
- ✓ Implemented: Production-ready handler in `src/cortex/atoms/`
- Terminal-Ready: Can be implemented with Rich library widgets
- Greenlight-Delegated: Requires IDE (code execution, debugging, visual editors)
- Meta-Wrappers: Enhance existing atom types (confidence, reflection, etc.)

---

## Table of Contents

1. [Recognition & Discrimination Atoms](#i-recognition--discrimination-atoms)
2. [Recall & Entry Atoms](#ii-recall--entry-atoms)
3. [Structural & Relational Atoms](#iii-structural--relational-atoms)
4. [Production & Generative Atoms](#iv-production--generative-atoms)
5. [Simulation & Dynamic Atoms](#v-simulation--dynamic-atoms)
6. [Meta-Cognitive Atoms](#vi-meta-cognitive-atoms)
7. [Computer Science Specific Atoms](#vii-computer-science-specific-atoms)
8. [Error-Focused Atoms](#viii-error-focused-atoms)
9. [Comparison & Discrimination Atoms](#ix-comparison--discrimination-atoms)
10. [Explanation & Elaboration Atoms](#x-explanation--elaboration-atoms)
11. [Creative & Generative Atoms](#xi-creative--generative-atoms)

---

## I. Recognition & Discrimination Atoms

**Cognitive Operation:** Low friction, high diagnostic speed. Verify facts and filter misconceptions.

**Use Case:** Rapid pulse-checking of factual premises.

### 1.1 Binary Choice
- **True/False**
- **Yes/No**
- **Valid/Invalid**
- **Correct/Incorrect**

**System Use:** Testing single premise validity. High failure rate indicates fundamental misunderstanding.

### 1.2 Single Selection (MCQ)
- **Standard 1-of-N** - Choose the single correct answer
- **Negative Selection** - "Which of these is NOT..."
- **Best Answer** - "Which is the MOST appropriate..."
- **Least Incorrect** - "Which is the LEAST problematic..."

**System Use:** Distinguishing correct concept from plausible distractors. Distractor selection reveals error class.

### 1.3 Multiple Selection
- **Select-All-That-Apply** - N-of-N correct answers
- **Select-None** - All options are incorrect
- **Select-Minimum** - "Choose at least 2 valid..."

**System Use:** Testing completeness of knowledge (e.g., "Select all valid IP addresses"). High failure rate indicates partial knowledge.

### 1.4 Visual Identification
- **Hotspot** - Click the specific region on an image/diagram
- **Region Selection** - Draw a box around the target area
- **Label Placement** - Drag labels to correct positions on diagram

**System Use:** Anatomy, UI elements, circuit diagrams, network topologies.

### 1.5 Error Spotting
- **Highlight Incorrect** - Mark the wrong part of text/code
- **Count Errors** - "How many errors are in this code?"
- **Classify Error** - "What type of error is this?"

**System Use:** Debugging, proofreading. High transfer value to real-world tasks.

---

## II. Recall & Entry Atoms

**Cognitive Operation:** Retrieval practice. Fights the forgetting curve (Ebbinghaus) better than recognition.

**Use Case:** Long-term retention, active recall, generation effect.

### 2.1 Short Answer
- **Exact Match** - Auto-graded against strict string/number
- **Fuzzy/Keyword** - Graded via Regex or keyword presence
- **Case-Insensitive** - Accepts variations in capitalization
- **Multiple Acceptable** - Any of several correct answers

**System Use:** Terms, definitions, commands, formulas.

### 2.2 Cloze Deletion (Fill-in-the-Blank)
- **Single Cloze** - One missing term
- **Multiple Cloze** - Several missing terms in sequence
- **Dropdown Cloze** - Select from options (easier, recognition-based)
- **Text Entry Cloze** - Type the answer (harder, recall-based)
- **Cloze with Hints** - First letter or character count provided

**System Use:** Syntax, key terms, procedural steps.

### 2.3 Numeric Entry
- **Exact** - Precise integer/float input
- **Range/Tolerance** - "Enter a value between 10.5 and 10.8"
- **Unit-Aware** - Number + Unit dropdown (e.g., "50" + "mV")
- **Scientific Notation** - Accepts variations (1000 = 1e3 = 1.0×10³)

**System Use:** Subnet calculations, time complexity, performance metrics.

### 2.4 Formula / Symbolic Entry
- **LaTeX/MathML Input** - Mathematical expressions
- **Code Expression** - Language-specific syntax (e.g., Python lambda)
- **Regex** - Regular expression construction
- **SQL Query** - Construct query to match specification

**System Use:** Math, Physics, Logic proofs, query languages.

---

## III. Structural & Relational Atoms

**Cognitive Operation:** Connecting concepts. Tests "System 2" thinking—understanding how things fit together.

**Use Case:** Schema building, relational understanding, prerequisite mapping.

### 3.1 Matching (1-to-1)
- **Term ↔ Definition**
- **Concept ↔ Example**
- **Cause ↔ Effect**
- **Input ↔ Output**
- **Symbol ↔ Meaning**
- **API ↔ Behavior**
- **Layer ↔ Responsibility** (OSI ↔ TCP/IP)

**System Use:** Building semantic relationships, concept discrimination.

### 3.2 Association (Many-to-Many)
- **Categorization** - Drag items into buckets
- **Grouping** - "Which of these belong together?"
- **Class Membership** - "Sort these into TCP vs UDP"
- **Taxonomy Placement** - Hierarchical classification

**System Use:** Understanding categories, protocols, design patterns.

### 3.3 Ordering / Sequencing
- **Step Ordering** - Arrange procedural steps
- **Timeline Ordering** - Historical/temporal sequence
- **Process Flow** - Execution order
- **Algorithm Steps** - Logical sequence
- **Network Protocol Phases** - Handshake steps

**System Use:** Procedures, algorithms, timelines, state machines.

### 3.4 Parsons Problems
- **Ordered Parsons** - Arrange code blocks in correct order
- **Scrambled Parsons** - Same as above but fully randomized
- **Distractor Parsons** - Contains unnecessary code blocks
- **Faded Parsons** - Some lines are missing code (semi-scaffolded)
- **Partial Parsons** - Mix of provided and blank lines
- **Block-Constrained Parsons** - Indentation/scope constraints

**System Use:** Teaching program structure without syntax overload (Cognitive Load Theory).

### 3.5 Graph / Network Construction
- **Node Connection** - Draw edges between entities
- **Dependency Graph** - Show prerequisite relationships
- **State Diagram** - Model state transitions
- **ER Diagram** - Entity-relationship modeling

**System Use:** Database design, system architecture, state machines.

---

## IV. Production & Generative Atoms

**Cognitive Operation:** Synthesis. High cognitive load, requires advanced grading (AI or peer).

**Use Case:** Expert-level assessment, transfer capability, creative application.

### 4.1 Free Text / Essay
- **Short Response** (1-3 sentences)
- **Paragraph** (100-300 words)
- **Essay** (500+ words)
- **Structured Response** (with required sections)

**System Use:** Explanation, justification, argumentation. Requires AI or peer grading.

### 4.2 Code Submission (Sandboxed)
- **Function Implementation** - Write a function to spec
- **Complete Program** - Full executable solution
- **Unit-Test Driven** - Must pass provided test cases
- **Performance Constrained** - Must meet time/space complexity
- **Language Translation** - Python → JavaScript equivalent

**System Use:** Gold standard for CS mastery. Auto-graded via test execution.

### 4.3 Diagram Drawing
- **UML Diagram** - Class/sequence/state diagrams
- **Network Topology** - Draw network architecture
- **Flowchart** - Logic flow representation
- **ER Diagram** - Database schema design

**System Use:** System design, architecture planning.

### 4.4 Audio / Oral Response
- **Recording Speech** - Pronunciation, pitch, intonation
- **Voice Command** - CLI command verbalization
- **Explanation Verbalization** - Teach-back protocol

**System Use:** Language learning, presentation skills, technical communication.

### 4.5 File Upload
- **CAD File** - Engineering design
- **Excel Sheet** - Data analysis
- **Image/Screenshot** - Visual artifact
- **Archive (zip)** - Complete project submission

**System Use:** Portfolio assessment, project-based learning.

---

## V. Simulation & Dynamic Atoms

**Cognitive Operation:** Application. Assessing behavior in a live environment.

**Use Case:** Transfer to real-world scenarios, procedural fluency.

### 5.1 Interactive Parameter Slider
- **Single Variable** - Adjust one parameter
- **Multi-Variable** - Adjust multiple interdependent values
- **Target State** - Reach a specific output state

**System Use:** Understanding variables in calculus, physics, performance tuning.

### 5.2 CLI / Terminal Emulator
- **Command Sequence** - Execute commands to achieve state
- **Configuration Task** - Configure a system via terminal
- **Troubleshooting** - Diagnose and fix via CLI commands

**System Use:** DevOps, Linux training, Cisco networking (perfect for CCNA).

### 5.3 Chat / Dialogue Sim
- **Branching Conversation** - Choose responses
- **Negotiation** - Achieve a goal through dialogue
- **Customer Service** - Handle support scenario

**System Use:** Soft skills, patient diagnosis, sales training.

### 5.4 State Manipulation
- **Widget Interaction** - Manipulate UI to reach solved state
- **Puzzle** - Balance binary tree, solve maze
- **Game Simulation** - Strategic decision-making

**System Use:** Algorithm visualization, strategic thinking.

---

## VI. Meta-Cognitive Atoms

**Cognitive Operation:** The "Sensors" of the Learning System. Optimize the algorithm, not the score.

**Use Case:** Calibrating confidence, detecting misconceptions, personalizing difficulty.

### 6.1 Confidence Rating
- **Pre-Answer** - "How sure are you?" (before attempting)
- **Post-Answer** - "How confident in your answer?" (after attempting)
- **Likert Scale** - 1-5 or 1-7 scale
- **Binary** - Confident vs Not Confident

**System Use:** High Confidence + Wrong Answer = **Misconception** (Urgent intervention needed).

### 6.2 Difficulty Rating
- **Subjective Difficulty** - "Was this too hard?"
- **Effort Rating** - "How much mental effort did this require?"
- **Time Perception** - "Did this feel too slow?"

**System Use:** Adaptive difficulty calibration, cognitive load detection.

### 6.3 Reflection / Justification
- **"Why did you choose that answer?"**
- **"Explain your reasoning"**
- **"What strategy did you use?"**

**System Use:** Metacognition development, strategy awareness.

### 6.4 Self-Correction
- **Post-Error Diagnosis** - "You got this wrong. Why might that be?"
- **Hint-Triggered Retry** - "Look at the hint and try again"
- **Peer Explanation** - "Explain this to someone else"

**System Use:** Hypercorrection effect, self-regulated learning.

### 6.5 Error Classification
- **Tag Your Error** - "Was this a slip or a misconception?"
- **Error Source** - "Syntax error, logic error, or conceptual error?"

**System Use:** Error pattern analysis, targeted remediation.

---

## VII. Computer Science Specific Atoms

**Cognitive Operation:** Domain-specific interactions optimized for programming and systems.

**Use Case:** Teaching CS concepts with high transfer to real-world coding.

### 7.1 Code Understanding (Passive)
- **Output Prediction** - "What does this code print?"
- **State Tracing** - "What is the value of `x` at line 10?"
- **Control-Flow Tracing** - "Which lines execute if input is 5?"
- **Variable Evolution Table** - Track variable values through execution

**System Use:** Reading comprehension before writing capability.

### 7.2 Code Construction (Active)
- **Complete the Line** - Fill in missing code statement
- **Complete the Function** - Finish partially-written function
- **Implement Algorithm Skeleton** - Fill in TODO sections
- **Write From Specification** - Full implementation from requirements
- **Translate Pseudocode** - Convert algorithm to code

**System Use:** Scaffolded progression from passive to active coding.

### 7.3 Debugging Atoms
- **Bug Identification** - "Where is the bug?"
- **Root-Cause Analysis** - "Why is this failing?"
- **Minimal Fix Selection** - "What's the smallest change to fix this?"
- **Error Message Interpretation** - "What does this compiler error mean?"
- **Log Analysis** - "Diagnose the issue from these logs"
- **Failing Test Diagnosis** - "Why did this test fail?"

**System Use:** High-ROI skill development, mirrors real-world work.

### 7.4 Configuration & CLI Atoms
- **Command Sequencing** - Order of commands matters
- **Command Completion** - Finish the command syntax
- **Config Ordering** - Apply configuration in correct order
- **Which Command Does This?** - Reverse lookup
- **Missing Command Detection** - Identify omitted step
- **Stateful CLI Reasoning** - "What mode are we in? (exec vs config)"

**System Use:** DevOps, networking, sysadmin training.

### 7.5 System & Architecture Reasoning
- **Architecture Comparison** - Monolith vs Microservices
- **Trade-off Analysis** - "What are the pros/cons of approach X?"
- **Component Responsibility Attribution** - "Which layer handles X?"
- **Failure Mode Prediction** - "What breaks if X fails?"
- **Scalability Reasoning** - "How does this scale to N users?"
- **Security Boundary Identification** - "Where should validation occur?"

**System Use:** Moving learner from coder → engineer.

### 7.6 Algorithmic Reasoning
- **Dry-Run Algorithm** - Execute by hand
- **Invariant Identification** - "What stays true in this loop?"
- **Edge Case Identification** - "What inputs break this?"
- **Complexity Analysis** - "What's the Big-O?"
- **Correctness Proof (Informal)** - "Why does this algorithm work?"
- **Optimization Choice** - "How can we make this faster?"

**System Use:** CS theory + practice integration.

### 7.7 Testing & Verification Atoms
- **Test Case Generation** - "Write test cases for this function"
- **Boundary Testing** - "Identify edge cases"
- **Property-Based Reasoning** - "What properties must hold?"
- **Expected vs Actual Comparison** - "Does this match the spec?"
- **Coverage Gap Identification** - "What's not tested?"

**System Use:** Professional software engineering practices.

---

## VIII. Error-Focused Atoms

**Cognitive Operation:** One of the strongest learning accelerators.

**Use Case:** Learning from mistakes, debugging, fault isolation.

### 8.1 Error Identification
- **Spot the Bug** - Find incorrect code/logic
- **Find Incorrect Step** - Identify wrong procedural step
- **Identify False Premise** - Detect flawed assumption
- **Inconsistent Assumption** - Find logical contradiction

**System Use:** Critical thinking, debugging expertise.

### 8.2 Error Correction
- **Fix the Code** - Correct the bug
- **Correct the Formula** - Fix mathematical error
- **Rewrite Incorrect Statement** - Improve flawed explanation
- **Repair Configuration** - Fix broken config

**System Use:** Active remediation, transfer to real debugging.

---

## IX. Comparison & Discrimination Atoms

**Cognitive Operation:** Prevents shallow pattern matching.

**Use Case:** Deep understanding, boundary recognition, when-to-use-which knowledge.

### 9.1 Comparison Types
- **Compare A vs B** - Side-by-side analysis
- **Similarities** - "What do they have in common?"
- **Differences** - "How do they differ?"
- **Trade-offs** - "What are the pros/cons of each?"
- **When to use which** - "When should you choose X over Y?"
- **Boundary cases** - "Where does X stop being appropriate?"

**System Use:** Discriminating between similar concepts (TCP vs UDP, Array vs Linked List).

---

## X. Explanation & Elaboration Atoms

**Cognitive Operation:** Germane load generators (productive cognitive effort).

**Use Case:** Deep understanding, transfer, teaching capability.

### 10.1 Explanation Types
- **Explain in own words** - Paraphrase concept
- **Teach-back** - "Explain as if teaching a peer"
- **Why does this work?** - Mechanism explanation
- **Why not the alternative?** - Contrast justification
- **Mechanism explanation** - "How does X achieve Y?"
- **Causal chain explanation** - "What causes what?"

**System Use:** Testing genuine understanding vs memorization.

---

## XI. Creative & Generative Atoms

**Cognitive Operation:** High cognitive load, expert-level application.

**Use Case:** Synthesis, innovation, transfer to novel contexts.

### 11.1 Creative Types
- **Generate example** - "Give an example of X"
- **Generate counterexample** - "When does this NOT work?"
- **Create analogy** - "What is X like?"
- **Create test case** - "Design a test for this"
- **Design solution** - "How would you solve this?"
- **Propose alternative** - "What's another way?"

**System Use:** Expert-level synthesis, real-world application.

---

## Implementation Notes

### Atom vs Wrapper

In a DARPA/Knewton-like system, the **Atom Type** is just the container. The intelligence comes from the **Tagging Schema** applied to that atom.

**Example:**

```json
{
  "atom_type": "mcq",
  "question": "What is the default OSPF cost for a 100 Mbps link?",
  "choices": [
    {
      "text": "1",
      "correct": true,
      "skill_id": "ospf_cost_calculation",
      "mastery_level": 3
    },
    {
      "text": "10",
      "correct": false,
      "error_class": "wrong_bandwidth",
      "misconception_id": 44
    },
    {
      "text": "100",
      "correct": false,
      "error_class": "inverted_formula",
      "misconception_id": 45
    },
    {
      "text": "64",
      "correct": false,
      "error_class": "confused_with_eigrp",
      "misconception_id": 46
    }
  ]
}
```

The system doesn't just know "Choice B is wrong"—it knows **why** it's wrong and **what misconception** it reveals.

---

## Scientific Hierarchy of Efficacy

**Retention ROI** (Return on Investment for Long-Term Mastery):

| Rank | Cognitive Mechanism | Atom Types | Why? |
|------|---------------------|------------|------|
| 1 (Highest) | Active Recall | Short Answer, Code Entry, Essay | Forces neural pathway strengthening. Hardest to do, best for long-term memory. |
| 2 | Structural Assembly | Parsons, Concept Mapping, Ordering | Builds mental schemas (how things fit together) without overloading working memory. |
| 3 | Discrimination | Multiple Choice, Classification | Good for checking if the user can distinguish A from B, but creates weaker memory traces. |
| 4 (Lowest) | Passive Exposure | Reading, Watching Video | Not an interaction atom. This is input, not learning. |

---

## Next Steps

See:
- [Scientific Foundations](scientific-foundations.md) for cognitive science backing
- [TUI Design](../explanation/tui-design.md) for presentation architecture
- [Atom Handlers](atom-handlers.md) for implementation details

---

**Status:** Reference Document (Living Document)
**Last Updated:** 2025-12-21
**Authors:** Project Astartes Team
