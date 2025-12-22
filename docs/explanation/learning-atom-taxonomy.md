# learning atom taxonomy

## purpose

Define the interaction primitives used by Cortex-CLI. These are cognitive operations, not UI widgets.

## classification axes

- engagement mode (icap): passive, active, constructive, interactive
- element interactivity (clt): 0.0 to 1.0
- knowledge dimension: factual, conceptual, procedural, metacognitive

## atom families (100+ types)

### perception and discrimination

- visual hotspot
- visual search
- error highlighting
- image labeling
- region selection
- audio discrimination
- pitch matching
- phoneme matching
- color grading
- 3d rotation match
- waveform alignment
- reaction time check
- fuzzy pattern match

### recognition and selection

- binary choice (true/false)
- yes/no
- valid/invalid
- single select mcq
- multi select mcq
- negative selection
- best answer
- least incorrect
- matching with distractors
- spot the error

### recall and entry

- short answer exact
- short answer regex
- cloze single
- cloze multi
- cloze with hints
- cloze dropdown
- cloze word bank
- free recall (short)
- free recall (long)
- oral recall
- diagram recall
- code recall
- list recall
- ordered list recall

### flashcard variants

- front to back
- back to front
- bidirectional
- image to term
- audio to term
- symbol to meaning

### structural and relational

- matching pairs (term/definition)
- concept/example matching
- cause/effect matching
- input/output matching
- symbol/meaning matching
- api/behavior matching
- association buckets
- sorting or grouping
- taxonomy placement
- class membership
- matrix classification
- graph construction
- network mapping

### ordering and sequencing

- step ordering
- timeline ordering
- process flow
- algorithm steps
- protocol phases
- execution order
- lifecycle ordering
- dependency ordering

### parsons family

- ordered parsons
- scrambled parsons
- distractor parsons
- faded parsons
- block constrained parsons
- 2d parsons (indentation)

### numeric and symbolic

- numeric exact
- numeric range
- multi step numeric
- unit aware numeric
- formula construction
- equation solving
- logic expressions
- boolean algebra
- regex construction
- sql query prediction
- big o derivation
- subnet calculation
- hex/binary conversion

### code understanding

- output prediction
- state tracing
- control flow tracing
- variable evolution table
- explain this code
- annotate code
- find the bug
- spot undefined behavior

### code construction

- write the line
- complete the function
- implement algorithm skeleton
- write from specification
- translate pseudocode to code
- language translation (python/js)
- refactoring for complexity

### debugging and fault isolation

- bug identification
- root cause analysis
- minimal fix selection
- error message interpretation
- log analysis
- failing test diagnosis
- fault isolation

### configuration and cli

- command sequencing
- command completion
- config ordering
- which command does this
- missing command detection
- stateful cli reasoning
- exec vs config mode

### system and architecture reasoning

- architecture comparison
- trade off analysis
- component responsibility
- failure mode prediction
- scalability reasoning
- security boundary identification

### algorithmic reasoning

- dry run algorithm
- invariant identification
- edge case identification
- complexity analysis
- correctness proof (informal)
- optimization choice

### constraint and design

- design under constraints
- select best pattern
- anti pattern detection
- api design decision
- refactor choice

### testing and verification

- test case generation
- boundary testing
- property based reasoning
- expected vs actual comparison
- coverage gap identification

### scenario and simulation

- case analysis
- what would you do
- diagnosis task
- output prediction (system)
- side effect prediction
- failure injection
- concurrency simulation
- race condition reasoning
- state manipulation
- cli simulation

### explanation and elaboration

- explain in own words
- teach back
- mechanism explanation
- causal chain explanation
- why not the alternative

### metacognitive

- confidence rating
- difficulty rating
- error source tagging
- strategy selection
- self explanation
- reflection prompt
- assumption audit
- judgment of learning
- effort rating

### creative and generative

- generate example
- generate counterexample
- create analogy
- create test case
- essay response
- diagram drawing
- graph plotting
- audio recording

### security specific

- threat modeling
- attack vector matching
- vulnerability identification
- mitigation selection
- trust boundary reasoning

## implementation notes

- each atom type maps to a handler and a schema
- distractors must map to misconception ids
- grading logic is separate from content
- icap and clt fields are required metadata

## links

- schema-migration-plan.md
- bdd-testing-strategy.md
- ci-cd-pipeline.md
