"""
Configuration settings for notion-learning-sync service.

Uses Pydantic Settings for environment variable management with .env file support.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ========================================
    # Database
    # ========================================
    database_url: str = Field(
        default="postgresql://postgres:learning123@localhost:5432/notion_learning_sync",
        description="PostgreSQL connection string",
    )

    # ========================================
    # Notion API
    # ========================================
    notion_api_key: str = Field(
        default="",
        description="Notion integration API key",
    )
    notion_version: str = Field(
        default="2022-06-28",  # Update to "2025-09-03" when using latest features
        description="Notion API version",
    )

    # ─── Core Databases (Cortex 2.0 Schema) ─────────────────────────────────────
    # Primary: All-Atom Master Database
    flashcards_db_id: str | None = Field(
        default=None,
        description="Notion Flashcards (All-Atom Master) database ID",
    )
    # Knowledge Hierarchy
    superconcepts_db_id: str | None = Field(
        default=None,
        description="Notion Superconcepts (L0 Areas + L1 Clusters) database ID",
    )
    subconcepts_db_id: str | None = Field(
        default=None,
        description="Notion Subconcepts (being merged into Flashcards) database ID",
    )
    # Legacy (for backwards compatibility)
    concepts_db_id: str | None = Field(
        default=None,
        description="Notion Concepts (L2) database ID - legacy",
    )
    concept_areas_db_id: str | None = Field(
        default=None,
        description="Notion Concept Areas (L0) database ID - legacy",
    )
    concept_clusters_db_id: str | None = Field(
        default=None,
        description="Notion Concept Clusters (L1) database ID - legacy",
    )
    # Projects (for Z-Score project relevance signal)
    projects_db_id: str | None = Field(
        default=None,
        description="Notion Projects (learning focus/goals) database ID",
    )

    # ─── Curriculum Structure Databases (3) ─────────────────────────────────────
    modules_db_id: str | None = Field(
        default=None,
        description="Notion Modules (week/chapter units) database ID",
    )
    tracks_db_id: str | None = Field(
        default=None,
        description="Notion Tracks (course sequences) database ID",
    )
    programs_db_id: str | None = Field(
        default=None,
        description="Notion Programs (degree/cert paths) database ID",
    )

    # ─── Activity & Session Databases (2) ───────────────────────────────────────
    activities_db_id: str | None = Field(
        default=None,
        description="Notion Activities (assignments/exercises) database ID",
    )
    sessions_db_id: str | None = Field(
        default=None,
        description="Notion Sessions (study session logs) database ID",
    )

    # ─── Assessment & Practice Databases (2) ────────────────────────────────────
    quizzes_db_id: str | None = Field(
        default=None,
        description="Notion Quizzes (mastery assessments) database ID",
    )
    critical_skills_db_id: str | None = Field(
        default=None,
        description="Notion Critical Skills (procedural tracking) database ID",
    )

    # ─── Knowledge Support Databases (3) ────────────────────────────────────────
    resources_db_id: str | None = Field(
        default=None,
        description="Notion Resources (articles, videos, papers) database ID",
    )
    mental_models_db_id: str | None = Field(
        default=None,
        description="Notion Mental Models (meta-learning patterns) database ID",
    )
    evidence_db_id: str | None = Field(
        default=None,
        description="Notion Evidence (research citations) database ID",
    )

    # ─── Neuroplasticity Databases (4) ──────────────────────────────────────────
    brain_regions_db_id: str | None = Field(
        default=None,
        description="Notion Brain Regions (neurosystem tracking) database ID",
    )
    training_protocols_db_id: str | None = Field(
        default=None,
        description="Notion Training Protocols (intervention protocols) database ID",
    )
    practice_logs_db_id: str | None = Field(
        default=None,
        description="Notion Practice Logs (adherence tracking) database ID",
    )
    assessments_db_id: str | None = Field(
        default=None,
        description="Notion Assessments (cognitive tests) database ID",
    )

    # ========================================
    # Anki Integration
    # ========================================
    anki_connect_url: str = Field(
        default="http://127.0.0.1:8765",
        description="AnkiConnect plugin URL",
    )
    anki_deck_name: str = Field(
        default="LearningOS::Synced",
        description="Target Anki deck for synced cards",
    )
    anki_note_type: str = Field(
        default="Basic",
        description="Anki note type for new cards",
    )

    # ========================================
    # AI Integration (for cleaning/rewriting)
    # ========================================
    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key for Claude models",
    )
    gemini_api_key: str | None = Field(
        default=None,
        description="Google Generative AI (Gemini) API key",
    )
    vertex_project: str | None = Field(
        default=None,
        description="Google Cloud project ID for Vertex AI",
    )
    vertex_location: str = Field(
        default="us-central1",
        description="Google Cloud region for Vertex AI",
    )
    ai_model: str = Field(
        default="gemini-2.0-flash",
        description="AI model for content rewriting",
    )

    # ========================================
    # Atomicity Thresholds (Evidence-Based)
    # ========================================
    atomicity_front_max_words: int = Field(
        default=25,
        description="Maximum words for question (Wozniak/Gwern research)",
    )
    atomicity_back_optimal_words: int = Field(
        default=5,
        description="Optimal words for answer",
    )
    atomicity_back_warning_words: int = Field(
        default=15,
        description="Warning threshold for answer length",
    )
    atomicity_back_max_chars: int = Field(
        default=120,
        description="Maximum characters for answer (CLT)",
    )
    atomicity_mode: Literal["relaxed", "strict"] = Field(
        default="relaxed",
        description="Atomicity enforcement mode",
    )

    # ========================================
    # Sync Behavior
    # ========================================
    sync_interval_minutes: int = Field(
        default=120,
        description="Auto-sync interval (0 to disable)",
    )
    protect_notion: bool = Field(
        default=True,
        description="Prevent writes to Notion (safety flag)",
    )
    dry_run: bool = Field(
        default=False,
        description="Log actions without making changes",
    )

    # ========================================
    # Logging
    # ========================================
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging verbosity level",
    )
    log_file: str | None = Field(
        default="logs/notion_learning_sync.log",
        description="Log file path (None for stdout only)",
    )

    # ========================================
    # API Server
    # ========================================
    api_host: str = Field(
        default="127.0.0.1",
        description="API server host",
    )
    api_port: int = Field(
        default=8100,
        description="API server port",
    )

    # ========================================
    # FSRS Settings (for spaced repetition)
    # ========================================
    fsrs_default_stability: float = Field(
        default=1.0,
        description="Initial stability for new cards (days)",
    )
    fsrs_default_difficulty: float = Field(
        default=0.3,
        description="Initial difficulty for new cards (0-1)",
    )
    fsrs_desired_retention: float = Field(
        default=0.9,
        description="Target retention rate for scheduling",
    )

    # ========================================
    # Semantic Embeddings (Phase 2.5)
    # ========================================
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Sentence transformer model for embeddings (384-dim)",
    )
    embedding_dimension: int = Field(
        default=384,
        description="Embedding vector dimension (must match model)",
    )
    semantic_duplicate_threshold: float = Field(
        default=0.85,
        description="Cosine similarity threshold for duplicate detection",
    )
    prerequisite_similarity_threshold: float = Field(
        default=0.7,
        description="Similarity threshold for prerequisite inference",
    )
    prerequisite_high_confidence: float = Field(
        default=0.85,
        description="Similarity threshold for high-confidence prerequisites",
    )
    prerequisite_medium_confidence: float = Field(
        default=0.75,
        description="Similarity threshold for medium-confidence prerequisites",
    )
    embedding_batch_size: int = Field(
        default=32,
        description="Batch size for embedding generation",
    )
    embedding_show_progress: bool = Field(
        default=True,
        description="Show progress bar during embedding generation",
    )

    # ========================================
    # Helper Methods
    # ========================================
    def get_all_database_ids(self) -> dict[str, str | None]:
        """Return a dictionary of all Notion database IDs (including None)."""
        return {
            # Cortex 2.0 Core Databases
            "flashcards": self.flashcards_db_id,      # All-Atom Master
            "superconcepts": self.superconcepts_db_id,  # Knowledge Areas (L0/L1)
            "subconcepts": self.subconcepts_db_id,    # Being merged
            "projects": self.projects_db_id,          # Learning focus
            # Legacy concept databases (backwards compatibility)
            "concepts": self.concepts_db_id,
            "concept_areas": self.concept_areas_db_id,
            "concept_clusters": self.concept_clusters_db_id,
            # Curriculum (3)
            "modules": self.modules_db_id,
            "tracks": self.tracks_db_id,
            "programs": self.programs_db_id,
            # Activity & sessions (2)
            "activities": self.activities_db_id,
            "sessions": self.sessions_db_id,
            # Assessment (2)
            "quizzes": self.quizzes_db_id,
            "critical_skills": self.critical_skills_db_id,
            # Knowledge support (3)
            "resources": self.resources_db_id,
            "mental_models": self.mental_models_db_id,
            "evidence": self.evidence_db_id,
            # Neuroplasticity (4)
            "brain_regions": self.brain_regions_db_id,
            "training_protocols": self.training_protocols_db_id,
            "practice_logs": self.practice_logs_db_id,
            "assessments": self.assessments_db_id,
        }

    def get_cortex_database_ids(self) -> dict[str, str | None]:
        """Return only the core Cortex 2.0 database IDs."""
        return {
            "flashcards": self.flashcards_db_id,
            "superconcepts": self.superconcepts_db_id,
            "projects": self.projects_db_id,
            "modules": self.modules_db_id,
            "tracks": self.tracks_db_id,
            "sessions": self.sessions_db_id,
        }

    def get_configured_notion_databases(self) -> dict[str, str]:
        """Return only the Notion database IDs that are configured (non-None)."""
        return {k: v for k, v in self.get_all_database_ids().items() if v is not None}

    def has_ai_configured(self) -> bool:
        """Check if any AI provider is configured."""
        return bool(self.gemini_api_key or self.vertex_project)

    def has_anki_configured(self) -> bool:
        """Check if Anki integration is available."""
        return bool(self.anki_connect_url)

    def get_semantic_config(self) -> dict[str, any]:
        """Get semantic embedding configuration as a dictionary."""
        return {
            "model": self.embedding_model,
            "dimension": self.embedding_dimension,
            "duplicate_threshold": self.semantic_duplicate_threshold,
            "prerequisite_threshold": self.prerequisite_similarity_threshold,
            "high_confidence": self.prerequisite_high_confidence,
            "medium_confidence": self.prerequisite_medium_confidence,
            "batch_size": self.embedding_batch_size,
            "show_progress": self.embedding_show_progress,
        }

    # ========================================
    # Prerequisites (Phase 3 - Soft/Hard Gating)
    # ========================================
    prerequisite_foundation_threshold: float = Field(
        default=0.40,
        description="Mastery threshold for foundation prerequisites (basic exposure)",
    )
    prerequisite_integration_threshold: float = Field(
        default=0.65,
        description="Mastery threshold for integration prerequisites (solid understanding)",
    )
    prerequisite_mastery_threshold: float = Field(
        default=0.85,
        description="Mastery threshold for mastery prerequisites (expert level)",
    )
    prerequisite_anki_tag_prefix: str = Field(
        default="tag:prereq:",
        description="Anki tag prefix for prerequisite relationships",
    )
    prerequisite_circular_max_depth: int = Field(
        default=10,
        description="Maximum depth for circular dependency detection",
    )
    prerequisite_default_gating: Literal["soft", "hard"] = Field(
        default="soft",
        description="Default gating type for new prerequisites",
    )

    # ========================================
    # Quiz Quality Assurance (Phase 3)
    # ========================================
    quiz_mcq_min_options: int = Field(
        default=3,
        description="Minimum options for MCQ questions",
    )
    quiz_mcq_max_options: int = Field(
        default=6,
        description="Maximum options for MCQ questions",
    )
    quiz_mcq_optimal_options: int = Field(
        default=4,
        description="Optimal number of MCQ options (evidence-based)",
    )
    quiz_matching_max_pairs: int = Field(
        default=6,
        description="Maximum pairs for matching questions (cognitive load)",
    )
    quiz_ranking_max_items: int = Field(
        default=7,
        description="Maximum items for ranking questions",
    )
    quiz_parsons_max_blocks: int = Field(
        default=12,
        description="Maximum code blocks for Parsons problems",
    )
    quiz_default_passing_threshold: float = Field(
        default=0.70,
        description="Default passing score threshold for quizzes",
    )
    quiz_mastery_weight: float = Field(
        default=0.375,
        description="Weight of quiz scores in mastery calculation (37.5%)",
    )
    quiz_review_weight: float = Field(
        default=0.625,
        description="Weight of review scores in mastery calculation (62.5%)",
    )
    quiz_distractor_quality_threshold: float = Field(
        default=0.60,
        description="Minimum distractor quality score for MCQ",
    )
    quiz_question_optimal_length_min: int = Field(
        default=8,
        description="Minimum optimal words for question stem",
    )
    quiz_question_optimal_length_max: int = Field(
        default=15,
        description="Maximum optimal words for question stem",
    )
    quiz_answer_optimal_length_max: int = Field(
        default=5,
        description="Maximum optimal words for answer",
    )

    # ========================================
    # Knowledge Type Passing Thresholds
    # ========================================
    knowledge_factual_passing: float = Field(
        default=0.70,
        description="Passing threshold for factual knowledge (recall)",
    )
    knowledge_conceptual_passing: float = Field(
        default=0.80,
        description="Passing threshold for conceptual knowledge (understanding)",
    )
    knowledge_procedural_passing: float = Field(
        default=0.85,
        description="Passing threshold for procedural knowledge (execution)",
    )
    knowledge_metacognitive_passing: float = Field(
        default=0.75,
        description="Passing threshold for metacognitive knowledge (self-regulation)",
    )

    def get_prerequisite_config(self) -> dict[str, any]:
        """Get prerequisite configuration as a dictionary."""
        return {
            "thresholds": {
                "foundation": self.prerequisite_foundation_threshold,
                "integration": self.prerequisite_integration_threshold,
                "mastery": self.prerequisite_mastery_threshold,
            },
            "anki_tag_prefix": self.prerequisite_anki_tag_prefix,
            "circular_max_depth": self.prerequisite_circular_max_depth,
            "default_gating": self.prerequisite_default_gating,
        }

    def get_quiz_config(self) -> dict[str, any]:
        """Get quiz quality configuration as a dictionary."""
        return {
            "mcq": {
                "min_options": self.quiz_mcq_min_options,
                "max_options": self.quiz_mcq_max_options,
                "optimal_options": self.quiz_mcq_optimal_options,
            },
            "matching_max_pairs": self.quiz_matching_max_pairs,
            "ranking_max_items": self.quiz_ranking_max_items,
            "parsons_max_blocks": self.quiz_parsons_max_blocks,
            "passing_threshold": self.quiz_default_passing_threshold,
            "mastery_weights": {
                "quiz": self.quiz_mastery_weight,
                "review": self.quiz_review_weight,
            },
            "quality": {
                "distractor_threshold": self.quiz_distractor_quality_threshold,
                "question_length": {
                    "min": self.quiz_question_optimal_length_min,
                    "max": self.quiz_question_optimal_length_max,
                },
                "answer_length_max": self.quiz_answer_optimal_length_max,
            },
        }

    def get_knowledge_thresholds(self) -> dict[str, float]:
        """Get knowledge type passing thresholds."""
        return {
            "factual": self.knowledge_factual_passing,
            "conceptual": self.knowledge_conceptual_passing,
            "procedural": self.knowledge_procedural_passing,
            "metacognitive": self.knowledge_metacognitive_passing,
        }

    # ========================================
    # Cortex 2.0: Notion-Centric Architecture
    # ========================================
    # Neo4j Shadow Graph (graph algorithm cache)
    neo4j_uri: str = Field(
        default="bolt://localhost:7687",
        description="Neo4j connection URI for Shadow Graph",
    )
    neo4j_user: str = Field(
        default="neo4j",
        description="Neo4j username",
    )
    neo4j_password: str = Field(
        default="cortex2025",
        description="Neo4j password",
    )
    neo4j_database: str = Field(
        default="cortex",
        description="Neo4j database name",
    )

    # Z-Score Algorithm Weights
    zscore_weight_decay: float = Field(
        default=0.30,
        description="Weight for time-decay signal D(t) in Z-Score",
    )
    zscore_weight_centrality: float = Field(
        default=0.25,
        description="Weight for graph centrality signal C(a) in Z-Score",
    )
    zscore_weight_project: float = Field(
        default=0.25,
        description="Weight for project relevance signal P(a) in Z-Score",
    )
    zscore_weight_novelty: float = Field(
        default=0.20,
        description="Weight for novelty signal N(a) in Z-Score",
    )
    zscore_activation_threshold: float = Field(
        default=0.5,
        description="Z-Score threshold for Focus Stream activation",
    )
    zscore_decay_halflife_days: int = Field(
        default=7,
        description="Half-life for time-decay function (days since last touch)",
    )

    # Force Z Algorithm
    force_z_mastery_threshold: float = Field(
        default=0.65,
        description="Prerequisite mastery threshold for Force Z backtracking",
    )
    force_z_max_depth: int = Field(
        default=5,
        description="Maximum backtracking depth in prerequisite graph",
    )

    # PLM Sidecar Settings
    plm_protocol: str = Field(
        default="cortex://",
        description="Protocol for PLM sidecar deep linking",
    )
    plm_target_response_ms: int = Field(
        default=800,
        description="Target response time for PLM fluency (ms)",
    )
    plm_accuracy_threshold: float = Field(
        default=0.90,
        description="Accuracy threshold for PLM fluency achieved",
    )

    # Sync Strategy Settings
    sync_reflex_enabled: bool = Field(
        default=True,
        description="Enable webhook-based immediate sync (Reflex Loop)",
    )
    sync_pulse_interval_minutes: int = Field(
        default=5,
        description="Interval for Pulse Loop polling sync (minutes)",
    )
    sync_audit_hour: int = Field(
        default=2,
        description="Hour for nightly Deep Audit sync (0-23)",
    )

    # ─── Notion Property Names (Cortex 2.0 Schema) ─────────────────────────────
    # Core Atom Properties
    notion_prop_question: str = Field(
        default="Question",
        description="Notion property name for question/front",
    )
    notion_prop_answer: str = Field(
        default="Answer",
        description="Notion property name for answer/back",
    )
    notion_prop_atom_type: str = Field(
        default="Atom_Type",
        description="Notion property name for atom type (Flashcard, Definition, etc.)",
    )
    notion_prop_hierarchy_level: str = Field(
        default="Hierarchy_Level",
        description="Notion property name for hierarchy level (Atom, Concept, Skill)",
    )

    # Z-Score System Properties
    notion_prop_z_score: str = Field(
        default="Z_Score",
        description="Notion property name for computed Z-Score",
    )
    notion_prop_z_activation: str = Field(
        default="Z_Activation",
        description="Notion property name for Focus Stream activation",
    )

    # Memory & Learning Properties
    notion_prop_memory_state: str = Field(
        default="Memory_State",
        description="Notion property name for memory state (NEW|LEARNING|REVIEW|MASTERED)",
    )
    notion_prop_stability: str = Field(
        default="Stability",
        description="Notion property name for FSRS stability (days)",
    )
    notion_prop_difficulty: str = Field(
        default="Difficulty",
        description="Notion property name for FSRS difficulty",
    )
    notion_prop_last_review: str = Field(
        default="Last_Review",
        description="Notion property name for last review date",
    )
    notion_prop_next_review: str = Field(
        default="Next_Review",
        description="Notion property name for next review date",
    )
    notion_prop_review_count: str = Field(
        default="Review_Count",
        description="Notion property name for review count",
    )
    notion_prop_lapses: str = Field(
        default="Lapses",
        description="Notion property name for lapse count",
    )

    # Cognitive Index Properties
    notion_prop_psi: str = Field(
        default="PSI",
        description="Notion property name for Pattern Separation Index",
    )
    notion_prop_pfit: str = Field(
        default="PFIT",
        description="Notion property name for P-FIT Integration Index",
    )

    # Quality & Validation Properties
    notion_prop_quality_grade: str = Field(
        default="Quality_Grade",
        description="Notion property name for atomicity quality grade (A-F)",
    )
    notion_prop_validation: str = Field(
        default="Validation_Status",
        description="Notion property name for validation status",
    )

    # Relation Properties
    notion_prop_prerequisites: str = Field(
        default="Prerequisites",
        description="Notion property name for prerequisite relations",
    )
    notion_prop_confusables: str = Field(
        default="Confusables",
        description="Notion property name for confusable atom relations",
    )
    notion_prop_parent_concept: str = Field(
        default="Parent_Concept",
        description="Notion property name for parent concept relation",
    )
    notion_prop_module: str = Field(
        default="Module",
        description="Notion property name for module relation",
    )

    # PLM Integration
    notion_prop_launch_plm: str = Field(
        default="Launch_PLM",
        description="Notion property name for PLM launch formula",
    )

    def get_notion_property_map(self) -> dict[str, str]:
        """Get all Notion property name mappings."""
        return {
            # Core
            "question": self.notion_prop_question,
            "answer": self.notion_prop_answer,
            "atom_type": self.notion_prop_atom_type,
            "hierarchy_level": self.notion_prop_hierarchy_level,
            # Z-Score
            "z_score": self.notion_prop_z_score,
            "z_activation": self.notion_prop_z_activation,
            # Memory
            "memory_state": self.notion_prop_memory_state,
            "stability": self.notion_prop_stability,
            "difficulty": self.notion_prop_difficulty,
            "last_review": self.notion_prop_last_review,
            "next_review": self.notion_prop_next_review,
            "review_count": self.notion_prop_review_count,
            "lapses": self.notion_prop_lapses,
            # Cognitive
            "psi": self.notion_prop_psi,
            "pfit": self.notion_prop_pfit,
            # Quality
            "quality_grade": self.notion_prop_quality_grade,
            "validation": self.notion_prop_validation,
            # Relations
            "prerequisites": self.notion_prop_prerequisites,
            "confusables": self.notion_prop_confusables,
            "parent_concept": self.notion_prop_parent_concept,
            "module": self.notion_prop_module,
            # PLM
            "launch_plm": self.notion_prop_launch_plm,
        }

    def get_zscore_weights(self) -> dict[str, float]:
        """Get Z-Score algorithm weights."""
        return {
            "decay": self.zscore_weight_decay,
            "centrality": self.zscore_weight_centrality,
            "project": self.zscore_weight_project,
            "novelty": self.zscore_weight_novelty,
        }

    def get_cortex_config(self) -> dict[str, any]:
        """Get Cortex 2.0 configuration as a dictionary."""
        return {
            "neo4j": {
                "uri": self.neo4j_uri,
                "user": self.neo4j_user,
                "database": self.neo4j_database,
            },
            "zscore": {
                "weights": self.get_zscore_weights(),
                "activation_threshold": self.zscore_activation_threshold,
                "decay_halflife_days": self.zscore_decay_halflife_days,
            },
            "force_z": {
                "mastery_threshold": self.force_z_mastery_threshold,
                "max_depth": self.force_z_max_depth,
            },
            "plm": {
                "protocol": self.plm_protocol,
                "target_ms": self.plm_target_response_ms,
                "accuracy_threshold": self.plm_accuracy_threshold,
            },
            "sync": {
                "reflex_enabled": self.sync_reflex_enabled,
                "pulse_interval": self.sync_pulse_interval_minutes,
                "audit_hour": self.sync_audit_hour,
            },
        }

    # ========================================
    # CCNA Content Generation (Phase 4)
    # ========================================
    ccna_modules_path: str = Field(
        default="docs/CCNA",
        description="Path to CCNA module TXT files",
    )
    ccna_generation_batch_size: int = Field(
        default=10,
        description="Number of sections to process per batch",
    )
    ccna_min_quality_grade: str = Field(
        default="B",
        description="Minimum grade to accept without flagging (A, B, C, D)",
    )
    ccna_regeneration_attempts: int = Field(
        default=3,
        description="Maximum regeneration attempts for low-quality content",
    )

    # Atom type distribution (target percentages)
    ccna_flashcard_percentage: float = Field(
        default=0.50,
        description="Target percentage of flashcards (50%)",
    )
    ccna_mcq_percentage: float = Field(
        default=0.20,
        description="Target percentage of MCQ questions (20%)",
    )
    ccna_cloze_percentage: float = Field(
        default=0.10,
        description="Target percentage of cloze deletions (10%)",
    )
    ccna_parsons_percentage: float = Field(
        default=0.10,
        description="Target percentage of Parsons problems (10%)",
    )
    ccna_other_percentage: float = Field(
        default=0.10,
        description="Target percentage of other types (10%)",
    )

    # Migration settings
    ccna_migration_similarity_threshold: float = Field(
        default=0.75,
        description="Minimum similarity score for card matching",
    )
    ccna_preserve_grades: str = Field(
        default="A,B",
        description="Comma-separated grades to preserve (e.g., 'A,B')",
    )

    # Generation prompts (evidence-based)
    ccna_question_optimal_min: int = Field(
        default=8,
        description="Minimum optimal words for questions (Wozniak)",
    )
    ccna_question_optimal_max: int = Field(
        default=15,
        description="Maximum optimal words for questions",
    )
    ccna_answer_optimal_factual: int = Field(
        default=15,
        description="Optimal words for factual answers (8-15 with context)",
    )
    ccna_answer_optimal_conceptual: int = Field(
        default=25,
        description="Optimal words for conceptual answers (15-25 with why/how)",
    )

    def get_ccna_config(self) -> dict[str, any]:
        """Get CCNA generation configuration as a dictionary."""
        return {
            "modules_path": self.ccna_modules_path,
            "batch_size": self.ccna_generation_batch_size,
            "min_quality_grade": self.ccna_min_quality_grade,
            "regeneration_attempts": self.ccna_regeneration_attempts,
            "type_distribution": {
                "flashcard": self.ccna_flashcard_percentage,
                "mcq": self.ccna_mcq_percentage,
                "cloze": self.ccna_cloze_percentage,
                "parsons": self.ccna_parsons_percentage,
                "other": self.ccna_other_percentage,
            },
            "migration": {
                "similarity_threshold": self.ccna_migration_similarity_threshold,
                "preserve_grades": [g.strip() for g in self.ccna_preserve_grades.split(",")],
            },
            "quality_thresholds": {
                "question_words": {
                    "min": self.ccna_question_optimal_min,
                    "max": self.ccna_question_optimal_max,
                },
                "answer_words": {
                    "factual": self.ccna_answer_optimal_factual,
                    "conceptual": self.ccna_answer_optimal_conceptual,
                },
            },
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
