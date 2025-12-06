Feature: Neuro-Cognitive Failure Diagnosis
  As the Cortex Adaptive Engine
  I want to classify learner errors based on keystroke dynamics, response time, and semantic topology
  So that I can trigger the correct neurological remediation strategy (Force Z, Lures, or Rest).

  Background:
    Given the learner "Ramanujan_01" has a "High" processing speed
    And the current Learning Atom is "Definition of Uniform Continuity"
    And the "Pattern Separation Index" (PSI) between "Uniform Continuity" and "Pointwise Continuity" is 0.85

  # ==========================================================================
  # HIPPOCAMPAL PATTERN SEPARATION (Dentate Gyrus / CA3)
  # ==========================================================================

  @hippocampus @pattern_separation @critical
  Scenario: Detecting a Hippocampal Discrimination Error
    # The Dentate Gyrus performs pattern separation - distinguishing between
    # similar memory traces. When PSI is high (>0.7), items are semantically
    # close and prone to interference. If the learner selects a lure that
    # matches a confusable item, it indicates DG orthogonalization failure.
    # Reference: Norman & O'Reilly (2003) - Hippocampal Pattern Separation
    Given the learner has previously mastered "Pointwise Continuity"
    When the learner answers "Incorrect" to "Definition of Uniform Continuity"
    And the response matches the "Pointwise Continuity" lure
    Then the system should diagnose a "DISCRIMINATION_ERROR"
    And the remediation strategy should be "CONTRASTIVE_LURE_TRAINING"
    And the log should cite mechanism "Dentate Gyrus Orthogonalization Failure"

  @hippocampus @encoding
  Scenario: Detecting an Encoding Error (Never Consolidated)
    # When stability is low (<7 days) and review count is insufficient (<3),
    # the trace was never properly consolidated in CA3/CA1.
    Given the Learning Atom has stability of 2 days
    And the Learning Atom has 1 review
    When the learner answers "Incorrect"
    Then the system should diagnose an "ENCODING_ERROR"
    And the remediation strategy should be "READ_SOURCE"
    And the explanation should mention "re-read" or "source material"

  @hippocampus @retrieval
  Scenario: Detecting a Retrieval Error (Forgotten)
    # High stability but failed retrieval suggests the trace exists but
    # the retrieval cue failed (CA3 pattern completion failure).
    Given the Learning Atom has stability of 30 days
    And the Learning Atom has 8 reviews
    When the learner answers "Incorrect"
    And the response time is 6000ms
    Then the system should diagnose a "RETRIEVAL_ERROR"
    And the remediation strategy should be "SPACED_REPEAT"

  # ==========================================================================
  # P-FIT INTEGRATION (Parieto-Frontal Network)
  # ==========================================================================

  @pfit @integration
  Scenario: Detecting a P-FIT Integration Error
    # P-FIT (Parieto-Frontal Integration Theory) describes intelligence as
    # the efficiency of communication between parietal (visuospatial) and
    # frontal (executive/symbolic) regions. Tasks requiring translation
    # between visual and symbolic representations stress this network.
    # Reference: Jung & Haier (2007) - P-FIT Model
    Given the Learning Atom requires "Visual-Symbolic" translation
    And the Learning Atom has pfit_index of 0.85
    When the learner answers "Incorrect"
    And the learner spent > 5000ms in the "Parietal" visual state
    But failed to produce the "Frontal" symbolic output
    Then the system should diagnose an "INTEGRATION_ERROR"
    And the remediation strategy should be "WORKED_EXAMPLE_SCAFFOLDING"

  @pfit @procedural
  Scenario: Detecting Integration Error on Procedural Atoms
    # Parsons problems and numeric calculations require step-by-step
    # integration of multiple facts - a P-FIT intensive operation.
    Given the Learning Atom is of type "parsons"
    When the learner answers "Incorrect"
    And the response time is 8000ms
    Then the system should diagnose an "INTEGRATION_ERROR"
    And the remediation strategy should be "WORKED_EXAMPLE"

  # ==========================================================================
  # PREFRONTAL CORTEX (Executive Function)
  # ==========================================================================

  @pfc @executive_function
  Scenario: Detecting an Executive Control Failure (Impulsivity)
    # Fast errors (<1500ms) indicate System 1 heuristic thinking without
    # engaging deeper processing. The PFC failed to inhibit the impulse.
    Given the learner has adequate knowledge of the topic
    When the learner answers "Incorrect"
    And the "Time to First Action" is < 1500ms
    Then the system should diagnose an "EXECUTIVE_ERROR"
    And the remediation strategy should be "SLOW_DOWN"
    And the explanation should mention "read carefully"

  @pfc @fatigue
  Scenario: Detecting an Executive Control Failure (Fatigue)
    # Cognitive fatigue depletes prefrontal resources. Fast errors with
    # high fatigue vectors indicate depleted executive control.
    Given the learner's "Fatigue Vector" is > 0.7
    When the learner answers "Incorrect"
    And the "Time to First Action" is < 400ms
    Then the system should diagnose an "EXECUTIVE_ERROR"
    And the system should trigger "INCUBATION_PERIOD"

  @pfc @fatigue @session
  Scenario: Detecting Fatigue from Session Duration
    # After 45+ minutes of study, cognitive resources are depleted
    # regardless of individual error patterns.
    Given the session has been running for 50 minutes
    And the learner has made 5 consecutive errors
    When the learner answers "Incorrect"
    Then the system should diagnose a "FATIGUE_ERROR"
    And the remediation strategy should be "REST"
    And the recommended break should be at least 10 minutes

  # ==========================================================================
  # SUCCESS CLASSIFICATION
  # ==========================================================================

  @success @fluency
  Scenario: Detecting Perceptual Fluency (Automaticity)
    # Response times <2000ms with correct answers indicate the knowledge
    # has been proceduralized - it's automatic and effortless.
    When the learner answers "Correct" to the Learning Atom
    And the response time is 800ms
    Then the system should classify success as "FLUENCY"
    And the remediation strategy should be "ACCELERATE"

  @success @recall
  Scenario: Detecting Successful Free Recall
    # Standard successful retrieval with normal response time.
    Given the Learning Atom is of type "flashcard"
    When the learner answers "Correct"
    And the response time is 4000ms
    Then the system should classify success as "RECALL"
    And the cognitive state should be "FLOW"

  @success @inference
  Scenario: Detecting Successful Inference
    # Success on integration-heavy tasks indicates P-FIT network is
    # functioning well - facts are being connected into understanding.
    Given the Learning Atom is of type "numeric"
    And the Learning Atom has pfit_index of 0.8
    When the learner answers "Correct"
    And the response time is 6000ms
    Then the system should classify success as "INFERENCE"
    And the explanation should mention "connecting facts"

  # ==========================================================================
  # COGNITIVE LOAD MANAGEMENT
  # ==========================================================================

  @cognitive_load @critical
  Scenario: Detecting Critical Cognitive Overload
    # When total cognitive load exceeds working memory capacity,
    # learning fails. System must intervene before this happens.
    # Reference: Sweller (1988) - Cognitive Load Theory
    Given the intrinsic load of the current atom is 0.7
    And the session has been running for 40 minutes
    And the learner has made 3 consecutive errors
    When the cognitive load is computed
    Then the load level should be "high" or "critical"
    And the system should recommend reducing difficulty or taking a break

  # ==========================================================================
  # PLM (PERCEPTUAL LEARNING MODULE)
  # ==========================================================================

  @plm @fluency_training
  Scenario: Recommending PLM Training for Slow-but-Accurate Learner
    # PLMs train rapid categorization (<1000ms). If a learner is accurate
    # but slow, they need PLM training to achieve automaticity.
    # Reference: Kellman & Garrigan (2009) - Perceptual Learning
    Given the learner has 80% accuracy on "Trig Identities"
    But average response time is 4000ms
    When perceptual fluency is analyzed
    Then the PLM result should indicate "needs_plm_training" is true
    And the recommendation should mention "rapid discrimination"

  @plm @achieved
  Scenario: Confirming Perceptual Fluency Achieved
    # Fluency is achieved when >80% of responses are under target time
    # with >90% accuracy.
    Given the learner has 95% accuracy on "Trig Identities"
    And 85% of responses are under 1000ms
    When perceptual fluency is analyzed
    Then the PLM result should indicate "is_fluent" is true
    And the recommendation should mention "increasing difficulty"

  # ==========================================================================
  # FORCE Z (PREREQUISITE BACKTRACKING)
  # ==========================================================================

  @force_z @prerequisites
  Scenario: Triggering Force Z Backtrack
    # When prerequisite mastery is below threshold (65%), the system
    # must backtrack to the prerequisite before continuing.
    Given the learner attempts "Integration by Parts"
    And the prerequisite "Product Rule" has mastery of 0.40
    When the system checks prerequisites
    Then a Force Z event should be triggered
    And the target should be "Product Rule"
    And the explanation should mention "prerequisite" or "foundation"

  # ==========================================================================
  # STRUGGLE PATTERN DETECTION
  # ==========================================================================

  @struggle @critical
  Scenario: Detecting Critical Struggle Pattern
    # When failure rate exceeds 60% on a concept, the system must
    # stop quizzing and redirect to source material.
    Given the learner has failed 4 out of 5 recent attempts on "Epsilon-Delta Proofs"
    When the struggle pattern is analyzed
    Then a struggle pattern should be detected
    And the priority should be "critical"
    And the recommendation should mention "stop" and "re-read"

  # ==========================================================================
  # REWARD FUNCTION (HRL SCHEDULER)
  # ==========================================================================

  @hrl @reward
  Scenario: Computing Learning Reward in Flow State
    # The HRL scheduler optimizes for:
    # R_t = w1*ΔKnowledge + w2*FluencyScore - w3*FatiguePenalty - w4*OffloadingPenalty
    # Flow state provides a 10% bonus.
    Given the diagnosis shows cognitive state "FLOW"
    And delta_knowledge is 0.5
    And fluency_score is 0.6
    And fatigue_level is 0.2
    And offloading was not detected
    When the learning reward is computed
    Then the reward should be greater than 0.3
    And the reward should include a flow bonus

  @hrl @penalty
  Scenario: Penalizing Cognitive Offloading
    # When the learner relies too heavily on hints, they're offloading
    # cognitive work to the system. This must be penalized.
    Given the diagnosis shows cognitive state "FLOW"
    And delta_knowledge is 0.5
    And fluency_score is 0.6
    And fatigue_level is 0.1
    And offloading was detected
    When the learning reward is computed
    Then the reward should be reduced by the offloading penalty
    And the penalty weight should be 0.3
