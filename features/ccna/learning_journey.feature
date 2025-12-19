Feature: CCNA learning journey respects prerequisites and provides remediation
  Background:
    Given a user "alice" starts a new CCNA session for module 1
    And the atom deck is loaded with learnable-ready atoms

  Scenario: Prerequisite gating and mastery unlock
    When Alice requests the next atom
    Then she is given an atom whose prerequisites are all mastered
    When she answers correctly three times without hints
    Then the sequencer marks the atom as mastered
    And the next atom increases in difficulty within the same objective cluster

  Scenario: Remediation after repeated failure
    Given Alice answered atom "CIDR-Calc-01" incorrectly twice
    When she requests the next atom
    Then the sequencer serves a prerequisite refresher for "Binary-Subnet-Basics"
    And also queues a similar easier atom from the same cluster
    And the UI shows a hint before the next attempt
