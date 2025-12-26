Feature: Variation Theory and Conceptual Discernment

  Scenario: Discerning a concept with examples and non-examples
    Given a concept "prime number"
    When the learner is presented with an example "2"
    And the learner is presented with an example "3"
    And the learner is presented with a non-example "4"
    Then the learner should be able to discern the critical features of the concept

  Scenario: Discerning a concept with multiple examples and non-examples
    Given a concept "even number"
    When the learner is presented with an example "2"
    And the learner is presented with an example "4"
    And the learner is presented with a non-example "1"
    And the learner is presented with a non-example "3"
    Then the learner should be able to discern the critical features of the concept
