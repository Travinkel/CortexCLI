# tests/features/worked_example.feature
Feature: Worked-Example Effect and Completion Problems
  As a Learning Scientist
  I want to use "Worked Examples" and "Completion Problems" to reduce cognitive load during initial skill acquisition
  So that the learner can focus on schema construction before being overwhelmed by full problem solving

  Scenario: Displaying a Worked Example
    Given the CLI is invoked with the "worked-example" command
    When the user requests a worked example for "algebra"
    Then the CLI should display a step-by-step solution for an algebra problem

  Scenario: Displaying a Completion Problem
    Given the CLI is invoked with the "completion-problem" command
    When the user requests a completion problem for "calculus"
    Then the CLI should display a partial solution for a calculus problem, with steps for the user to complete
