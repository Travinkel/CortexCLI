# TUI Design: Split-Pane Interactive Learning Interface

**Purpose:** Define the Terminal User Interface (TUI) architecture for Cortex-CLI as a DARPA Digital Tutor-class system.

**Design Philosophy:** The learner should never see "atom types" (MCQ, Parsons, etc.). They see **tasks, challenges, or checks**.

---

## Table of Contents

1. [Design Principles](#design-principles)
2. [Session Orchestration](#session-orchestration)
3. [Split-Pane Layouts](#split-pane-layouts)
4. [Feedback & Cognition Layer](#feedback--cognition-layer)
5. [Presentation Modes](#presentation-modes)
6. [Macro-Presentation](#macro-presentation)
7. [Implementation Approach](#implementation-approach)

---

## Design Principles

### 1. Tasks, Not Types

**Rule:** The learner should never see "atom types" (MCQ, Parsons, etc.). They see tasks, challenges, or checks.

**Presentation Primitives (Learner-Facing):**

| Internal Type | Learner Sees |
|---------------|--------------|
| MCQ | "Choose the best approach" |
| Parsons | "Reconstruct the solution" |
| Code Submission | "Implement this" |
| Debugging | "Something is broken—find it" |
| Output Prediction | "Predict what happens" |
| Numeric Calculation | "Compute the result" |
| Design Decision | "Pick the best approach under constraints" |
| Free Recall | "Explain from memory" |
| Meta-Cognitive | "How confident are you?" |

> **Atom type is an internal implementation detail.**

### 2. Minimal Chrome

- One task at a time
- Minimal UI elements
- No visible scoring until after commitment
- Feedback is **diagnostic**, not evaluative

### 3. Diagnostic Feedback

Never say "wrong." Say **what kind of wrong**.

**Examples:**
- ❌ "Incorrect" → ✅ "Your ordering suggests you understand the goal, but not the execution order."
- ❌ "Wrong answer" → ✅ "You're confusing correlation with causation."
- ❌ "Try again" → ✅ "This would work if the loop ran backwards. Check your range."

---

## Session Orchestration

Think **mission briefing**, not lesson plan.

### Session Structure (DARPA-Style)

#### 1. Goal Framing
> "After this, you should be able to reason about X under Y constraints."

**Example:**
```
┌───────────────────────────────────────────────────────────┐
│ Session Goal: OSPF Path Selection                         │
│                                                            │
│ After this session, you'll be able to:                    │
│ • Calculate OSPF cost for any interface                   │
│ • Predict best path given a topology                      │
│ • Troubleshoot neighbor adjacency issues                  │
│                                                            │
│ Estimated: 12 minutes │ 8 atoms                           │
└───────────────────────────────────────────────────────────┘
```

#### 2. Rapid Probe
1-2 low-cost atoms to estimate current state.

**Purpose:** Calibrate difficulty and detect existing knowledge.

**Example:**
```
Quick Check: What layer is OSPF in the TCP/IP model?

[ ] Application
[ ] Transport
[x] Network
[ ] Data Link

Result: ✓ Basic knowledge confirmed. Skipping fundamentals.
```

#### 3. Adaptive Core
Atom types selected **live** based on:
- **Error class** (misconception vs slip)
- **Latency** (fast wrong = guessing, slow wrong = overload)
- **Confidence mismatch** (high confidence + wrong = hypercorrection)

**Key Principle:**
> You do not repeat the same atom type twice in a row unless diagnosing.

#### 4. Stress Test
Transfer / edge case / failure mode to test application.

**Example:**
```
Scenario: Two OSPF routes have the same cost. What happens?

[Your answer]: _______________________________

This tests: Transfer to novel situation (not explicitly taught)
```

#### 5. Consolidation
One recall or explain-back atom to solidify learning.

**Example:**
```
Explain in your own words: Why does OSPF use cost instead of hop count?

[Your explanation]:
_________________________________________________
_________________________________________________
_________________________________________________
```

---

## Split-Pane Layouts

### Layout 1: Horizontal Split (Theory over Practice)

**Use Case:** Instructional content with practice area

```
┌─────────────────────────────────────────────────────────────────────┐
│ Cortex-CLI v2.0 │ Module 11: OSPF Routing │ Mastery: 67% ◑        │
├─────────────────────────────────────────────────────────────────────┤
│ LEARN PANE (40% height)                                             │
│                                                                      │
│ ## OSPF Path Selection                                              │
│                                                                      │
│ OSPF uses cost to determine best path. Cost = 10^8 / Bandwidth     │
│                                                                      │
│ Key Facts:                                                          │
│ • Lower cost = better path                                          │
│ • Cost is cumulative along the path                                 │
│ • Bandwidth-based by default (reference BW = 100 Mbps)              │
│                                                                      │
│ [Previous] [Next] [Test Me]                                         │
├─────────────────────────────────────────────────────────────────────┤
│ PRACTICE PANE (40% height)                                          │
│                                                                      │
│ >>> Calculate OSPF cost for a 10 Mbps link:                        │
│                                                                      │
│ Cost = 10^8 / BW                                                    │
│      = 100,000,000 / _________                                      │
│      = _________                                                    │
│                                                                      │
│ Your answer: [        ]                                             │
│                                                                      │
│ [Hint available: Press H] [Submit] [Skip]                           │
├─────────────────────────────────────────────────────────────────────┤
│ FEEDBACK PANE (20% height)                                          │
│ 🎯 Status: Waiting for your answer...                              │
└─────────────────────────────────────────────────────────────────────┘
```

**Advantages:**
- Natural reading flow (top to bottom)
- Reference material stays visible during practice
- Good for procedural learning

---

### Layout 2: Vertical Split (Side-by-side)

**Use Case:** Code examples alongside workspace

```
┌──────────────────────────────┬──────────────────────────────────┐
│ REFERENCE PANE (50% width)   │ WORKSPACE PANE (50% width)       │
│                              │                                  │
│ Example: Binary Search       │ Your Turn: Implement Binary      │
│                              │ Search                           │
│ def binary_search(arr, x):   │                                  │
│     left, right = 0, len(arr)│ def binary_search(arr, target):  │
│     while left <= right:     │     # TODO: Implement            │
│         mid = (left+right)//2│     _________________________    │
│         if arr[mid] == x:    │     _________________________    │
│             return mid       │     _________________________    │
│         elif arr[mid] < x:   │     _________________________    │
│             left = mid + 1   │     _________________________    │
│         else:                │                                  │
│             right = mid - 1  │                                  │
│     return -1                │                                  │
│                              │ Test Cases:                      │
│ Time Complexity: O(log n)    │ • search([1,3,5,7], 5) → 2      │
│ Space Complexity: O(1)       │ • search([1,3,5,7], 4) → -1     │
│                              │                                  │
│ [Scroll ↑↓]                  │ [Run Tests] [Submit]             │
├──────────────────────────────┴──────────────────────────────────┤
│ FEEDBACK & MASTERY TRACKER                                        │
│ ○ ○ ○ ● ● ● ○ ○  (3/8 atoms completed, 67% mastery)             │
└───────────────────────────────────────────────────────────────────┘
```

**Advantages:**
- Natural comparison (example vs your solution)
- More screen width for code
- Good for coding exercises

---

### Layout 3: 3-Pane (Advanced)

**Use Case:** Complex exercises with reference, workspace, and console

```
┌──────────────────────────────┬──────────────────────────────────┐
│ REFERENCE (40% width)        │ WORKSPACE (60% width)            │
│                              │                                  │
│ OSPF Commands Reference:     │ Router R1 Configuration:         │
│                              │                                  │
│ router ospf <process-id>     │ R1# configure terminal           │
│   network <ip> <wildcard>    │ R1(config)# router ospf 1        │
│     area <area-id>           │ R1(config-router)# network       │
│   router-id <id>             │   10.1.1.0 0.0.0.255 area 0      │
│                              │ R1(config-router)# _             │
│ show ip ospf neighbor        │                                  │
│ show ip ospf interface       │                                  │
│ show ip route ospf           │ Task:                            │
│                              │ Configure OSPF for network       │
│ [Scroll for more ↓]          │ 192.168.1.0/24 in area 1         │
│                              │                                  │
│                              │ [Submit] [Reset] [Hint]          │
├──────────────────────────────┴──────────────────────────────────┤
│ OUTPUT / FEEDBACK PANE                                            │
│                                                                   │
│ R1# show ip ospf neighbor                                        │
│                                                                   │
│ Neighbor ID     Pri   State       Dead Time   Address            │
│ 2.2.2.2         1     FULL/DR     00:00:35    10.1.1.2           │
│                                                                   │
│ ✓ Neighbor adjacency established! Cost calculation next...       │
└───────────────────────────────────────────────────────────────────┘
```

**Advantages:**
- Full context (reference + workspace + output)
- Professional development environment feel
- Good for CLI/terminal exercises

---

### Layout 4: Full-Screen Immersive

**Use Case:** Code debugging, deep focus tasks

```
┌───────────────────────────────────────────────────────────────────┐
│ Debug Challenge: Fix the Infinite Loop                            │
├───────────────────────────────────────────────────────────────────┤
│                                                                    │
│  1  def countdown(n):                                             │
│  2      while n > 0:                                              │
│  3          print(n)                                              │
│  4          n + 1  # Bug is here                                  │
│  5      print("Done!")                                            │
│  6                                                                 │
│  7  countdown(5)                                                  │
│                                                                    │
│ Problem: This code runs forever. Fix line 4.                      │
│                                                                    │
│ Your fix: n + 1 → [_____________]                                 │
│                                                                    │
│                                                                    │
│ Confidence: ○ Low  ○ Medium  ● High                               │
│                                                                    │
│ [Submit Fix]  [Skip]  [Explain the Bug]                           │
│                                                                    │
├───────────────────────────────────────────────────────────────────┤
│ Progress: [████████░░] 8/10 atoms │ Time: 4m 32s │ Focus: High   │
└───────────────────────────────────────────────────────────────────┘
```

**Advantages:**
- Zero distraction
- Full focus on the problem
- Good for high-difficulty atoms

---

## Feedback & Cognition Layer

This is where DARPA/Knewton differed from normal edtech.

### Feedback is Typed, Not Generic

Each response produces:

1. **Outcome:** correct / incorrect / partial
2. **Error class:**
   - `misconception` - Fundamental misunderstanding
   - `slip` - Minor mistake (typo, off-by-one)
   - `missing_prerequisite` - Lacks foundation knowledge
   - `execution_failure` - Knows what to do, can't execute

3. **Cognitive signal:**
   - Fast & Wrong → Guessing
   - Slow & Wrong → Cognitive overload
   - Fast & Right → Mastery candidate

### Feedback Presentation Rules

1. **Never say "wrong"**
2. **Say what kind of wrong**
3. **Show one corrective insight only**
4. **Delay full explanation until learner commits again**

**Example:**

```
┌───────────────────────────────────────────────────────────────────┐
│ Your answer: 64                                                    │
│ Correct answer: 10                                                │
│                                                                    │
│ ⚠️ Error Class: Formula Confusion                                 │
│                                                                    │
│ You used 10^8 / 10^6 = 100, then divided by some factor.          │
│ It looks like you might be confusing OSPF cost with EIGRP metric. │
│                                                                    │
│ OSPF cost = 10^8 / bandwidth_in_bps                               │
│           = 100,000,000 / 10,000,000                               │
│           = 10                                                     │
│                                                                    │
│ Next: I'll show you an EIGRP vs OSPF comparison to clarify.       │
│                                                                    │
│ [Continue] [Add to Review Queue] [Explain More]                   │
└───────────────────────────────────────────────────────────────────┘
```

---

## Presentation Modes

### What the Learner Sees vs What the System Knows

| Internal Atom Type | Learner-Visible Form |
|--------------------|----------------------|
| MCQ | "Choose the best explanation" |
| Parsons | "Reconstruct the solution" |
| Numeric | "Compute the result" |
| Matching | "Connect the concepts" |
| Debugging | "Something is broken—find it" |
| Design | "Pick the best approach under constraints" |
| Recall | "Explain from memory" |
| Meta-cognitive | "How confident are you?" |

---

## Macro-Presentation

This is where most systems fail.

### Learner Sees:

1. **Capabilities, not topics**
   - "Can reason about TCP state transitions"
   - "Can debug OSPF neighbor issues"
   - "Can calculate subnet masks"

2. **Confidence bands, not grades**
   ```
   TCP Fundamentals    [████████░░] 80% ± 15%
   OSPF Routing        [██████░░░░] 60% ± 20%
   Subnetting          [██████████] 95% ± 5%
   ```

3. **Decay warnings**
   - "TCP handshake knowledge is likely to decay in ~12 days"
   - "Schedule a review session to maintain mastery"

### Instructor / System Sees:

1. **Atom effectiveness by learner**
   - "Parsons problems are 2x more effective than MCQ for this learner"

2. **Error topology maps**
   - "Clusters of 'order-of-operations' errors in subnetting"

3. **Transfer success rates**
   - "Can apply OSPF cost to new topologies: 75%"

4. **Cognitive load indicators**
   - "Session cognitive load: Moderate (optimal)"
   - "Atom 5 caused spike → reduce complexity"

---

## Implementation Approach

### Technology Stack Options

#### Option 1: Textual (Recommended)
**Pros:**
- Modern, reactive framework
- Widget composition
- CSS-like styling
- Live reload during development

**Cons:**
- Newer, smaller ecosystem

#### Option 2: Rich
**Pros:**
- Mature, stable
- Excellent rendering (tables, code syntax)
- More low-level control

**Cons:**
- Less structured for complex UIs
- More manual event handling

#### Option 3: Blessed / Urwid
**Pros:**
- Very mature
- Large ecosystems

**Cons:**
- Python 2 legacy baggage (Urwid)
- Less modern patterns

### Recommended: Textual

**Rationale:**
- Best fit for split-pane, reactive UI
- Good documentation
- Active development
- Python 3.7+ native

---

## One Non-Negotiable Rule (DARPA Insight)

> **You never teach and test at the same time.**

**Teaching atoms** → examples, scaffolds, guided builds
**Testing atoms** → no hints, no scaffolds, no cues

The system switches modes explicitly, even if the learner doesn't notice.

**Example State Machine:**

```
State: TEACHING
  → Show worked example
  → Provide scaffold (Parsons)
  → Offer hints
  ↓
  Learner shows understanding (2/2 correct)
  ↓
State: TRANSITION
  → Faded scaffold (partial Parsons)
  → Optional hints
  ↓
  Learner maintains performance
  ↓
State: TESTING
  → No scaffold (free recall)
  → No hints (maybe 1 after failure)
  → Measure true capability
```

---

## Next Implementation Steps

### Phase 1: TUI Foundation (Weeks 1-2)
1. ✅ Install Textual framework
2. ⬜ Implement basic split-pane layout (horizontal)
3. ⬜ Create atom renderer (MCQ, Short Answer, Cloze)
4. ⬜ Implement keyboard navigation

### Phase 2: Interactive Study Mode (Weeks 3-4)
5. ⬜ Guided practice mode (not just flashcard review)
6. ⬜ Live code execution sandbox (Python/bash/SQL)
7. ⬜ Session state management (save/resume)
8. ⬜ Feedback rendering with error class display

### Phase 3: Intelligence Layer (Weeks 5-6)
9. ⬜ Cognitive load detection (time-on-task, retries)
10. ⬜ Confidence mismatch detection (hypercorrection)
11. ⬜ Adaptive atom selection (Z-Score + error history)
12. ⬜ Session recording (cognitive flow analysis)

---

## Related Documents

- [Vision: DARPA Digital Tutor](vision-darpa-tutor.md)
- [Learning Atoms Reference](../reference/learning-atoms.md)
- [Scientific Foundations](../reference/scientific-foundations.md)

---

**Status:** Design Document (Living Document)
**Last Updated:** 2025-12-21
**Authors:** Project Astartes Team
