"""
Evidence-Based LLM Prompts for Learning Atom Generation.

Contains prompts for all 6 atom types:
- Flashcard (Anki) - Retrieval practice
- Cloze (Anki) - Contextual recall
- MCQ (NSL) - Discrimination
- True/False (NSL) - Binary discrimination
- Parsons (NSL) - Procedure ordering
- Matching (NSL) - Term-definition pairs

Each prompt includes:
1. Evidence-based quality rules
2. Positive examples (what to generate)
3. Negative examples (what NOT to generate)
4. Output format specification
"""
from __future__ import annotations

# =============================================================================
# System Prompt (Applied to All Generation)
# =============================================================================

SYSTEM_PROMPT = """You are an expert CCNA instructor creating high-quality learning content.
Your content will be used in two systems:
1. Anki (flashcards + cloze) - spaced repetition for long-term retention
2. NSL (MCQ, T/F, Parsons, Matching) - interactive quizzes for active learning

CRITICAL QUALITY RULES (Evidence-Based):

1. ATOMICITY - ONE fact per item
   - Formula: S_composite = (S_a × S_b) / (S_a + S_b)
   - Two facts with S=30 days each → S_composite=15 days (HALF retention!)
   - If you need "and", "also", "additionally" → SPLIT into separate items

2. COMPLETENESS - Every answer must be a COMPLETE sentence/phrase
   - NEVER end with articles: a, an, the
   - NEVER end with prepositions: of, to, for, with, by, at, in, on, or, and
   - NEVER end with commas or colons
   - ALWAYS verify the last word makes grammatical sense as an ending

3. COHERENCE - Questions must be grammatically correct
   - NEVER include source text fragments in questions
   - NEVER use "This", "The X" without proper context
   - NEVER create questions like "What X The Y?" or "What is This?"

4. ANSWER LENGTH (Flashcards)
   - MINIMUM 10 words - NO EXCEPTIONS
   - Include PURPOSE/FUNCTION/CONTEXT, not just definitions
   - Format: "[What it is] + [What it does/why it matters]"

5. CISCO TERMINOLOGY
   - Use exact terms from CCNA curriculum
   - Include command modes: Router>, Router#, Router(config)#

6. NO HALLUCINATION
   - ONLY use information from the source content
   - Do NOT infer or expand beyond what is written

7. SOURCE TRACEABILITY (REQUIRED)
   - EVERY atom MUST include a source_refs array
   - Capture the section_id (e.g., "1.2.3") from the section header
   - Include a 10-30 word excerpt of the source text you based the atom on
   - This creates a "golden thread" for auditing atom accuracy

8. HANDLING VISUAL DESCRIPTIONS
   - Source content may include [VISUAL: ...], [IMAGE: ...], or [Figure X: ...] tags
   - These are textual descriptions of images that are not available to you
   - DO NOT create questions asking "What does the figure show?"
   - Instead, transform visual concepts into SCENARIO-BASED questions:
     ✅ "In a star topology, what device connects all endpoints?"
     ❌ "According to Figure 1.2, what does the diagram show?"
   - Set metadata.derived_from_visual = true for these atoms

9. HANDLING EMPTY OR MISSING DATA
   - If a table in the source text is empty (e.g., "| | |" with no content), DO NOT generate atoms for it
   - If data is missing from the source, DO NOT invent or hallucinate content to fill it
   - Skip that specific element and move on
   - You will see "[EMPTY TABLE - No content to extract]" markers - ignore these entirely
   - NEVER create an atom that references information not present in the source

10. HANDLING RAW/MESSY SOURCE TEXT
    - Source text may contain formatting artifacts, broken tables, or CLI typos
    - YOU handle the "fuzzy parsing" - understand the semantic meaning despite formatting issues
    - Fix syntax errors IN YOUR OUTPUT (the generated atoms), not in citations
    - Example: If source has "hostnamehostname", understand it means "hostname hostname"
    - Preserve technical accuracy even when source formatting is imperfect

11. FIDELITY & ATTRIBUTION (REQUIRED FOR ALL ATOMS)
    For every atom you generate, you MUST classify its origin in the metadata:

    **'verbatim_extract'**: You used a definition, list, or syntax EXACTLY as it appears in the text.
    - Use for: Port numbers, command syntax, standard definitions, protocol specifications
    - Set is_hydrated = false
    - source_fact_basis = (leave empty or null)

    **'rephrased_fact'**: You rewrote a sentence for clarity, but added NO new context or examples.
    - Use for: Simplifying complex sentences while preserving meaning
    - Set is_hydrated = false
    - source_fact_basis = (leave empty or null)

    **'ai_scenario_enrichment'** (The "Hydration"): You took a raw fact and created a realistic
    NETWORKING SCENARIO around it (e.g., "Host A sends to Host B..." or "A technician sees...").
    - REQUIREMENT: Set is_hydrated = true
    - REQUIREMENT: Copy the EXACT source sentence into source_fact_basis
    - This enables audit: we can trace your scenario back to the original fact

    EXAMPLES:
    Source text: "Broadcasts are stopped at routers."

    ❌ verbatim_extract: Q: "What stops broadcasts?" A: "Routers"
       (Too simple, tests trivia not application)

    ✅ ai_scenario_enrichment: Q: "PC-A sends an ARP request broadcast. Does Router R1 forward it?"
       A: "No, routers do not forward broadcast traffic. The ARP request stays in PC-A's local subnet."
       metadata.is_hydrated = true
       metadata.fidelity_type = "ai_scenario_enrichment"
       metadata.source_fact_basis = "Broadcasts are stopped at routers."

OUTPUT: Always return valid JSON as specified in each prompt type."""


# =============================================================================
# Negative Examples (What NOT to Generate)
# =============================================================================

NEGATIVE_EXAMPLES = """
=== NEGATIVE EXAMPLES - NEVER GENERATE THESE ===

❌ MALFORMED QUESTIONS (garbled text):
- "In networking, what circuits The circuits?"
- "What hosts Some hosts are also called?"
- "What is This concept The concept?"
- "What the However the term hosts specifically?"
- "What type This type of network?"
- "What layer If one path fails?"

❌ VAGUE QUESTIONS (no context):
- "What is This?"
- "What is BYOD?" (bare acronym without context)
- "What is Business DSL?" (just the term)
- "Define VLAN."

❌ TRUNCATED ANSWERS (incomplete):
- "Provides the" (ends mid-sentence)
- "Leased lines are reserved circuits within the service provider's network that connect geographically separated offices for private voice and/or data networking. The circuits are rented at a monthly or" (cut off)
- "Business DSL is" (incomplete)
- "Used for" (too short)
- "TCP" (single word)
- "Layer 3" (no context)

❌ TOO SHORT ANSWERS:
- "Contacts other servers" (3 words)
- "Troubleshoot name resolution" (3 words)
- "Provides connectivity" (2 words)

❌ MULTI-FACT ANSWERS:
- "VLANs segment the network AND provide security AND reduce broadcast traffic"
- Lists with multiple bullet points
- "First, X happens. Then, Y occurs. Finally, Z."

❌ MCQ WEAK DISTRACTORS:
- "All of the above"
- "None of the above"
- "Both A and B"
- Single-word options when others are sentences
"""


# =============================================================================
# Flashcard Prompt (Anki)
# =============================================================================

FLASHCARD_PROMPT = """Generate atomic flashcards from this CCNA content.

=== MANDATORY REQUIREMENTS ===
1. ONE fact per card - if you need "and", make two cards
2. Question: 8-15 words, tests specific knowledge
3. Answer: 10-25 words - THIS IS MANDATORY
   - Include WHAT it is + WHY/HOW it matters
   - NEVER less than 10 words
4. SCENARIO-BASED: Frame questions around realistic situations, not abstract definitions

=== FEW-SHOT EXAMPLES: SCENARIO vs ABSTRACT ===

**NEGATIVE EXAMPLE (Abstract - Do NOT Do This):**
Q: "What is a unicast address?"
A: "A unicast address identifies a single interface."
(Problems: Abstract, no context, doesn't test application)

**POSITIVE EXAMPLE (Scenario-Based - Do This):**
Q: "Host A (192.168.1.5) wants to send a frame directly to Server B (192.168.1.200) on the same subnet. What specific type of destination address must the frame contain?"
A: "The frame must contain a unicast destination MAC address - Server B's unique MAC - because unicast addresses identify a single, specific interface for point-to-point delivery on the local network." (29 words)
(Why better: Tests the concept IN CONTEXT of actual network behavior)

---

**NEGATIVE EXAMPLE (Abstract - Do NOT Do This):**
Q: "What is the difference between TCP and UDP?"
A: "TCP is reliable and UDP is unreliable."
(Problems: Vague, tests trivia not application)

**POSITIVE EXAMPLE (Scenario-Based - Do This):**
Q: "A VoIP application needs to stream real-time audio between two hosts. Why would the developer choose UDP over TCP for this traffic?"
A: "UDP is preferred for real-time audio because it has no retransmission delays - dropped packets are better than late packets in live communication, and TCP's reliability mechanisms would cause unacceptable latency." (31 words)
(Why better: Tests WHY the choice matters in a real scenario)

---

**NEGATIVE EXAMPLE (Abstract - Do NOT Do This):**
Q: "What OSI layer handles routing?"
A: "Layer 3 (Network layer)"
(Problems: Too short, tests memorization not understanding)

**POSITIVE EXAMPLE (Scenario-Based - Do This):**
Q: "When a packet travels from PC1 in the 10.0.0.0/24 network to a web server in the 172.16.0.0/16 network, which OSI layer determines the path the packet takes across multiple routers?"
A: "The Network layer (Layer 3) determines the path by using logical IP addresses to make routing decisions at each hop, selecting the best route from source to destination network." (28 words)
(Why better: Tests understanding of HOW routing works across networks)

---

=== ANSWER LENGTH EXAMPLES ===

✅ GOOD (Proper Length + Scenario):
Q: "A network admin notices that broadcast storms are affecting switch performance. What Layer 2 feature should they implement to prevent this while still allowing inter-VLAN communication?"
A: "VLANs (Virtual LANs) segment the broadcast domain at Layer 2, containing broadcast traffic within each VLAN while a Layer 3 device enables controlled communication between VLANs." (25 words)

Q: "When troubleshooting, a technician needs to see the MAC address table on a Cisco switch. What command displays this information and what does it show?"
A: "The 'show mac address-table' command displays the switch's mapping of MAC addresses to ports, showing which devices are reachable through which switch interfaces." (23 words)

❌ BAD (Too Short - REJECT):
Q: "What does DNS do?"
A: "Resolves names" (2 words - REJECTED)

Q: "What layer handles routing?"
A: "Layer 3" (2 words - REJECTED)

Q: "What is TCP?"
A: "Transport protocol" (2 words - REJECTED)

{negative_examples}

=== OUTPUT FORMAT ===
Return JSON array:
[
  {{
    "card_id": "{section_id}-FC-001",
    "front": "specific question testing single fact (8-15 words)",
    "back": "complete answer with context (10-25 words, MUST be complete sentence)",
    "tags": ["topic", "subtopic"],
    "source_refs": [
      {{
        "section_id": "{section_id}",
        "section_title": "title from header",
        "source_text_excerpt": "10-30 word excerpt this atom is based on"
      }}
    ],
    "knowledge_type": "factual|conceptual|procedural",
    "metadata": {{
      "difficulty": 1-5,
      "knowledge_type": "factual|conceptual|procedural",
      "derived_from_visual": false
    }}
  }}
]

Generate 5-10 cards. Increment suffix: 001, 002, 003...

SECTION ID: {section_id}
CONTENT:
{content}"""


# =============================================================================
# Cloze Prompt (Anki)
# =============================================================================

CLOZE_PROMPT = """Generate cloze deletion cards for key terminology from this CCNA content.

=== REQUIREMENTS ===
1. ONE blank per card (single {{{{c1::term}}}} deletion)
2. Context must make the answer UNAMBIGUOUS
3. Blank should test the KEY TERM being learned
4. Surrounding text provides retrieval cues
5. Full sentence with proper grammar
6. SCENARIO-BASED: Embed the term in a realistic networking context

=== FEW-SHOT EXAMPLES: SCENARIO vs ABSTRACT ===

**NEGATIVE EXAMPLE (Abstract - Do NOT Do This):**
"The {{{{c1::default gateway}}}} is the router interface that forwards packets."
(Problem: Generic definition, no scenario)

**POSITIVE EXAMPLE (Scenario-Based - Do This):**
"When PC1 (192.168.1.50) needs to reach a web server on the internet, it sends packets to its {{{{c1::default gateway}}}} - the local router interface that forwards traffic destined for networks outside the local subnet."
(Why better: Shows WHEN and WHY the default gateway is used)

---

**NEGATIVE EXAMPLE (Abstract - Do NOT Do This):**
"{{{{c1::OSPF}}}} is a routing protocol."
(Problem: No context about what makes OSPF special)

**POSITIVE EXAMPLE (Scenario-Based - Do This):**
"In an enterprise network with 50 routers, the network team chose {{{{c1::OSPF}}}} because its link-state design allows each router to build a complete topology map and calculate optimal paths independently."
(Why better: Shows WHY OSPF is chosen in a real scenario)

---

=== ADDITIONAL POSITIVE EXAMPLES ===
✅ "After a switch receives a frame from a new device, it records the source MAC address in its {{{{c1::MAC address table}}}} so it can forward future frames directly to that port."
✅ "When troubleshooting connectivity, the command {{{{c1::ping}}}} sends ICMP echo requests to verify Layer 3 reachability between source and destination."
✅ "In a corporate network using 172.16.0.0/12, the IT team implemented {{{{c1::VLANs}}}} to separate HR, Finance, and Engineering departments into isolated broadcast domains."
✅ "During the {{{{c1::three-way handshake}}}}, TCP establishes a reliable connection by exchanging SYN and ACK segments before application data transfer begins."

=== NEGATIVE EXAMPLES ===
❌ "{{{{c1::It}}}} is used for routing." (vague reference)
❌ "{{{{c1::This protocol}}}} does something." (no context)
❌ "The {{{{c1::X}}}} and {{{{c2::Y}}}} work together." (multiple deletions)
❌ "{{{{c1::DNS}}}}." (no context at all)

{negative_examples}

=== OUTPUT FORMAT ===
Return JSON array:
[
  {{
    "card_id": "{section_id}-CL-001",
    "front": "Complete sentence with {{{{c1::term}}}} deletion providing clear context",
    "back": "term",
    "tags": ["topic", "terminology"],
    "source_refs": [
      {{
        "section_id": "{section_id}",
        "section_title": "title from header",
        "source_text_excerpt": "10-30 word excerpt this atom is based on"
      }}
    ],
    "knowledge_type": "factual",
    "metadata": {{
      "difficulty": 1-5,
      "knowledge_type": "factual",
      "derived_from_visual": false
    }}
  }}
]

Generate 3-5 cloze cards. Increment suffix: 001, 002, 003...

SECTION ID: {section_id}
CONTENT:
{content}"""


# =============================================================================
# MCQ Prompt (NSL)
# =============================================================================

MCQ_PROMPT = """Generate multiple choice questions from this CCNA content for interactive quizzes.

=== REQUIREMENTS ===
1. Stem: Clear question, 10-20 words - MUST be scenario-based
2. Correct answer: Unambiguous, precise
3. Distractors (3): Plausible but clearly wrong to knowledgeable person
   - Common misconceptions
   - Related but incorrect terms
   - Partially correct statements
4. EXACTLY 4 options total (research: diminishing returns beyond 4)
5. All options similar length (±20%)
6. NEVER use "All of the above" or "None of the above"

=== FEW-SHOT EXAMPLES: SCENARIO vs ABSTRACT ===

**NEGATIVE EXAMPLE (Abstract - Do NOT Do This):**
Stem: "Which OSI layer is responsible for logical addressing and routing decisions?"
Options: ["Network (Layer 3)", "Data Link (Layer 2)", "Transport (Layer 4)", "Physical (Layer 1)"]
(Problem: Tests memorization, not application)

**POSITIVE EXAMPLE (Troubleshooting Scenario - Do This):**
Stem: "A user in the 10.1.1.0/24 network cannot reach a server in the 172.16.0.0/16 network, but can ping other hosts in their own subnet. At which OSI layer is the problem most likely occurring?"
Options: [
  "Network (Layer 3) - routing or IP addressing issue",
  "Data Link (Layer 2) - switch or MAC address issue",
  "Transport (Layer 4) - port or session issue",
  "Physical (Layer 1) - cable or hardware issue"
]
Correct: 0
Explanation: "Since local connectivity works but remote fails, the problem is at Layer 3 where routing decisions are made for traffic between different networks."
(Why better: Tests DIAGNOSIS ability, not just recall)

---

**NEGATIVE EXAMPLE (Abstract - Do NOT Do This):**
Stem: "What protocol provides reliable, ordered delivery of data?"
Options: ["TCP", "UDP", "ICMP", "ARP"]
(Problem: Simple recall question)

**POSITIVE EXAMPLE (Design Decision Scenario - Do This):**
Stem: "An application developer is building a file transfer service that must guarantee complete, uncorrupted delivery of large documents. Which transport protocol should they use?"
Options: [
  "TCP - provides sequencing, acknowledgments, and retransmission",
  "UDP - provides best-effort delivery with minimal overhead",
  "ICMP - provides network diagnostic messaging",
  "ARP - provides address resolution services"
]
Correct: 0
Explanation: "TCP's reliability features (acknowledgments, sequencing, retransmission) ensure files arrive complete and in order, which is critical for document integrity."
(Why better: Tests understanding of WHEN to apply the concept)

---

**NEGATIVE EXAMPLE (Abstract - Do NOT Do This):**
Stem: "What is the default administrative distance of OSPF?"
Options: ["110", "90", "120", "100"]
(Problem: Pure trivia, no practical context)

**POSITIVE EXAMPLE (Real Network Scenario - Do This):**
Stem: "A router has learned the route to 192.168.50.0/24 via both OSPF (AD 110) and EIGRP (AD 90). Which route will appear in the routing table and why?"
Options: [
  "EIGRP route - lower AD indicates more trustworthy source",
  "OSPF route - link-state protocols are preferred over distance-vector",
  "Both routes - load balancing across protocols",
  "Neither route - administrative distance conflict prevents installation"
]
Correct: 0
Explanation: "The router installs the route with the lowest administrative distance. EIGRP's AD of 90 is lower than OSPF's 110, making it the preferred source."
(Why better: Tests understanding of AD concept in action)

---

=== ADDITIONAL POSITIVE EXAMPLES ===
✅ Stem: "A switch receives a frame with destination MAC AA:BB:CC:DD:EE:FF but this MAC is not in its MAC address table. What action does the switch take?"
   Options: [
     "Floods the frame out all ports except the source port",
     "Drops the frame and sends an error message",
     "Forwards the frame to the default gateway",
     "Buffers the frame until the destination responds"
   ]
   Correct: 0
   Explanation: "Unknown unicast frames are flooded to all ports (except source) so the destination can respond and the switch can learn its location."

=== NEGATIVE EXAMPLES ===
❌ "All of the above" as an option
❌ "None of the above" as an option
❌ "Both A and B" as an option
❌ Single-word options when others are full sentences
❌ Obviously wrong distractors ("pizza", "42", random terms)
❌ Two options that are essentially the same

{negative_examples}

=== OUTPUT FORMAT ===
Return JSON array:
[
  {{
    "card_id": "{section_id}-MCQ-001",
    "front": "question stem (10-20 words)",
    "correct_answer": "the correct option text",
    "distractors": ["plausible wrong 1", "plausible wrong 2", "plausible wrong 3"],
    "explanation": "Why the correct answer is right (1-2 sentences)",
    "source_refs": [
      {{
        "section_id": "{section_id}",
        "section_title": "title from header",
        "source_text_excerpt": "10-30 word excerpt this atom is based on"
      }}
    ],
    "knowledge_type": "conceptual|procedural",
    "metadata": {{
      "difficulty": 1-5,
      "knowledge_type": "conceptual|procedural",
      "derived_from_visual": false
    }}
  }}
]

Generate 3-5 MCQs. Increment suffix: 001, 002, 003...

SECTION ID: {section_id}
CONTENT:
{content}"""


# =============================================================================
# True/False Prompt (NSL)
# =============================================================================

TRUE_FALSE_PROMPT = """Generate true/false questions from this CCNA content for interactive quizzes.

=== REQUIREMENTS ===
1. Statement must be CLEARLY true or false (no ambiguity)
2. Avoid double negatives
3. Test SINGLE concept per question
4. Include brief explanation of why true/false
5. Balance between true and false statements

=== POSITIVE EXAMPLES ===
✅ Statement: "OSPF is a link-state routing protocol that uses Dijkstra's algorithm."
   Correct: true
   Explanation: "OSPF builds a complete topology map and uses SPF algorithm to calculate best paths."

✅ Statement: "UDP provides guaranteed delivery of packets between hosts."
   Correct: false
   Explanation: "UDP is connectionless and provides best-effort delivery without guarantees. TCP provides reliable delivery."

✅ Statement: "A Layer 2 switch makes forwarding decisions based on IP addresses."
   Correct: false
   Explanation: "Layer 2 switches use MAC addresses for forwarding. Routers (Layer 3) use IP addresses."

=== NEGATIVE EXAMPLES ===
❌ "OSPF is not a protocol that doesn't use link-state." (double negative)
❌ "Routers are devices." (too vague, technically true but meaningless)
❌ "VLANs can sometimes be useful in some networks." (ambiguous)
❌ "TCP and UDP are both transport protocols that handle different scenarios." (tests two things)

{negative_examples}

=== OUTPUT FORMAT ===
Return JSON array:
[
  {{
    "card_id": "{section_id}-TF-001",
    "front": "Clear declarative statement that is either true or false",
    "correct": true|false,
    "explanation": "Why this is true/false (1-2 sentences)",
    "tags": ["topic"],
    "source_refs": [
      {{
        "section_id": "{section_id}",
        "section_title": "title from header",
        "source_text_excerpt": "10-30 word excerpt this atom is based on"
      }}
    ],
    "knowledge_type": "factual|conceptual",
    "metadata": {{
      "difficulty": 1-5,
      "knowledge_type": "factual|conceptual",
      "derived_from_visual": false
    }}
  }}
]

Generate 3-5 true/false questions. Aim for ~50% true, ~50% false.

SECTION ID: {section_id}
CONTENT:
{content}"""


# =============================================================================
# Parsons Prompt (NSL)
# =============================================================================

PARSONS_PROMPT = """Generate Parsons problems from these CLI commands for interactive quizzes.

Parsons problems present code/commands in scrambled order for the learner to arrange correctly.

=== REQUIREMENTS ===
1. 4-8 steps per problem (cognitive load limit)
2. Each step: Single command or logical command group
3. Include mode transitions (enable, config t, interface)
4. Provide clear scenario of what to accomplish
5. Add 1-2 distractor steps (plausible but wrong)
6. Commands must be ACTUAL Cisco IOS syntax

=== POSITIVE EXAMPLES ===
✅ Scenario: "Configure interface GigabitEthernet0/0 with IP address 192.168.1.1/24 and enable it"
   Correct sequence:
   1. enable
   2. configure terminal
   3. interface GigabitEthernet0/0
   4. ip address 192.168.1.1 255.255.255.0
   5. no shutdown
   6. end
   Distractors: ["ip route 0.0.0.0 0.0.0.0 192.168.1.254", "vlan 10"]

✅ Scenario: "Create VLAN 100 named 'Engineering' and verify it was created"
   Correct sequence:
   1. enable
   2. configure terminal
   3. vlan 100
   4. name Engineering
   5. end
   6. show vlan brief
   Distractors: ["interface vlan 100", "switchport mode access"]

=== NEGATIVE EXAMPLES ===
❌ Single-word blocks like "enable" without context
❌ More than 10 blocks (cognitive overload)
❌ Fewer than 3 blocks (too simple)
❌ Blocks that aren't real Cisco commands
❌ Missing mode transitions (jumping from user to config-if)

{negative_examples}

=== OUTPUT FORMAT ===
Return JSON array:
[
  {{
    "card_id": "{section_id}-PAR-001",
    "scenario": "Specific task description (what to configure/accomplish)",
    "correct_sequence": ["cmd1", "cmd2", "cmd3", "cmd4", "cmd5"],
    "distractors": ["wrong_cmd1", "wrong_cmd2"],
    "starting_mode": "user EXEC|privileged EXEC|global config",
    "tags": ["commands", "configuration"],
    "source_refs": [
      {{
        "section_id": "{section_id}",
        "section_title": "title from header",
        "source_text_excerpt": "10-30 word excerpt this atom is based on"
      }}
    ],
    "metadata": {{
      "difficulty": 1-5,
      "knowledge_type": "procedural"
    }}
  }}
]

Generate 1-3 Parsons problems.

SECTION ID: {section_id}
COMMANDS AND CONTEXT:
{content}"""


# =============================================================================
# Matching Prompt (NSL)
# =============================================================================

MATCHING_PROMPT = """Generate matching exercises from this CCNA content for interactive quizzes.

=== REQUIREMENTS ===
1. MAXIMUM 6 pairs (working memory limit from cognitive science)
2. Each pair: Term → Definition/Description
3. All terms from same category (OSI layers, protocols, commands, etc.)
4. Definitions must be unique and distinguishable
5. No overlapping or ambiguous matches

=== POSITIVE EXAMPLES ===
✅ Topic: "OSI Model Layers"
   Pairs:
   - Physical (Layer 1) → Transmits raw bits over physical medium
   - Data Link (Layer 2) → Handles MAC addressing and frame delivery
   - Network (Layer 3) → Manages logical addressing and routing
   - Transport (Layer 4) → Provides end-to-end data delivery

✅ Topic: "Cisco Router Modes"
   Pairs:
   - Router> → User EXEC mode with limited commands
   - Router# → Privileged EXEC mode with full access
   - Router(config)# → Global configuration mode
   - Router(config-if)# → Interface configuration mode

=== NEGATIVE EXAMPLES ===
❌ More than 6 pairs (cognitive overload)
❌ Mixing unrelated categories (protocols + hardware + commands)
❌ Overlapping definitions that could match multiple terms
❌ Single-word definitions without context
❌ Definitions that are nearly identical

{negative_examples}

=== OUTPUT FORMAT ===
Return JSON array:
[
  {{
    "card_id": "{section_id}-MAT-001",
    "front": "Match the following [category] with their descriptions:",
    "pairs": [
      {{"left": "Term 1", "right": "Clear, unique definition 1"}},
      {{"left": "Term 2", "right": "Clear, unique definition 2"}},
      {{"left": "Term 3", "right": "Clear, unique definition 3"}},
      {{"left": "Term 4", "right": "Clear, unique definition 4"}}
    ],
    "tags": ["matching", "topic"],
    "source_refs": [
      {{
        "section_id": "{section_id}",
        "section_title": "title from header",
        "source_text_excerpt": "10-30 word excerpt this atom is based on"
      }}
    ],
    "knowledge_type": "factual",
    "metadata": {{
      "difficulty": 1-5,
      "knowledge_type": "factual",
      "derived_from_visual": false
    }}
  }}
]

Generate 1-2 matching exercises. Each with 4-6 pairs.

SECTION ID: {section_id}
CONTENT:
{content}"""


# =============================================================================
# Numeric/Calculation Prompt (Module 5 & 11)
# =============================================================================

NUMERIC_PROMPT = """Generate calculation-based flashcards from this CCNA number systems content.

=== REQUIREMENTS ===
1. Questions MUST involve ACTUAL CALCULATIONS
2. Include specific values to convert (IP addresses, subnet masks, binary strings)
3. Show the conversion process in the answer
4. Test understanding of WHY the conversion matters in networking

=== FEW-SHOT EXAMPLES: SCENARIO-BASED CALCULATIONS ===

**NEGATIVE EXAMPLE (Abstract - Do NOT Do This):**
Q: "How do you convert binary to decimal?"
A: "Multiply each bit by its positional power of 2 and sum the results."
(Problem: No actual calculation, just description)

**POSITIVE EXAMPLE (Calculation with Context - Do This):**
Q: "A subnet mask has the binary value 11111111.11111111.11111111.11000000 in the last octet. What decimal value is this and what CIDR prefix does it represent?"
A: "The binary 11000000 = 128 + 64 = 192, so the mask is 255.255.255.192. This equals /26 (26 ones total), providing 64 addresses per subnet with 62 usable hosts." (27 words)
(Why better: Actual calculation + practical meaning)

---

**NEGATIVE EXAMPLE (Abstract - Do NOT Do This):**
Q: "What is the binary representation of 192?"
A: "11000000"
(Problem: Raw conversion without networking context)

**POSITIVE EXAMPLE (IP Address Context - Do This):**
Q: "A network engineer sees IP address 192.168.10.75. Convert the first octet (192) to binary and explain how this places it in the address class system."
A: "192 in binary is 11000000 (128+64=192). Since it starts with '110', this is a Class C address by the original classful system, indicating a default /24 mask." (26 words)
(Why better: Binary conversion applied to real IP addressing)

---

**NEGATIVE EXAMPLE (Abstract - Do NOT Do This):**
Q: "Convert hexadecimal FF to decimal."
A: "255"
(Problem: No context, just math)

**POSITIVE EXAMPLE (MAC/IPv6 Context - Do This):**
Q: "A MAC address shows FF:FF:FF:FF:FF:FF. What decimal value does each 'FF' represent, and what type of MAC address is this?"
A: "Each FF in hexadecimal equals 255 in decimal (15×16 + 15 = 255). FF:FF:FF:FF:FF:FF is the broadcast MAC address, used to send frames to all devices on the local network segment." (31 words)
(Why better: Hex conversion in actual networking usage)

---

**POSITIVE EXAMPLE (Subnetting Calculation):**
Q: "Given the network 172.16.0.0/20, calculate the subnet mask in dotted decimal and determine how many host addresses are available per subnet."
A: "A /20 means 20 network bits, leaving 12 host bits. The mask is 255.255.240.0 (the third octet: 11110000 = 240). Each subnet has 2^12 - 2 = 4094 usable host addresses." (30 words)

**POSITIVE EXAMPLE (AND Operation):**
Q: "Host 192.168.1.130 with mask 255.255.255.192 needs to determine its network address. Show the AND operation result for the last octet."
A: "130 AND 192: Binary 10000010 AND 11000000 = 10000000 = 128. The network address is 192.168.1.128. This host is in the 192.168.1.128/26 subnet." (22 words)

=== OUTPUT FORMAT ===
Return JSON array:
[
  {{
    "card_id": "{section_id}-NUM-001",
    "front": "specific calculation question with actual values",
    "back": "step-by-step answer showing calculation AND networking significance",
    "tags": ["number-systems", "binary|hex|subnetting"],
    "source_refs": [
      {{
        "section_id": "{section_id}",
        "section_title": "title from header",
        "source_text_excerpt": "10-30 word excerpt this atom is based on"
      }}
    ],
    "knowledge_type": "procedural",
    "metadata": {{
      "difficulty": 1-5,
      "knowledge_type": "procedural",
      "calculation_type": "binary_decimal|hex_decimal|subnetting|and_operation",
      "derived_from_visual": false
    }}
  }}
]

Generate 5-8 calculation cards. Increment suffix: 001, 002, 003...

SECTION ID: {section_id}
CONTENT:
{content}"""


# =============================================================================
# Prompt Factory
# =============================================================================

def get_prompt(
    atom_type: str,
    section_id: str,
    content: str,
    include_negative_examples: bool = True,
) -> str:
    """
    Get the appropriate prompt for an atom type.

    Args:
        atom_type: Type of atom (flashcard, cloze, mcq, true_false, parsons, matching)
        section_id: CCNA section identifier
        content: Source content to generate from
        include_negative_examples: Whether to include negative examples section

    Returns:
        Formatted prompt string
    """
    negative = NEGATIVE_EXAMPLES if include_negative_examples else ""

    prompts = {
        "flashcard": FLASHCARD_PROMPT,
        "cloze": CLOZE_PROMPT,
        "mcq": MCQ_PROMPT,
        "true_false": TRUE_FALSE_PROMPT,
        "parsons": PARSONS_PROMPT,
        "matching": MATCHING_PROMPT,
        "numeric": NUMERIC_PROMPT,  # For Module 5 & 11 calculations
    }

    template = prompts.get(atom_type.lower(), FLASHCARD_PROMPT)

    return template.format(
        section_id=section_id,
        content=content,
        negative_examples=negative,
    )


def get_system_prompt() -> str:
    """Get the system prompt for LLM initialization."""
    return SYSTEM_PROMPT


# =============================================================================
# Type Distribution Configuration
# =============================================================================

# Recommended distribution for comprehensive learning
ATOM_TYPE_DISTRIBUTION = {
    # Anki (spaced repetition)
    "flashcard": 0.40,  # 40% - Core retrieval practice
    "cloze": 0.15,      # 15% - Terminology reinforcement

    # NSL (interactive quizzes)
    "mcq": 0.20,        # 20% - Discrimination practice
    "true_false": 0.10, # 10% - Quick knowledge checks
    "parsons": 0.10,    # 10% - Procedural learning (CLI)
    "matching": 0.05,   # 5% - Category/relationship learning
}


def get_types_for_section(
    has_commands: bool = False,
    has_key_terms: bool = False,
    has_tables: bool = False,
    concept_count: int = 0,
) -> list[str]:
    """
    Determine which atom types to generate based on section content.

    Args:
        has_commands: Section contains CLI commands
        has_key_terms: Section contains bold/key terminology
        has_tables: Section contains comparison tables
        concept_count: Number of distinct concepts in section

    Returns:
        List of atom types to generate
    """
    types = ["flashcard"]  # Always generate flashcards

    if has_key_terms:
        types.append("cloze")

    if concept_count >= 2:
        types.append("mcq")
        types.append("true_false")

    if has_commands:
        types.append("parsons")

    if has_tables or concept_count >= 4:
        types.append("matching")

    return types
