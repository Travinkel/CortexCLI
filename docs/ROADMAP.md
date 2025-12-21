# Cortex-CLI Roadmap: DARPA Digital Tutor Implementation

**Vision:** Build a terminal-based adaptive learning system that rivals DARPA's Digital Tutor and Knewton's adaptive engine.

**Status:** Foundation complete, TUI implementation phase starting

**Last Updated:** 2025-12-21

---

## Current State (v1.0 - Baseline)

### ✅ Completed Foundation

#### Core Learning Engine
- [x] FSRS spaced repetition algorithm
- [x] Z-Score prioritization (decay, centrality, project, novelty)
- [x] Mastery calculation (review + quiz weighted)
- [x] Prerequisite graph (Force Z backtracking)
- [x] Cognitive diagnosis (struggle detection)

#### Data Infrastructure
- [x] PostgreSQL database with full schema
- [x] Notion sync (ETL pipeline for content authoring)
- [x] Anki bidirectional sync
- [x] Semantic embeddings (duplicate detection, prerequisite inference)
- [x] Neo4j shadow graph (graph algorithms)

#### Content Management
- [x] Flashcard atoms (basic Q&A)
- [x] Multiple choice questions
- [x] Cloze deletions
- [x] Parsons problems (code ordering)
- [x] Content validation pipeline
- [x] Atomicity quality grading (A-F scale)

#### API Layer
- [x] FastAPI REST endpoints
- [x] Sync operations (Notion, Anki)
- [x] Adaptive session management
- [x] Quiz generation and grading
- [x] Semantic search and deduplication

#### CLI (Basic)
- [x] Study mode (flashcard review)
- [x] Stats display
- [x] Curriculum import
- [x] Queue visualization
- [x] Focus Stream (Z-Score based selection)

---

## Phase 1: TUI Foundation (Weeks 1-2)

**Goal:** Replace basic CLI with split-pane interactive interface

### Objectives

#### 1.1 Install Textual Framework
- [ ] Add `textual` to dependencies
- [ ] Set up hot reload for development
- [ ] Create basic app skeleton
- [ ] Test rendering on Windows/Linux/macOS

#### 1.2 Implement Split-Pane Layouts
- [ ] Horizontal split (Theory over Practice)
- [ ] Vertical split (Side-by-side)
- [ ] 3-pane layout (Reference + Workspace + Feedback)
- [ ] Full-screen immersive mode
- [ ] Layout switching (keyboard shortcuts)

#### 1.3 Atom Renderers
- [ ] **MCQ Renderer** - Radio buttons, distractor highlighting
- [ ] **Short Answer Renderer** - Text input with fuzzy matching
- [ ] **Cloze Renderer** - Fill-in-the-blank with context
- [ ] **Parsons Renderer** - Drag-and-drop code blocks
- [ ] **Numeric Renderer** - Number input with unit selection
- [ ] **Confidence Rating Widget** - Likert scale (1-5)

#### 1.4 Keyboard Navigation
- [ ] Tab between panes
- [ ] Arrow keys for selection
- [ ] Enter to submit
- [ ] `H` for hint
- [ ] `S` to skip
- [ ] `E` to explain
- [ ] `Q` to quit session

**Deliverable:** Working TUI that can render basic atoms (MCQ, Short Answer, Cloze) in split-pane layout.

---

## Phase 2: Interactive Study Mode (Weeks 3-4)

**Goal:** Transform from passive flashcard review to active guided practice

### Objectives

#### 2.1 Session Orchestration
- [ ] **Goal Framing** - Display session objectives
- [ ] **Rapid Probe** - 1-2 calibration questions
- [ ] **Adaptive Core** - Real-time difficulty adjustment
- [ ] **Stress Test** - Transfer/edge case challenges
- [ ] **Consolidation** - End-of-session recall

#### 2.2 Live Code Execution
- [ ] **Python Sandbox** - Execute user code with timeout
- [ ] **Bash Sandbox** - Safe command execution (whitelist)
- [ ] **SQL Sandbox** - SQLite query execution
- [ ] **Unit Test Runner** - Auto-grade code submissions
- [ ] **Performance Constraints** - Big-O enforcement

#### 2.3 CLI Simulation
- [ ] **Terminal Emulator** - Simulate Cisco/Linux CLI
- [ ] **Stateful Commands** - Track exec vs config mode
- [ ] **Output Validation** - Check `show` command results
- [ ] **Network Topology Sim** - OSPF, EIGRP, VLANs

#### 2.4 Session State Management
- [ ] **Auto-save** - Every 5 atoms or 2 minutes
- [ ] **Resume** - Pick up where you left off
- [ ] **Progress Bar** - Atoms completed / total
- [ ] **Time Tracking** - Session duration, time per atom
- [ ] **Export Session** - Save for analysis

**Deliverable:** Full study session that guides learner through goal → probe → core → stress → consolidation with live code execution.

---

## Phase 3: Intelligence Layer (Weeks 5-6)

**Goal:** Implement cognitive diagnosis and adaptive selection

### Objectives

#### 3.1 Cognitive Load Detection
- [ ] **Time-on-Task Tracking** - Detect slow/fast responses
- [ ] **Retry Counter** - Track attempts per atom
- [ ] **Latency Analysis** - Fast wrong = guess, slow wrong = overload
- [ ] **Cognitive Load Index** - Real-time session difficulty score
- [ ] **Adaptive Difficulty** - Increase/decrease based on load

#### 3.2 Confidence Mismatch Detection
- [ ] **Pre-Answer Confidence** - Capture before attempt
- [ ] **Post-Answer Confidence** - Capture after attempt
- [ ] **Hypercorrection Trigger** - High confidence + wrong = intervention
- [ ] **Calibration Tracking** - Confidence vs accuracy over time
- [ ] **Metacognitive Feedback** - "You tend to overestimate on X topics"

#### 3.3 Enhanced Atom Selection
- [ ] **Error History Integration** - Boost atoms related to past errors
- [ ] **Interleaving Enforcement** - Never same type twice
- [ ] **Atom Type Effectiveness** - Track ROI per learner
- [ ] **Prerequisite-Aware Selection** - Don't show before prereqs met
- [ ] **Transfer Testing** - Inject novel scenarios periodically

#### 3.4 Session Recording & Analysis
- [ ] **Event Stream** - Log every interaction (JSON Lines)
- [ ] **Error Topology Maps** - Cluster similar errors
- [ ] **Cognitive Flow Graphs** - Visualize learning trajectory
- [ ] **Struggle Zone Identification** - Auto-detect weak areas
- [ ] **Export for Research** - Anonymized data for analysis

**Deliverable:** Fully adaptive system that diagnoses learner state and adjusts in real-time.

---

## Phase 4: Enhanced Atom Types (Weeks 7-8)

**Goal:** Implement advanced atom types for expert-level assessment

### Objectives

#### 4.1 Debugging Challenges
- [ ] **Spot the Bug** - Highlight incorrect line
- [ ] **Root Cause Analysis** - Explain why it fails
- [ ] **Minimal Fix** - Smallest change to correct
- [ ] **Error Message Interpretation** - Decode compiler errors
- [ ] **Log Analysis** - Diagnose from stack traces

#### 4.2 Design & Architecture
- [ ] **Trade-off Analysis** - Compare approaches
- [ ] **Component Responsibility** - "Which layer does X?"
- [ ] **Failure Mode Prediction** - "What breaks if X fails?"
- [ ] **Scalability Reasoning** - "How does this scale?"
- [ ] **Security Boundary ID** - "Where should validation occur?"

#### 4.3 System Simulation
- [ ] **What Happens If** - Scenario prediction
- [ ] **State Simulation** - Step through execution
- [ ] **Failure Injection** - "What if this service dies?"
- [ ] **Concurrency Reasoning** - Race condition detection
- [ ] **Performance Impact** - "How does X affect latency?"

#### 4.4 Creative & Transfer
- [ ] **Generate Example** - "Give an example of X"
- [ ] **Generate Counterexample** - "When does this NOT work?"
- [ ] **Create Analogy** - "What is X like?"
- [ ] **Design Test Case** - "How would you test this?"
- [ ] **Propose Alternative** - "What's another way?"

**Deliverable:** Full suite of 80+ atom types implemented and tested.

---

## Phase 5: Greenlight Integration (Weeks 9-10)

**Goal:** Auto-generate remediation atoms from real coding struggles

### Objectives

#### 5.1 Error Detection API
- [ ] **Watch File System** - Monitor test runs
- [ ] **Parse Test Failures** - Extract error class
- [ ] **Classify Error** - Syntax, logic, conceptual
- [ ] **Pattern Matching** - Detect repeated mistakes
- [ ] **Confidence Inference** - Time-to-fix = confidence proxy

#### 5.2 Atom Generation
- [ ] **Template System** - Error → Atom mapping
- [ ] **Distractor Engineering** - Generate plausible wrong answers
- [ ] **Difficulty Calibration** - Match current mastery level
- [ ] **Tag with Error Class** - Link back to original failure
- [ ] **Priority Boost** - High Z-Score for immediate review

#### 5.3 Feedback Loop
- [ ] **IDE Plugin Communication** - Local API or file-based
- [ ] **Real-time Sync** - Push atoms to Cortex-CLI queue
- [ ] **Progress Reporting** - "You've mastered async/await!"
- [ ] **Decay Detection** - "You haven't used regex in 3 weeks"
- [ ] **Proactive Review** - "Quick refresh on X before coding"

**Deliverable:** Seamless integration where coding errors automatically become learning atoms.

---

## Phase 6: Right-Learning Integration (Weeks 11-12)

**Goal:** Bi-directional sync with web platform

### Objectives

#### 6.1 API Client
- [ ] **Authentication** - JWT token management
- [ ] **Profile Sync** - Download user mastery state
- [ ] **Atom Sync** - Pull latest curriculum
- [ ] **Progress Upload** - Push local study sessions
- [ ] **Conflict Resolution** - Handle offline edits

#### 6.2 Export/Import
- [ ] **Full Export** - Profile + due cards for offline
- [ ] **Selective Export** - Specific courses/modules
- [ ] **Import with Merge** - Combine offline progress
- [ ] **Validation** - Verify data integrity
- [ ] **Rollback** - Undo bad imports

#### 6.3 Content Pipeline
- [ ] **Validate** - Check atom quality before upload
- [ ] **Deduplicate** - Semantic similarity matching
- [ ] **Enrich** - Add embeddings, prerequisites
- [ ] **Ingest** - Bulk upload to Right-Learning
- [ ] **CI/CD Integration** - Run in GitHub Actions

**Deliverable:** Cortex-CLI as both standalone tool and Right-Learning client.

---

## Phase 7: Polish & Launch (Weeks 13-14)

**Goal:** Production-ready release

### Objectives

#### 7.1 Performance Optimization
- [ ] **Database Indexing** - Query optimization
- [ ] **Caching** - Redis for frequent queries
- [ ] **Lazy Loading** - Load atoms on demand
- [ ] **Background Jobs** - Async embedding generation
- [ ] **Profiling** - Identify bottlenecks

#### 7.2 User Experience
- [ ] **Onboarding Tutorial** - First-time user guide
- [ ] **Keyboard Shortcuts Help** - `?` key overlay
- [ ] **Theme Support** - Light/dark/custom
- [ ] **Accessibility** - Screen reader support
- [ ] **Error Messages** - User-friendly, actionable

#### 7.3 Documentation
- [ ] **User Guide** - Getting started, workflows
- [ ] **API Documentation** - OpenAPI spec
- [ ] **Architecture Diagrams** - System overview
- [ ] **Video Tutorials** - YouTube walkthroughs
- [ ] **Scientific FAQ** - "Why these features?"

#### 7.4 Testing & QA
- [ ] **Unit Tests** - 80%+ coverage
- [ ] **Integration Tests** - End-to-end scenarios
- [ ] **Performance Tests** - Load testing
- [ ] **User Acceptance** - Beta tester feedback
- [ ] **Security Audit** - Code review, dependency scan

**Deliverable:** v2.0 release with full DARPA Digital Tutor feature set.

---

## Success Metrics

### Learning Effectiveness
- **Retention Rate:** 90%+ at 30 days (vs 70% baseline)
- **Transfer Success:** 75%+ on novel scenarios
- **Mastery Velocity:** 2x faster than passive study
- **Confidence Calibration:** <10% mismatch (confidence vs accuracy)

### User Experience
- **Session Completion:** 85%+ finish rate
- **Daily Active Users:** 60%+ return next day
- **Net Promoter Score:** >50
- **Time to Mastery:** 50% reduction vs traditional methods

### Technical Performance
- **Latency:** <100ms atom rendering
- **Uptime:** 99.9% API availability
- **Data Sync:** <5 sec round-trip
- **Offline Support:** Full functionality without network

---

## Future Enhancements (v3.0+)

### Advanced Features
- [ ] **Spaced Repetition Optimizer** - Auto-tune FSRS parameters
- [ ] **Peer Learning** - Collaborative study sessions
- [ ] **Instructor Dashboard** - Class-wide analytics
- [ ] **Mobile Companion** - iOS/Android app
- [ ] **Voice Interface** - Hands-free study mode

### Content Expansion
- [ ] **More Domains** - Math, Physics, Languages
- [ ] **Video Integration** - Annotated video lessons
- [ ] **Interactive Diagrams** - Zoomable, clickable
- [ ] **AR/VR Experiments** - 3D visualization
- [ ] **Game-ification** - Leaderboards, achievements

### Research Features
- [ ] **A/B Testing Framework** - Test learning strategies
- [ ] **Academic Partnerships** - Publish research
- [ ] **Open Dataset** - Anonymized learning data
- [ ] **ML Model Training** - Personalized difficulty prediction
- [ ] **Neuroscience Integration** - EEG/fMRI correlation

---

## Contributing

We welcome contributions! Focus areas:

1. **Atom Type Implementations** - See `src/atoms/handlers/`
2. **TUI Widgets** - See `src/tui/components/`
3. **Scientific Research** - Add citations to `docs/reference/scientific-foundations.md`
4. **Content Pipelines** - New import sources (Obsidian, Roam, etc.)
5. **Translations** - i18n support for global learners

See `CONTRIBUTING.md` for guidelines.

---

## References

- [Vision: DARPA Digital Tutor](explanation/vision-darpa-tutor.md)
- [Learning Atoms Taxonomy](reference/learning-atoms.md)
- [Scientific Foundations](reference/scientific-foundations.md)
- [TUI Design](explanation/tui-design.md)
- [Architecture](explanation/architecture.md)

---

**Next Review:** End of Phase 1 (Week 2)
**Team:** Project Astartes
**License:** MIT
