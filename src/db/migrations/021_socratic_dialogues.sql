-- Migration: 021_socratic_dialogues
-- Purpose: Schema for recording Socratic tutoring dialogues and analytics

-- Table: socratic_dialogues
-- Records each Socratic tutoring session when learner says "don't know"
CREATE TABLE IF NOT EXISTS socratic_dialogues (
    id SERIAL PRIMARY KEY,
    atom_id VARCHAR(64) NOT NULL,
    learner_id VARCHAR(64) DEFAULT 'default',
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMP,
    resolution VARCHAR(32),  -- self_solved, guided_solved, gave_up, revealed
    scaffold_level_reached INT DEFAULT 0,
    turns_count INT DEFAULT 0,
    total_duration_ms INT,
    detected_gaps TEXT,  -- JSON array of prerequisite topic IDs
    created_at TIMESTAMP DEFAULT NOW()
);

-- Table: dialogue_turns
-- Records individual turns in a Socratic dialogue
CREATE TABLE IF NOT EXISTS dialogue_turns (
    id SERIAL PRIMARY KEY,
    dialogue_id INT REFERENCES socratic_dialogues(id) ON DELETE CASCADE,
    turn_number INT NOT NULL,
    role VARCHAR(16) NOT NULL,  -- tutor, learner
    content TEXT NOT NULL,
    latency_ms INT,
    signal VARCHAR(32),  -- confused, progressing, breakthrough, stuck
    timestamp TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_dialogues_atom ON socratic_dialogues(atom_id);
CREATE INDEX IF NOT EXISTS idx_dialogues_learner ON socratic_dialogues(learner_id);
CREATE INDEX IF NOT EXISTS idx_dialogues_resolution ON socratic_dialogues(resolution);
CREATE INDEX IF NOT EXISTS idx_turns_dialogue ON dialogue_turns(dialogue_id);
