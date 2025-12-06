-- Migration 004: Semantic Embeddings Infrastructure (Phase 2.5)
-- NO PGVECTOR VERSION - For systems without pgvector extension
--
-- This version stores embeddings as BYTEA (serialized numpy arrays)
-- and performs similarity calculations in Python instead of SQL.
--
-- Implements embedding-based semantic analysis for learning atoms.
-- Enables:
--   1. Semantic duplicate detection (cosine similarity > 0.85)
--   2. Prerequisite inference using embedding similarity
--   3. Knowledge state clustering for adaptive learning
--
-- Technology:
--   - Embeddings stored as BYTEA (serialized with numpy)
--   - Similarity calculations done in Python
--   - 384-dimensional embeddings from sentence-transformers (all-MiniLM-L6-v2)

-- ========================================
-- ALTER TABLE: Add Embedding Columns
-- Using BYTEA instead of vector for portability
-- ========================================

-- Add embedding columns to clean_atoms (canonical table)
ALTER TABLE clean_atoms
ADD COLUMN IF NOT EXISTS embedding BYTEA,
ADD COLUMN IF NOT EXISTS embedding_model TEXT DEFAULT 'all-MiniLM-L6-v2',
ADD COLUMN IF NOT EXISTS embedding_generated_at TIMESTAMPTZ;

-- Add embedding columns to stg_anki_cards (staging table)
ALTER TABLE stg_anki_cards
ADD COLUMN IF NOT EXISTS embedding BYTEA,
ADD COLUMN IF NOT EXISTS embedding_model TEXT DEFAULT 'all-MiniLM-L6-v2',
ADD COLUMN IF NOT EXISTS embedding_generated_at TIMESTAMPTZ;

-- Add embedding column to clean_concepts (for prerequisite inference)
ALTER TABLE clean_concepts
ADD COLUMN IF NOT EXISTS embedding BYTEA,
ADD COLUMN IF NOT EXISTS embedding_model TEXT DEFAULT 'all-MiniLM-L6-v2',
ADD COLUMN IF NOT EXISTS embedding_generated_at TIMESTAMPTZ;

-- ========================================
-- INDEXES: Standard indexes (no HNSW without pgvector)
-- ========================================

-- Index for filtering atoms without embeddings
CREATE INDEX IF NOT EXISTS idx_clean_atoms_no_embedding
ON clean_atoms(id) WHERE embedding IS NULL;

CREATE INDEX IF NOT EXISTS idx_stg_anki_no_embedding
ON stg_anki_cards(anki_note_id) WHERE embedding IS NULL;

-- ========================================
-- TABLE: Semantic Duplicates
-- Stores detected duplicate pairs with similarity scores
-- ========================================

CREATE TABLE IF NOT EXISTS semantic_duplicates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Atom pair (ordered: atom_id_1 < atom_id_2 to prevent duplicates)
    atom_id_1 UUID NOT NULL REFERENCES clean_atoms(id) ON DELETE CASCADE,
    atom_id_2 UUID NOT NULL REFERENCES clean_atoms(id) ON DELETE CASCADE,

    -- Similarity metrics
    similarity_score DECIMAL(5,4) NOT NULL CHECK (similarity_score BETWEEN 0 AND 1),
    detection_method TEXT DEFAULT 'embedding',  -- 'embedding', 'fuzzy', 'exact'

    -- Review workflow
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'merged', 'dismissed', 'reviewed')),
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,

    -- If merged, which atom was kept
    merged_into_atom_id UUID REFERENCES clean_atoms(id) ON DELETE SET NULL,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- Ensure unique pairs (ordered)
    UNIQUE(atom_id_1, atom_id_2),

    -- Ensure atom_id_1 < atom_id_2 for consistent ordering
    CHECK (atom_id_1 < atom_id_2)
);

-- Indexes for semantic_duplicates
CREATE INDEX IF NOT EXISTS idx_semantic_dup_atom1 ON semantic_duplicates(atom_id_1);
CREATE INDEX IF NOT EXISTS idx_semantic_dup_atom2 ON semantic_duplicates(atom_id_2);
CREATE INDEX IF NOT EXISTS idx_semantic_dup_status ON semantic_duplicates(status);
CREATE INDEX IF NOT EXISTS idx_semantic_dup_score ON semantic_duplicates(similarity_score DESC);
CREATE INDEX IF NOT EXISTS idx_semantic_dup_pending ON semantic_duplicates(created_at DESC) WHERE status = 'pending';

-- ========================================
-- TABLE: Inferred Prerequisites
-- AI-suggested prerequisite relationships based on embedding similarity
-- ========================================

CREATE TABLE IF NOT EXISTS inferred_prerequisites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- The atom that needs this prerequisite
    source_atom_id UUID NOT NULL REFERENCES clean_atoms(id) ON DELETE CASCADE,

    -- The concept suggested as prerequisite
    target_concept_id UUID NOT NULL REFERENCES clean_concepts(id) ON DELETE CASCADE,

    -- Similarity and confidence
    similarity_score DECIMAL(5,4) NOT NULL CHECK (similarity_score BETWEEN 0 AND 1),
    confidence TEXT DEFAULT 'medium' CHECK (confidence IN ('low', 'medium', 'high')),
    inference_method TEXT DEFAULT 'embedding',  -- 'embedding', 'tag', 'explicit', 'graph'

    -- Evidence supporting the inference
    evidence_atoms UUID[],  -- Other atoms that support this relationship
    evidence_score DECIMAL(5,4),  -- Aggregate evidence strength

    -- Review workflow
    status TEXT DEFAULT 'suggested' CHECK (status IN ('suggested', 'accepted', 'rejected', 'applied')),
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,

    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),

    -- Prevent duplicate suggestions
    UNIQUE(source_atom_id, target_concept_id)
);

-- Indexes for inferred_prerequisites
CREATE INDEX IF NOT EXISTS idx_inferred_prereq_source ON inferred_prerequisites(source_atom_id);
CREATE INDEX IF NOT EXISTS idx_inferred_prereq_target ON inferred_prerequisites(target_concept_id);
CREATE INDEX IF NOT EXISTS idx_inferred_prereq_status ON inferred_prerequisites(status);
CREATE INDEX IF NOT EXISTS idx_inferred_prereq_confidence ON inferred_prerequisites(confidence);
CREATE INDEX IF NOT EXISTS idx_inferred_prereq_score ON inferred_prerequisites(similarity_score DESC);
CREATE INDEX IF NOT EXISTS idx_inferred_prereq_suggested ON inferred_prerequisites(created_at DESC) WHERE status = 'suggested';

-- ========================================
-- TABLE: Knowledge Clusters
-- Groups of semantically related atoms
-- (centroid stored as BYTEA instead of vector)
-- ========================================

CREATE TABLE IF NOT EXISTS knowledge_clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Cluster metadata
    name TEXT,
    description TEXT,

    -- Cluster embedding (centroid) - stored as BYTEA
    centroid BYTEA,

    -- Clustering parameters
    cluster_method TEXT DEFAULT 'kmeans' CHECK (cluster_method IN ('kmeans', 'hierarchical', 'dbscan', 'hdbscan')),
    cluster_params JSONB,  -- {"n_clusters": 10, "random_state": 42}

    -- Scope (optional: cluster within a concept area or globally)
    concept_area_id UUID REFERENCES clean_concept_areas(id) ON DELETE SET NULL,

    -- Quality metrics
    silhouette_score DECIMAL(5,4),  -- Cluster quality (-1 to 1)
    intra_cluster_distance DECIMAL(8,4),  -- Avg distance to centroid

    -- Lifecycle
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for knowledge_clusters
CREATE INDEX IF NOT EXISTS idx_knowledge_clusters_active ON knowledge_clusters(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_knowledge_clusters_method ON knowledge_clusters(cluster_method);
CREATE INDEX IF NOT EXISTS idx_knowledge_clusters_area ON knowledge_clusters(concept_area_id);

-- ========================================
-- TABLE: Knowledge Cluster Members
-- Junction table linking atoms to clusters
-- ========================================

CREATE TABLE IF NOT EXISTS knowledge_cluster_members (
    cluster_id UUID NOT NULL REFERENCES knowledge_clusters(id) ON DELETE CASCADE,
    atom_id UUID NOT NULL REFERENCES clean_atoms(id) ON DELETE CASCADE,

    -- Distance from atom to cluster centroid
    distance_to_centroid DECIMAL(8,4),

    -- Membership probability (for soft clustering like GMM)
    membership_probability DECIMAL(5,4) DEFAULT 1.0,

    -- Is this atom the cluster exemplar (most representative)?
    is_exemplar BOOLEAN DEFAULT false,

    created_at TIMESTAMPTZ DEFAULT now(),

    PRIMARY KEY (cluster_id, atom_id)
);

-- Indexes for knowledge_cluster_members
CREATE INDEX IF NOT EXISTS idx_cluster_members_atom ON knowledge_cluster_members(atom_id);
CREATE INDEX IF NOT EXISTS idx_cluster_members_distance ON knowledge_cluster_members(distance_to_centroid);
CREATE INDEX IF NOT EXISTS idx_cluster_members_exemplar ON knowledge_cluster_members(cluster_id) WHERE is_exemplar = true;

-- ========================================
-- TABLE: Embedding Generation Log
-- Audit trail for embedding operations
-- ========================================

CREATE TABLE IF NOT EXISTS embedding_generation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Batch identification
    batch_id TEXT NOT NULL,
    source_table TEXT NOT NULL,  -- 'clean_atoms', 'stg_anki_cards', 'clean_concepts'

    -- Timing
    started_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ,
    status TEXT DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),

    -- Statistics
    total_records INT DEFAULT 0,
    records_processed INT DEFAULT 0,
    records_skipped INT DEFAULT 0,  -- Already had embeddings
    records_failed INT DEFAULT 0,

    -- Configuration
    model_name TEXT DEFAULT 'all-MiniLM-L6-v2',
    batch_size INT,
    regenerate BOOLEAN DEFAULT false,

    -- Error tracking
    error_message TEXT,
    failed_record_ids TEXT[],

    details JSONB
);

-- Indexes for embedding_generation_log
CREATE INDEX IF NOT EXISTS idx_embedding_log_batch ON embedding_generation_log(batch_id);
CREATE INDEX IF NOT EXISTS idx_embedding_log_started ON embedding_generation_log(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_embedding_log_status ON embedding_generation_log(status);

-- ========================================
-- VIEWS: Semantic Analysis
-- ========================================

-- View: Atoms without embeddings (need processing)
CREATE OR REPLACE VIEW v_atoms_needing_embedding AS
SELECT
    id,
    card_id,
    front,
    back,
    concept_id,
    created_at
FROM clean_atoms
WHERE embedding IS NULL
ORDER BY created_at DESC;

-- View: Pending semantic duplicates for review
CREATE OR REPLACE VIEW v_pending_duplicates AS
SELECT
    sd.id as duplicate_id,
    sd.similarity_score,
    sd.detection_method,
    sd.created_at,
    a1.id as atom1_id,
    a1.card_id as atom1_card_id,
    a1.front as atom1_front,
    a1.back as atom1_back,
    a2.id as atom2_id,
    a2.card_id as atom2_card_id,
    a2.front as atom2_front,
    a2.back as atom2_back
FROM semantic_duplicates sd
JOIN clean_atoms a1 ON sd.atom_id_1 = a1.id
JOIN clean_atoms a2 ON sd.atom_id_2 = a2.id
WHERE sd.status = 'pending'
ORDER BY sd.similarity_score DESC;

-- View: High-confidence prerequisite suggestions
CREATE OR REPLACE VIEW v_prerequisite_suggestions AS
SELECT
    ip.id as suggestion_id,
    ip.similarity_score,
    ip.confidence,
    ip.created_at,
    a.id as atom_id,
    a.card_id,
    a.front as atom_front,
    c.id as concept_id,
    c.name as concept_name,
    c.definition as concept_definition
FROM inferred_prerequisites ip
JOIN clean_atoms a ON ip.source_atom_id = a.id
JOIN clean_concepts c ON ip.target_concept_id = c.id
WHERE ip.status = 'suggested'
ORDER BY ip.confidence DESC, ip.similarity_score DESC;

-- View: Cluster statistics
CREATE OR REPLACE VIEW v_cluster_stats AS
SELECT
    kc.id as cluster_id,
    kc.name,
    kc.cluster_method,
    kc.silhouette_score,
    COUNT(kcm.atom_id) as member_count,
    AVG(kcm.distance_to_centroid) as avg_distance,
    MIN(kcm.distance_to_centroid) as min_distance,
    MAX(kcm.distance_to_centroid) as max_distance
FROM knowledge_clusters kc
LEFT JOIN knowledge_cluster_members kcm ON kc.id = kcm.cluster_id
WHERE kc.is_active = true
GROUP BY kc.id, kc.name, kc.cluster_method, kc.silhouette_score
ORDER BY member_count DESC;

-- View: Embedding coverage statistics
CREATE OR REPLACE VIEW v_embedding_coverage AS
SELECT
    'clean_atoms' as table_name,
    COUNT(*) as total_records,
    COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_embedding,
    COUNT(*) FILTER (WHERE embedding IS NULL) as without_embedding,
    ROUND(COUNT(*) FILTER (WHERE embedding IS NOT NULL) * 100.0 / NULLIF(COUNT(*), 0), 2) as coverage_percent
FROM clean_atoms
UNION ALL
SELECT
    'stg_anki_cards' as table_name,
    COUNT(*) as total_records,
    COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_embedding,
    COUNT(*) FILTER (WHERE embedding IS NULL) as without_embedding,
    ROUND(COUNT(*) FILTER (WHERE embedding IS NOT NULL) * 100.0 / NULLIF(COUNT(*), 0), 2) as coverage_percent
FROM stg_anki_cards
UNION ALL
SELECT
    'clean_concepts' as table_name,
    COUNT(*) as total_records,
    COUNT(*) FILTER (WHERE embedding IS NOT NULL) as with_embedding,
    COUNT(*) FILTER (WHERE embedding IS NULL) as without_embedding,
    ROUND(COUNT(*) FILTER (WHERE embedding IS NOT NULL) * 100.0 / NULLIF(COUNT(*), 0), 2) as coverage_percent
FROM clean_concepts;

-- ========================================
-- FUNCTION: Trigger for embedding invalidation
-- ========================================

-- Function: Update trigger for embedding invalidation
CREATE OR REPLACE FUNCTION invalidate_embedding_on_content_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- If front or back content changed, invalidate the embedding
    IF (TG_OP = 'UPDATE') AND
       (OLD.front IS DISTINCT FROM NEW.front OR OLD.back IS DISTINCT FROM NEW.back) THEN
        NEW.embedding := NULL;
        NEW.embedding_generated_at := NULL;
    END IF;
    RETURN NEW;
END;
$$;

-- Trigger: Auto-invalidate embedding when content changes
DROP TRIGGER IF EXISTS trg_invalidate_atom_embedding ON clean_atoms;
CREATE TRIGGER trg_invalidate_atom_embedding
    BEFORE UPDATE ON clean_atoms
    FOR EACH ROW
    EXECUTE FUNCTION invalidate_embedding_on_content_change();

-- ========================================
-- COMMENTS
-- ========================================

COMMENT ON TABLE semantic_duplicates IS 'Stores detected pairs of semantically similar atoms (potential duplicates)';
COMMENT ON COLUMN semantic_duplicates.similarity_score IS 'Cosine similarity score between embeddings (0-1, higher = more similar)';
COMMENT ON COLUMN semantic_duplicates.status IS 'Review status: pending (needs review), merged (combined into one), dismissed (not duplicates)';

COMMENT ON TABLE inferred_prerequisites IS 'AI-suggested prerequisite relationships based on embedding similarity';
COMMENT ON COLUMN inferred_prerequisites.similarity_score IS 'Cosine similarity between atom and concept embeddings';
COMMENT ON COLUMN inferred_prerequisites.confidence IS 'Confidence level: high (>0.85), medium (0.75-0.85), low (0.7-0.75)';

COMMENT ON TABLE knowledge_clusters IS 'Groups of semantically related learning atoms for knowledge state analysis';
COMMENT ON COLUMN knowledge_clusters.centroid IS '384-dim vector representing cluster center (serialized as BYTEA)';
COMMENT ON COLUMN knowledge_clusters.silhouette_score IS 'Cluster quality metric: -1 (bad) to 1 (good)';

COMMENT ON TABLE knowledge_cluster_members IS 'Junction table linking atoms to their knowledge clusters';
COMMENT ON COLUMN knowledge_cluster_members.distance_to_centroid IS 'Cosine distance from atom to cluster centroid';
COMMENT ON COLUMN knowledge_cluster_members.is_exemplar IS 'True if this atom best represents the cluster';

COMMENT ON COLUMN clean_atoms.embedding IS '384-dim semantic embedding from sentence-transformers (serialized as BYTEA)';
COMMENT ON COLUMN clean_atoms.embedding_model IS 'Model used to generate embedding (for reproducibility)';

-- Note: Similarity search functions (find_similar_atoms, find_semantic_duplicate_pairs)
-- are implemented in Python since pgvector is not available.
-- See: src/semantic/similarity_service.py
