Feature: CCNA atom schema and quality validation
  Background:
    Given the atom deck is loaded

  Scenario Outline: Atom meets learnability schema and validation gates
    Given an atom with id "<atom_id>"
    Then the atom has required fields id, atom_type, front
    And the atom has metadata difficulty in [1..5]
    And the atom has a non-empty source reference excerpt
    And the atom validation score is >= <min_score>
    And the atom validation passed flag is true

    Examples:
      | atom_id         | min_score |
      | SAMPLE-MCQ-001  | 75        |
      | SAMPLE-ORDER-01 | 75        |

  Scenario: CCNA notation validators catch malformed values
    Given an atom about "IP-Addressing"
    When the back contains an invalid IP or CIDR
    Then the validator marks it invalid with a notation error
