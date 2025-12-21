Feature: CCNA sequencing and remediation adapt to learner struggles
  Background:
    Given a user "bob" has an ongoing CCNA session
    And the atom deck is loaded with learnable-ready atoms

  Scenario: Similarity-based remediation after repeated failure
    Given Bob failed atom "Switching-VLAN-Intro-01" twice
    When he requests the next atom
    Then the sequencer includes a prerequisite refresher atom
    And also includes a nearest-neighbor easier atom from the same cluster
    And the remediation atom shows a hint before answer submission

  Scenario: Spaced repetition injects scheduled reviews
    Given Bob mastered 3 atoms yesterday
    When he resumes the session
    Then the sequencer inserts due review atoms before introducing new content
