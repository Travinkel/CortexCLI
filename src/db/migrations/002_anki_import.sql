-- Migration 002: Anki Import Staging
--
-- Creates staging table for importing existing Anki decks.
-- Enables:
--   1. Bulk import of Anki cards with FSRS stats
--   2. Prerequisite tag parsing (tag:prereq:domain:topic:subtopic)
--   3. Quality analysis on imported cards
--   4. Identification of non-atomic cards for splitting
--
-- Data Flow:
--   Anki Deck → stg_anki_cards (this table) → Quality Analysis → clean_atoms

-- ========================================
-- STAGING TABLE: Anki Import
-- Raw import from AnkiConnect API
-- ========================================

CREATE TABLE IF NOT EXISTS stg_anki_cards (
    -- Anki Identifiers
    anki_note_id BIGINT PRIMARY KEY,    -- Anki's internal note ID
    anki_card_id BIGINT,                -- Anki's internal card ID
    card_id TEXT,                       -- Custom Card ID field (e.g., "NET-M1-015")

    -- Core Content
    front TEXT NOT NULL,
    back TEXT,
    deck_name TEXT NOT NULL,
    note_type TEXT,

    -- Tags (raw and parsed)
    tags TEXT[],                        -- Array of tag strings
    raw_tags_json JSONB,                -- Full tag data from Anki

    -- Prerequisite Extraction (from tag:prereq:domain:topic:subtopic)
    has_prerequisites BOOLEAN DEFAULT false,
    prerequisite_tags TEXT[],           -- Only prerequisite tags
    prerequisite_hierarchy JSONB,       -- Parsed: [{"domain": "cs", "topic": "networking", "subtopic": "ipv4"}]

    -- FSRS Scheduling Stats (from AnkiConnect)
    fsrs_stability_days DECIMAL(8,2),   -- Memory stability
    fsrs_difficulty DECIMAL(5,4),       -- Difficulty rating (0-1)
    fsrs_retrievability DECIMAL(5,4),   -- Current recall probability (0-1)
    interval_days INT,                  -- Current interval
    ease_factor DECIMAL(4,3),           -- Ease factor
    review_count INT DEFAULT 0,         -- Total reviews
    lapses INT DEFAULT 0,               -- Failed reviews
    last_review TIMESTAMPTZ,            -- Last review timestamp
    due_date DATE,                      -- Next due date
    queue TEXT,                         -- Anki queue state
    card_type TEXT,                     -- new, learning, review, relearning

    -- Performance Metrics (from review log)
    correct_count INT,                  -- Successful reviews
    accuracy_percent DECIMAL(5,2),      -- Success rate
    avg_response_time_ms INT,           -- Average response time

    -- Quality Analysis (populated after import)
    quality_grade TEXT,                 -- A/B/C/D/F (from atomicity check)
    is_atomic BOOLEAN,                  -- Passes atomicity thresholds
    front_word_count INT,
    back_word_count INT,
    front_char_count INT,
    back_char_count INT,
    atomicity_issues JSONB,             -- Array of issue codes
    needs_split BOOLEAN DEFAULT false,  -- Flagged for card splitting

    -- Linking to Clean Tables
    clean_atom_id UUID REFERENCES clean_atoms(id) ON DELETE SET NULL,
    import_status TEXT DEFAULT 'pending', -- 'pending', 'processed', 'merged', 'split', 'error'
    import_notes TEXT,

    -- Raw Data (full AnkiConnect response for debugging)
    raw_anki_data JSONB,                -- Complete note/card data from Anki

    -- Import Metadata
    imported_at TIMESTAMPTZ DEFAULT now(),
    processed_at TIMESTAMPTZ,
    import_batch_id TEXT
);

-- ========================================
-- INDEXES
-- ========================================

-- Lookup indexes
CREATE INDEX IF NOT EXISTS idx_stg_anki_card_id ON stg_anki_cards(card_id);
CREATE INDEX IF NOT EXISTS idx_stg_anki_deck ON stg_anki_cards(deck_name);
CREATE INDEX IF NOT EXISTS idx_stg_anki_import_status ON stg_anki_cards(import_status);

-- Quality analysis indexes
CREATE INDEX IF NOT EXISTS idx_stg_anki_quality_grade ON stg_anki_cards(quality_grade);
CREATE INDEX IF NOT EXISTS idx_stg_anki_needs_split ON stg_anki_cards(needs_split) WHERE needs_split = true;
CREATE INDEX IF NOT EXISTS idx_stg_anki_not_atomic ON stg_anki_cards(is_atomic) WHERE is_atomic = false;

-- Prerequisite indexes
CREATE INDEX IF NOT EXISTS idx_stg_anki_has_prereqs ON stg_anki_cards(has_prerequisites) WHERE has_prerequisites = true;
CREATE INDEX IF NOT EXISTS idx_stg_anki_prereq_tags ON stg_anki_cards USING GIN (prerequisite_tags);

-- FSRS stats indexes
CREATE INDEX IF NOT EXISTS idx_stg_anki_due_date ON stg_anki_cards(due_date) WHERE due_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_stg_anki_review_count ON stg_anki_cards(review_count);

-- Tag search (GIN index for array contains queries)
CREATE INDEX IF NOT EXISTS idx_stg_anki_tags ON stg_anki_cards USING GIN (tags);

-- JSONB search indexes
CREATE INDEX IF NOT EXISTS idx_stg_anki_raw_data ON stg_anki_cards USING GIN (raw_anki_data);
CREATE INDEX IF NOT EXISTS idx_stg_anki_prereq_hierarchy ON stg_anki_cards USING GIN (prerequisite_hierarchy);
CREATE INDEX IF NOT EXISTS idx_stg_anki_atomicity_issues ON stg_anki_cards USING GIN (atomicity_issues);

-- ========================================
-- HELPER VIEWS
-- ========================================

-- View: Non-atomic cards needing quality improvement
CREATE OR REPLACE VIEW v_anki_needs_improvement AS
SELECT
    anki_note_id,
    card_id,
    front,
    back,
    quality_grade,
    is_atomic,
    needs_split,
    atomicity_issues,
    front_word_count,
    back_word_count
FROM stg_anki_cards
WHERE import_status = 'pending'
  AND (
      quality_grade IN ('D', 'F')
      OR is_atomic = false
      OR needs_split = true
  )
ORDER BY quality_grade DESC, back_word_count DESC;

-- View: Cards with prerequisites (for prerequisite system)
CREATE OR REPLACE VIEW v_anki_with_prerequisites AS
SELECT
    anki_note_id,
    card_id,
    front,
    prerequisite_tags,
    prerequisite_hierarchy,
    deck_name,
    review_count,
    accuracy_percent
FROM stg_anki_cards
WHERE has_prerequisites = true
  AND import_status = 'pending'
ORDER BY deck_name, card_id;

-- View: FSRS stats summary by deck
CREATE OR REPLACE VIEW v_anki_fsrs_stats_by_deck AS
SELECT
    deck_name,
    COUNT(*) as total_cards,
    COUNT(*) FILTER (WHERE review_count > 0) as reviewed_cards,
    AVG(fsrs_stability_days) as avg_stability_days,
    AVG(fsrs_difficulty) as avg_difficulty,
    AVG(fsrs_retrievability) as avg_retrievability,
    AVG(accuracy_percent) as avg_accuracy,
    AVG(interval_days) as avg_interval_days,
    COUNT(*) FILTER (WHERE due_date <= CURRENT_DATE) as due_today_count
FROM stg_anki_cards
GROUP BY deck_name
ORDER BY deck_name;

-- View: Quality grade distribution
CREATE OR REPLACE VIEW v_anki_quality_distribution AS
SELECT
    quality_grade,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage,
    AVG(back_word_count) as avg_back_words,
    COUNT(*) FILTER (WHERE needs_split = true) as needs_split_count
FROM stg_anki_cards
WHERE quality_grade IS NOT NULL
GROUP BY quality_grade
ORDER BY quality_grade;

-- View: Prerequisite tag hierarchy (for building prerequisite graph)
CREATE OR REPLACE VIEW v_anki_prerequisite_graph AS
SELECT DISTINCT
    jsonb_array_elements(prerequisite_hierarchy)->>'full_tag' as prerequisite_tag,
    jsonb_array_elements(prerequisite_hierarchy)->>'domain' as domain,
    jsonb_array_elements(prerequisite_hierarchy)->>'topic' as topic,
    jsonb_array_elements(prerequisite_hierarchy)->>'subtopic' as subtopic,
    COUNT(*) as card_count
FROM stg_anki_cards
WHERE has_prerequisites = true
GROUP BY
    prerequisite_tag,
    domain,
    topic,
    subtopic
ORDER BY domain, topic, subtopic;

-- ========================================
-- AUDIT TABLE: Anki Import History
-- ========================================

CREATE TABLE IF NOT EXISTS anki_import_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    import_batch_id TEXT NOT NULL,
    deck_name TEXT NOT NULL,
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT DEFAULT 'running',      -- 'running', 'completed', 'failed'

    -- Import stats
    cards_imported INT DEFAULT 0,
    cards_with_fsrs INT DEFAULT 0,
    cards_with_prerequisites INT DEFAULT 0,
    cards_needing_split INT DEFAULT 0,

    -- Quality distribution
    grade_a_count INT DEFAULT 0,
    grade_b_count INT DEFAULT 0,
    grade_c_count INT DEFAULT 0,
    grade_d_count INT DEFAULT 0,
    grade_f_count INT DEFAULT 0,

    error_message TEXT,
    details JSONB
);

CREATE INDEX IF NOT EXISTS idx_anki_import_batch ON anki_import_log(import_batch_id);
CREATE INDEX IF NOT EXISTS idx_anki_import_started ON anki_import_log(started_at DESC);

-- ========================================
-- FUNCTIONS: Helper Functions
-- ========================================

-- Function: Parse prerequisite tags from tag array
CREATE OR REPLACE FUNCTION parse_prerequisite_tags(tags TEXT[])
RETURNS JSONB
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    prereq_tags TEXT[];
    parsed_hierarchy JSONB := '[]'::JSONB;
    tag TEXT;
    parts TEXT[];
    tag_obj JSONB;
BEGIN
    -- Filter prerequisite tags
    SELECT ARRAY_AGG(t)
    INTO prereq_tags
    FROM unnest(tags) AS t
    WHERE t LIKE 'tag:prereq:%';

    IF prereq_tags IS NULL OR array_length(prereq_tags, 1) IS NULL THEN
        RETURN '{
            "has_prerequisites": false,
            "prerequisite_tags": [],
            "parsed_hierarchy": []
        }'::JSONB;
    END IF;

    -- Parse each prerequisite tag
    FOREACH tag IN ARRAY prereq_tags
    LOOP
        parts := string_to_array(tag, ':');

        IF array_length(parts, 1) >= 3 THEN
            tag_obj := jsonb_build_object(
                'full_tag', tag,
                'domain', CASE WHEN array_length(parts, 1) > 2 THEN parts[3] ELSE NULL END,
                'topic', CASE WHEN array_length(parts, 1) > 3 THEN parts[4] ELSE NULL END,
                'subtopic', CASE WHEN array_length(parts, 1) > 4 THEN parts[5] ELSE NULL END
            );

            parsed_hierarchy := parsed_hierarchy || tag_obj;
        END IF;
    END LOOP;

    RETURN jsonb_build_object(
        'has_prerequisites', true,
        'prerequisite_tags', to_jsonb(prereq_tags),
        'parsed_hierarchy', parsed_hierarchy
    );
END;
$$;

-- Function: Count words in text
CREATE OR REPLACE FUNCTION count_words(text_content TEXT)
RETURNS INT
LANGUAGE plpgsql
IMMUTABLE
AS $$
BEGIN
    IF text_content IS NULL OR trim(text_content) = '' THEN
        RETURN 0;
    END IF;

    RETURN array_length(regexp_split_to_array(trim(text_content), '\s+'), 1);
END;
$$;

-- ========================================
-- COMMENTS
-- ========================================

COMMENT ON TABLE stg_anki_cards IS 'Staging table for Anki deck import with FSRS stats and prerequisite parsing';
COMMENT ON COLUMN stg_anki_cards.prerequisite_hierarchy IS 'Parsed tag:prereq:domain:topic:subtopic hierarchy as JSONB array';
COMMENT ON COLUMN stg_anki_cards.quality_grade IS 'Atomicity quality grade: A (excellent), B (good), C (acceptable), D (needs work), F (requires rewrite/split)';
COMMENT ON COLUMN stg_anki_cards.needs_split IS 'Card covers multiple concepts and should be split into atomic pieces';
COMMENT ON COLUMN stg_anki_cards.fsrs_stability_days IS 'FSRS memory stability in days (higher = stronger memory)';
COMMENT ON COLUMN stg_anki_cards.fsrs_difficulty IS 'FSRS difficulty rating 0-1 (higher = more difficult)';
COMMENT ON COLUMN stg_anki_cards.fsrs_retrievability IS 'Current recall probability 0-1 (estimated by FSRS)';

COMMENT ON FUNCTION parse_prerequisite_tags IS 'Extract and parse tag:prereq:domain:topic:subtopic tags from tag array';
COMMENT ON FUNCTION count_words IS 'Count words in text content (split on whitespace)';
