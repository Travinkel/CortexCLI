-- Greenlight async execution queue
CREATE TABLE greenlight_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    atom_id UUID REFERENCES learning_atoms(id) ON DELETE CASCADE,
    learner_id UUID NOT NULL,
    execution_id VARCHAR(100) UNIQUE,  -- From Greenlight API
    status VARCHAR(20) DEFAULT 'pending',  -- pending, executing, complete, failed
    request_payload JSONB NOT NULL,
    result_payload JSONB,
    queued_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3
);

-- Indexes for fast queries
CREATE INDEX idx_greenlight_queue_status
    ON greenlight_queue(status, queued_at);
CREATE INDEX idx_greenlight_queue_learner
    ON greenlight_queue(learner_id, status);
CREATE INDEX idx_greenlight_queue_execution_id
    ON greenlight_queue(execution_id)
    WHERE execution_id IS NOT NULL;

-- Comments for documentation
COMMENT ON TABLE greenlight_queue IS 'Queue for async Greenlight atom execution with retry logic';
COMMENT ON COLUMN greenlight_queue.status IS 'pending = queued, executing = in progress, complete = finished, failed = error';
COMMENT ON COLUMN greenlight_queue.request_payload IS 'JSON payload sent to Greenlight API';
COMMENT ON COLUMN greenlight_queue.result_payload IS 'JSON response from Greenlight API';
COMMENT ON COLUMN greenlight_queue.execution_id IS 'Greenlight execution ID for polling';
