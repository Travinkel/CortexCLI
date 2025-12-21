# Feature: Quiz Quality Assurance
#
# Learning Activity Types (15 types across 5 mechanisms):
#   - Retrieval (d=0.7): flashcard, cloze, mcq, true_false, short_answer
#   - Generation (d=0.5): explain, compare, parsons
#   - Elaboration (d=0.6): prediction, problem
#   - Discrimination (d=0.6): matching, ranking
#   - Application (d=0.5): sequence, project, passage_based
#
# Quality Grades (A-F):
#   - A: 0.90+ (Excellent)
#   - B: 0.75-0.89 (Good)
#   - C: 0.60-0.74 (Acceptable)
#   - D: 0.40-0.59 (Needs Improvement)
#   - F: <0.40 (Failing)
#
# Evidence-Based Thresholds:
#   - Question length: 8-15 words optimal
#   - Answer length: 1-5 words optimal
#   - MCQ options: 3-6 (4 optimal)
#   - Matching pairs: 4-6 max
#   - Ranking items: 3-7 items
#
# See: enhanced-cognition/right-learning for learning science research

Feature: Quiz Quality Assurance

  As a content creator, I want my quiz questions analyzed for quality,
  so I can create effective assessments that support learning.

  As the system, I want to enforce quality standards across question types,
  so learners receive well-designed questions that support retention.

  As a reviewer, I want quality metrics and grades for questions,
  so I can prioritize improvement efforts.

  Background:
    Given a PostgreSQL database with quiz_questions and clean_atoms
    And the quality analyzer is initialized
    And evidence-based thresholds are configured:
      | Metric               | Min    | Optimal | Max    |
      | question_length      | 5      | 8-15    | 30     |
      | answer_length        | 1      | 1-5     | 20     |
      | mcq_options          | 3      | 4       | 6      |
      | matching_pairs       | 2      | 4-5     | 6      |
      | ranking_items        | 3      | 4-5     | 7      |
      | parsons_blocks       | 3      | 5-8     | 12     |
      | passage_length       | 50     | 150-300 | 500    |

  # ========================================
  # MCQ (MULTIPLE CHOICE QUESTION)
  # Learning Mechanism: Retrieval (d=0.7)
  # ========================================

  Scenario: Analyze high-quality MCQ question
    Given an MCQ question:
      | front   | What is the primary function of TCP? |
      | correct | Reliable data transmission           |
      | options | ["Reliable data transmission", "Fast data routing", "IP address assignment", "Packet encryption"] |
    When I analyze the MCQ quality
    Then distractor_quality_score should be >= 0.70
    And answer_clarity_score should be >= 0.80
    And overall_grade should be "A" or "B"
    And quality_report should include:
      | metric                | value   |
      | question_word_count   | 7       |
      | option_count          | 4       |
      | has_distinct_options  | true    |
      | similar_option_pairs  | 0       |

  Scenario: Detect poor MCQ distractors (too similar)
    Given an MCQ question:
      | front   | What protocol uses port 443? |
      | correct | HTTPS                        |
      | options | ["HTTPS", "HTTP", "HTTSP", "HTTPSS"] |
    When I analyze the MCQ quality
    Then distractor_quality_score should be < 0.50
    And issues should include "Distractors too similar to each other"
    And recommendations should include "Differentiate distractor options"

  Scenario: Detect obvious incorrect option
    Given an MCQ question:
      | front   | Which layer handles routing?       |
      | correct | Network Layer                      |
      | options | ["Network Layer", "Banana", "Physical Layer", "Transport Layer"] |
    When I analyze the MCQ quality
    Then distractor_quality_score should be < 0.60
    And issues should include "Obvious incorrect option detected"
    And flagged_option should be "Banana"

  Scenario: MCQ with suboptimal option count
    Given an MCQ question with 2 options
    When I analyze the MCQ quality
    Then issues should include "Too few options (2 < 3 minimum)"
    And recommendations should include "Add more plausible distractors"

  # ========================================
  # TRUE/FALSE
  # Learning Mechanism: Retrieval (d=0.7)
  # ========================================

  Scenario: Analyze true/false question quality
    Given a true/false question:
      | front          | TCP uses a three-way handshake to establish connections |
      | correct_answer | true                                                     |
    When I analyze the true/false quality
    Then answer_clarity_score should be >= 0.80
    And issues should not include "Ambiguous statement"

  Scenario: Detect ambiguous true/false statement
    Given a true/false question:
      | front          | Networks are usually fast |
      | correct_answer | true                      |
    When I analyze the true/false quality
    Then answer_clarity_score should be < 0.60
    And issues should include "Ambiguous qualifier: 'usually'"
    And recommendations should include "Remove ambiguous terms"

  Scenario: Detect negation in true/false question
    Given a true/false question:
      | front          | TCP does not guarantee delivery |
      | correct_answer | false                           |
    When I analyze the true/false quality
    Then issues should include "Double negative detected"
    And recommendations should include "Rephrase to positive form"

  # ========================================
  # SHORT ANSWER
  # Learning Mechanism: Retrieval (d=0.7)
  # ========================================

  Scenario: Analyze short answer question quality
    Given a short answer question:
      | front          | What port does HTTP use by default? |
      | expected_answer| 80                                   |
      | acceptable     | ["80", "port 80", "eighty"]         |
    When I analyze the short answer quality
    Then answer_clarity_score should be >= 0.85
    And quality_report should include:
      | metric              | value |
      | has_single_answer   | true  |
      | acceptable_variants | 3     |

  Scenario: Detect overly broad short answer
    Given a short answer question:
      | front          | Explain TCP |
      | expected_answer| A protocol for reliable data transmission |
    When I analyze the short answer quality
    Then issues should include "Question too broad for short answer format"
    And recommendations should include "Make question more specific"

  # ========================================
  # MATCHING
  # Learning Mechanism: Discrimination (d=0.6)
  # ========================================

  Scenario: Analyze high-quality matching question
    Given a matching question:
      | front | Match the protocol to its port |
      | pairs | [{"left": "HTTP", "right": "80"}, {"left": "HTTPS", "right": "443"}, {"left": "SSH", "right": "22"}, {"left": "FTP", "right": "21"}] |
    When I analyze the matching quality
    Then overall_grade should be >= "B"
    And quality_report should include:
      | metric              | value |
      | pair_count          | 4     |
      | within_optimal_range| true  |
      | distinct_items      | true  |

  Scenario: Detect too many matching pairs
    Given a matching question with 8 pairs
    When I analyze the matching quality
    Then issues should include "Too many pairs (8 > 6 maximum)"
    And recommendations should include "Reduce to 4-6 pairs for optimal cognitive load"

  Scenario: Detect matching with duplicate items
    Given a matching question:
      | pairs | [{"left": "HTTP", "right": "80"}, {"left": "HTTP", "right": "8080"}] |
    When I analyze the matching quality
    Then issues should include "Duplicate items in matching pairs"

  # ========================================
  # RANKING
  # Learning Mechanism: Discrimination (d=0.6)
  # ========================================

  Scenario: Analyze ranking question quality
    Given a ranking question:
      | front | Order the OSI layers from lowest to highest |
      | items | ["Physical", "Data Link", "Network", "Transport"] |
      | correct_order | [0, 1, 2, 3] |
    When I analyze the ranking quality
    Then overall_grade should be >= "B"
    And quality_report should include:
      | metric        | value |
      | item_count    | 4     |
      | clear_ordering| true  |

  Scenario: Detect ranking with ambiguous order
    Given a ranking question:
      | front | Order these protocols by importance |
      | items | ["TCP", "UDP", "ICMP"] |
    When I analyze the ranking quality
    Then issues should include "Subjective ordering criterion"
    And recommendations should include "Use objective ordering criteria"

  # ========================================
  # SEQUENCE (PROCEDURAL)
  # Learning Mechanism: Application (d=0.5)
  # ========================================

  Scenario: Analyze sequence question quality
    Given a sequence question:
      | front | Order the TCP handshake steps |
      | steps | ["SYN", "SYN-ACK", "ACK"] |
    When I analyze the sequence quality
    Then overall_grade should be >= "B"
    And knowledge_type should be "procedural"

  # ========================================
  # PARSONS PROBLEMS
  # Learning Mechanism: Generation (d=0.5)
  # ========================================

  Scenario: Analyze parsons problem quality
    Given a parsons problem:
      | front       | Arrange the code to create a TCP connection |
      | code_blocks | ["import socket", "s = socket.socket()", "s.connect(('host', 80))", "s.send(data)"] |
      | distractors | ["s.listen()", "s.accept()"] |
    When I analyze the parsons quality
    Then overall_grade should be >= "B"
    And quality_report should include:
      | metric              | value |
      | block_count         | 4     |
      | distractor_count    | 2     |
      | has_distractors     | true  |

  Scenario: Detect parsons with too many blocks
    Given a parsons problem with 15 code blocks
    When I analyze the parsons quality
    Then issues should include "Too many code blocks (15 > 12 maximum)"
    And recommendations should include "Split into multiple smaller problems"

  Scenario: Detect parsons without distractors
    Given a parsons problem:
      | code_blocks | ["line1", "line2", "line3"] |
      | distractors | [] |
    When I analyze the parsons quality
    Then issues should include "No distractor blocks"
    And recommendations should include "Add 1-3 plausible distractor blocks"

  # ========================================
  # CLOZE (FILL IN THE BLANK)
  # Learning Mechanism: Retrieval (d=0.7)
  # ========================================

  Scenario: Analyze cloze question quality
    Given a cloze question:
      | front    | TCP uses a {{c1::three-way handshake}} to establish connections |
      | cloze_count | 1 |
    When I analyze the cloze quality
    Then overall_grade should be >= "B"
    And quality_report should include:
      | metric           | value |
      | cloze_count      | 1     |
      | context_adequate | true  |

  Scenario: Detect cloze with too many blanks
    Given a cloze question:
      | front | {{c1::TCP}} uses {{c2::three-way}} {{c3::handshake}} for {{c4::reliable}} {{c5::connections}} |
      | cloze_count | 5 |
    When I analyze the cloze quality
    Then issues should include "Too many cloze deletions (5 > 3 recommended)"
    And recommendations should include "Focus on one key concept per card"

  Scenario: Detect cloze without sufficient context
    Given a cloze question:
      | front | {{c1::TCP}} |
    When I analyze the cloze quality
    Then issues should include "Insufficient context for cloze"
    And recommendations should include "Provide surrounding context"

  # ========================================
  # PREDICTION
  # Learning Mechanism: Elaboration (d=0.6)
  # ========================================

  Scenario: Analyze prediction question quality
    Given a prediction question:
      | front    | What happens when a TCP packet is lost? |
      | expected | Retransmission occurs after timeout      |
    When I analyze the prediction quality
    Then knowledge_type should be "conceptual"
    And overall_grade should be >= "C"

  # ========================================
  # EXPLAIN
  # Learning Mechanism: Generation (d=0.5)
  # ========================================

  Scenario: Analyze explain question quality
    Given an explain question:
      | front        | Explain how TCP ensures reliable delivery |
      | key_concepts | ["acknowledgments", "retransmission", "sequence numbers"] |
    When I analyze the explain quality
    Then knowledge_type should be "conceptual"
    And quality_report should include:
      | metric           | value |
      | key_concept_count| 3     |
      | is_well_scoped   | true  |

  Scenario: Detect overly broad explain question
    Given an explain question:
      | front | Explain networking |
    When I analyze the explain quality
    Then issues should include "Question scope too broad"
    And recommendations should include "Focus on specific concept or relationship"

  # ========================================
  # COMPARE
  # Learning Mechanism: Generation (d=0.5)
  # ========================================

  Scenario: Analyze compare question quality
    Given a compare question:
      | front      | Compare TCP and UDP |
      | dimensions | ["reliability", "speed", "overhead", "use cases"] |
    When I analyze the compare quality
    Then overall_grade should be >= "B"
    And quality_report should include:
      | metric          | value |
      | item_count      | 2     |
      | dimension_count | 4     |

  Scenario: Detect compare with too many items
    Given a compare question:
      | front | Compare HTTP, HTTPS, FTP, SFTP, SSH, and Telnet |
    When I analyze the compare quality
    Then issues should include "Too many items to compare (6 > 3 recommended)"
    And recommendations should include "Limit comparison to 2-3 items"

  # ========================================
  # PROBLEM (APPLICATION)
  # Learning Mechanism: Elaboration (d=0.6)
  # ========================================

  Scenario: Analyze problem question quality
    Given a problem question:
      | front     | Calculate the subnet mask for a /24 network |
      | solution  | 255.255.255.0                                |
      | steps     | ["Start with /24", "Convert to binary", "Result: 255.255.255.0"] |
    When I analyze the problem quality
    Then knowledge_type should be "procedural"
    And quality_report should include:
      | metric      | value |
      | has_steps   | true  |
      | step_count  | 3     |

  # ========================================
  # PASSAGE-BASED
  # Learning Mechanism: Application (d=0.5)
  # ========================================

  Scenario: Analyze passage-based question quality
    Given a passage-based question:
      | passage | "TCP (Transmission Control Protocol) is a connection-oriented protocol that provides reliable, ordered delivery of data. It uses a three-way handshake to establish connections and implements flow control and congestion control mechanisms." |
      | questions | [{"type": "mcq", "front": "What type of protocol is TCP?", "options": ["Connection-oriented", "Connectionless", "Stateless", "Broadcast"]}] |
    When I analyze the passage-based quality
    Then overall_grade should be >= "B"
    And quality_report should include:
      | metric           | value |
      | passage_word_count| 39   |
      | question_count   | 1     |
      | answers_in_passage| true |

  Scenario: Detect passage-based with answer not in passage
    Given a passage-based question:
      | passage | "TCP provides reliable data delivery." |
      | questions | [{"type": "mcq", "front": "What port does TCP use?", "correct": "Various ports"}] |
    When I analyze the passage-based quality
    Then issues should include "Answer not supported by passage"
    And recommendations should include "Ensure all answers are derivable from passage"

  # ========================================
  # FLASHCARD (BASIC)
  # Learning Mechanism: Retrieval (d=0.7)
  # ========================================

  Scenario: Analyze high-quality flashcard
    Given a flashcard:
      | front | What is the default port for HTTPS? |
      | back  | 443                                  |
    When I analyze the flashcard quality
    Then overall_grade should be "A"
    And quality_report should include:
      | metric              | value |
      | front_word_count    | 7     |
      | back_word_count     | 1     |
      | atomic_fact         | true  |
      | has_question_form   | true  |

  Scenario: Detect flashcard with answer too long
    Given a flashcard:
      | front | What is TCP? |
      | back  | TCP (Transmission Control Protocol) is a core protocol of the Internet protocol suite that provides reliable, ordered, and error-checked delivery of a stream of octets between applications running on hosts communicating via an IP network. |
    When I analyze the flashcard quality
    Then issues should include "Answer too long (>20 words)"
    And recommendations should include "Break into multiple atomic cards"
    And overall_grade should be <= "C"

  Scenario: Detect flashcard violating minimum information principle
    Given a flashcard:
      | front | What are the seven layers of the OSI model? |
      | back  | Physical, Data Link, Network, Transport, Session, Presentation, Application |
    When I analyze the flashcard quality
    Then issues should include "Multiple facts in single card"
    And recommendations should include "Create separate card for each layer"

  # ========================================
  # BATCH QUALITY ANALYSIS
  # ========================================

  Scenario: Batch analyze questions with quality summary
    Given a batch of 50 quiz questions
    When I run batch quality analysis
    Then summary should include:
      | metric           | type     |
      | total_analyzed   | 50       |
      | grade_distribution| A:10, B:20, C:15, D:4, F:1 |
      | avg_quality_score| 0.72     |
      | improvement_needed| 5        |
    And low_quality_questions should be flagged for review

  Scenario: Filter questions by quality threshold
    Given a question pool with various quality scores
    When I filter questions with minimum grade "B"
    Then only questions with grade >= "B" should be returned
    And filtered count should be less than total count

  # ========================================
  # KNOWLEDGE TYPE CLASSIFICATION
  # ========================================

  Scenario: Classify question knowledge type as factual
    Given an MCQ question:
      | front | What port does SSH use? |
    When I classify the knowledge type
    Then knowledge_type should be "factual"
    And passing_threshold should be 0.70

  Scenario: Classify question knowledge type as conceptual
    Given an explain question:
      | front | How does TCP ensure reliable delivery? |
    When I classify the knowledge type
    Then knowledge_type should be "conceptual"
    And passing_threshold should be 0.80

  Scenario: Classify question knowledge type as procedural
    Given a sequence question:
      | front | Order the steps to establish a TCP connection |
    When I classify the knowledge type
    Then knowledge_type should be "procedural"
    And passing_threshold should be 0.85

  # ========================================
  # QUALITY GRADING
  # ========================================

  Scenario Outline: Quality grade thresholds
    Given a question with quality_score <score>
    When I calculate the grade
    Then grade should be "<grade>"

    Examples:
      | score | grade |
      | 0.95  | A     |
      | 0.82  | B     |
      | 0.67  | C     |
      | 0.45  | D     |
      | 0.30  | F     |

  # ========================================
  # QUESTION POOL MANAGEMENT
  # ========================================

  Scenario: Create question pool for concept
    Given concept "TCP Fundamentals" exists
    When I create a question pool:
      | name             | TCP Basics Pool |
      | concept_id       | TCP Fundamentals |
      | target_difficulty| 0.5             |
      | min_questions    | 10              |
    Then pool is created successfully
    And pool should have target_difficulty 0.5

  Scenario: Select random questions with seed
    Given pool "TCP Pool" with 50 questions
    When I select 10 questions with seed "user123:attempt1"
    Then 10 questions should be returned
    And selecting again with same seed should return same questions

  Scenario: Select questions with difficulty range
    Given pool with questions at various difficulties
    When I select questions with difficulty_range (0.4, 0.6)
    Then all selected questions should have difficulty between 0.4 and 0.6

  Scenario: Select diverse questions across types
    Given pool with MCQ, true_false, and short_answer questions
    When I select 9 questions with diversity enforcement
    Then selection should include questions from each type
    And no single type should exceed 50% of selection

  Scenario: Pool statistics calculation
    Given pool "Assessment Pool" with:
      | question_count | 30 |
      | active_count   | 28 |
      | difficulties   | [0.3, 0.5, 0.5, 0.7, 0.8] sample |
    When I get pool statistics
    Then statistics should include:
      | metric                  | value |
      | total_questions         | 30    |
      | active_questions        | 28    |
      | avg_difficulty          | ~0.56 |
      | difficulty_distribution | {"easy": 8, "medium": 15, "hard": 7} |
      | has_sufficient_questions| true  |

  # ========================================
  # QUIZ DEFINITION AND MASTERY
  # ========================================

  Scenario: Create quiz definition with mastery weights
    Given concept cluster "Networking Basics" exists
    When I create a quiz definition:
      | name           | Networking Fundamentals Quiz |
      | cluster_id     | Networking Basics            |
      | question_count | 20                           |
      | time_limit_min | 30                           |
      | passing_score  | 0.70                         |
      | quiz_weight    | 0.375                        |
      | review_weight  | 0.625                        |
    Then quiz definition is created successfully
    And mastery formula should be:
      """
      mastery = (review_score * 0.625) + (quiz_score * 0.375)
      """

  Scenario: Calculate mastery with quiz and review scores
    Given user has:
      | review_score | 0.80 |
      | quiz_score   | 0.70 |
    When I calculate mastery
    Then mastery should be:
      """
      (0.80 * 0.625) + (0.70 * 0.375) = 0.50 + 0.2625 = 0.7625
      """

  # ========================================
  # EXPORT FOR RIGHT-LEARNING
  # ========================================

  Scenario: Export quiz questions for right-learning API
    Given quiz definition "Final Assessment" exists
    And quiz has 20 questions across types
    When I call "GET /api/quiz/export/questions/{quiz_id}"
    Then response should include:
      | field              | type     |
      | quiz_id            | uuid     |
      | questions          | array    |
      | question.type      | string   |
      | question.content   | object   |
      | question.difficulty| float    |
      | question.knowledge_type| string |
      | metadata.version   | string   |

  Scenario: Export quiz quality summary for right-learning
    When I call "GET /api/quiz/questions/quality-summary"
    Then response should include:
      | field               | type   |
      | total_questions     | int    |
      | by_grade            | object |
      | by_type             | object |
      | by_knowledge_type   | object |
      | avg_quality         | float  |
      | improvement_queue   | array  |

  # ========================================
  # VALIDATION RULES
  # ========================================

  Scenario: Validate MCQ structure
    Given invalid MCQ content:
      | front   | What is TCP? |
      | options | ["TCP"]      |
    When I validate the question structure
    Then validation should fail
    And errors should include "MCQ requires at least 3 options"

  Scenario: Validate matching structure
    Given invalid matching content:
      | pairs | [{"left": "HTTP"}] |
    When I validate the question structure
    Then validation should fail
    And errors should include "Matching pairs require both 'left' and 'right' keys"

  Scenario: Validate parsons structure
    Given invalid parsons content:
      | code_blocks | [] |
    When I validate the question structure
    Then validation should fail
    And errors should include "Parsons problem requires at least 3 code blocks"

  # ========================================
  # QUALITY IMPROVEMENT RECOMMENDATIONS
  # ========================================

  Scenario: Generate improvement plan for low-quality questions
    Given 10 questions with grade "D" or "F"
    When I generate improvement recommendations
    Then recommendations should be prioritized by:
      | priority | criteria                    |
      | 1        | High-value concepts         |
      | 2        | Frequently used questions   |
      | 3        | Lowest quality scores       |
    And each recommendation should include:
      | field            | description                |
      | question_id      | UUID of question           |
      | current_grade    | Current quality grade      |
      | issues           | List of quality issues     |
      | suggestions      | Specific improvement steps |
      | estimated_effort | low/medium/high            |

