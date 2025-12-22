# Batch 1a: Skill Graph Database Schema

**Branch:** `batch-1a-skill-database`
**Worktree:** `../cortex-batch-1a-skill-database`
**Priority:** CRITICAL (Infrastructure - Blocks all other Batch 1 work)
**Estimated Effort:** 1-2 days
**Status:** Pending

## Objective

Create database schema for skill taxonomy, atom-skill linking, and learner mastery tracking.

## Dependencies

**Required:**
- PostgreSQL database running
- Existing `learning_atoms` table

**Blocks:**
- Batch 1b (needs tables to store mastery)
- Batch 1c (needs tables to query skills)
- All Batch 3 handlers (need skill linking)

## Files to Create

### 1. src/db/migrations/030_skill_graph.sql

```sql
-- Skill taxonomy table
CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_code VARCHAR(50) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    domain VARCHAR(100),              -- networking, programming, systems
    knowledge_dimension VARCHAR(20),  -- factual, conceptual, procedural, metacognitive
    engagement_mode VARCHAR(20),      -- passive, active, constructive, interactive (ICAP)
    element_interactivity_index NUMERIC(3,2), -- 0.0 to 1.0 (CLT)
    parent_skill_id UUID REFERENCES skills(id),  -- Hierarchy support
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Atom-Skill linking (many-to-many)
CREATE TABLE atom_skill_weights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    atom_id UUID REFERENCES learning_atoms(id) ON DELETE CASCADE,
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    weight NUMERIC(3,2) DEFAULT 1.0,  -- How much this atom measures this skill (0-1)
    is_primary BOOLEAN DEFAULT FALSE, -- Primary skill being tested
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(atom_id, skill_id)
);

-- Learner skill mastery state
CREATE TABLE learner_skill_mastery (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    learner_id UUID NOT NULL,
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    mastery_level NUMERIC(5,4) DEFAULT 0.0000,       -- 0.0000 (no mastery) to 1.0000 (full mastery)
    confidence_interval NUMERIC(5,4) DEFAULT 0.5000, -- Uncertainty in estimate
    last_practiced TIMESTAMPTZ,
    practice_count INTEGER DEFAULT 0,
    consecutive_correct INTEGER DEFAULT 0,
    retrievability NUMERIC(5,4) DEFAULT 1.0000,      -- FSRS retrievability for this skill
    difficulty NUMERIC(5,4) DEFAULT 0.3000,          -- FSRS difficulty for this skill
    stability NUMERIC(5,4) DEFAULT 1.0000,           -- FSRS stability (days until 90% recall)
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(learner_id, skill_id)
);

-- Indexes for fast skill-based atom queries
CREATE INDEX idx_atom_skill_primary ON atom_skill_weights(skill_id, is_primary) WHERE is_primary = TRUE;
CREATE INDEX idx_learner_skill_mastery_level ON learner_skill_mastery(learner_id, mastery_level);
CREATE INDEX idx_learner_skill_retrievability ON learner_skill_mastery(learner_id, retrievability);
CREATE INDEX idx_skills_domain ON skills(domain) WHERE is_active = TRUE;
CREATE INDEX idx_skills_knowledge_dimension ON skills(knowledge_dimension) WHERE is_active = TRUE;
CREATE INDEX idx_skills_engagement_mode ON skills(engagement_mode) WHERE is_active = TRUE;

-- Comments for documentation
COMMENT ON TABLE skills IS 'Hierarchical skill taxonomy with ICAP engagement and CLT interactivity';
COMMENT ON TABLE atom_skill_weights IS 'Many-to-many linking between atoms and skills with importance weights';
COMMENT ON TABLE learner_skill_mastery IS 'Per-skill mastery state with FSRS scheduling parameters';
COMMENT ON COLUMN atom_skill_weights.weight IS 'How much this atom measures this skill (0.0 to 1.0)';
COMMENT ON COLUMN learner_skill_mastery.retrievability IS 'FSRS retrievability: probability of recall at current time';
COMMENT ON COLUMN learner_skill_mastery.stability IS 'FSRS stability: days until retrievability drops to 90%';
```

### 2. data/skill_taxonomy_seed.sql

```sql
-- Skill Taxonomy Seed Data
-- 30 skills across 3 domains: Networking, Programming, Systems

-- Domain: Networking (CCNA ITN)
INSERT INTO skills (id, skill_code, name, description, domain, knowledge_dimension, engagement_mode, element_interactivity_index) VALUES
('550e8400-e29b-41d4-a716-446655440001', 'NET_OSI_LAYERS', 'OSI Model Layers', 'Recall and identify the 7 layers of the OSI model', 'networking', 'factual', 'active', 0.1),
('550e8400-e29b-41d4-a716-446655440002', 'NET_IP_ADDRESSING', 'IP Addressing and Subnetting', 'Calculate subnet masks and IP ranges', 'networking', 'procedural', 'constructive', 0.5),
('550e8400-e29b-41d4-a716-446655440003', 'NET_ROUTING_PROTOCOLS', 'Routing Protocol Configuration', 'Configure OSPF, EIGRP, RIP on routers', 'networking', 'procedural', 'constructive', 0.5),
('550e8400-e29b-41d4-a716-446655440004', 'NET_VLAN_DESIGN', 'VLAN Design and Trunking', 'Design VLAN topology and configure trunks', 'networking', 'conceptual', 'constructive', 0.7),
('550e8400-e29b-41d4-a716-446655440005', 'NET_ACL_CONFIG', 'Access Control List Configuration', 'Write ACLs to filter traffic', 'networking', 'procedural', 'constructive', 0.5),
('550e8400-e29b-41d4-a716-446655440006', 'NET_NAT_PAT', 'NAT and PAT Configuration', 'Configure network address translation', 'networking', 'procedural', 'constructive', 0.5),
('550e8400-e29b-41d4-a716-446655440007', 'NET_TROUBLESHOOT', 'Network Troubleshooting', 'Diagnose and fix network connectivity issues', 'networking', 'conceptual', 'constructive', 0.7),
('550e8400-e29b-41d4-a716-446655440008', 'NET_SWITCHING', 'Ethernet Switching', 'Understand MAC learning, flooding, forwarding', 'networking', 'conceptual', 'active', 0.2),
('550e8400-e29b-41d4-a716-446655440009', 'NET_SECURITY_BASICS', 'Network Security Basics', 'Identify security threats and mitigations', 'networking', 'conceptual', 'active', 0.2),
('550e8400-e29b-41d4-a716-446655440010', 'NET_WIRELESS', 'Wireless Networking', 'Configure wireless access points and security', 'networking', 'procedural', 'constructive', 0.5);

-- Domain: Programming (PROGII)
INSERT INTO skills (id, skill_code, name, description, domain, knowledge_dimension, engagement_mode, element_interactivity_index) VALUES
('550e8400-e29b-41d4-a716-446655440011', 'PROG_CONTROL_FLOW', 'Control Flow Understanding', 'Trace if/else, loops, switch statements', 'programming', 'conceptual', 'active', 0.2),
('550e8400-e29b-41d4-a716-446655440012', 'PROG_DEBUGGING', 'Debugging and Error Tracing', 'Identify and fix syntax, logic, runtime errors', 'programming', 'conceptual', 'constructive', 0.7),
('550e8400-e29b-41d4-a716-446655440013', 'PROG_ALGORITHM_COMPLEXITY', 'Algorithm Complexity Analysis', 'Determine Big O notation for algorithms', 'programming', 'metacognitive', 'interactive', 0.8),
('550e8400-e29b-41d4-a716-446655440014', 'PROG_DATA_STRUCTURES', 'Data Structure Selection', 'Choose appropriate data structures for problems', 'programming', 'procedural', 'constructive', 0.5),
('550e8400-e29b-41d4-a716-446655440015', 'PROG_REFACTORING', 'Code Refactoring', 'Improve code quality without changing behavior', 'programming', 'procedural', 'constructive', 0.8),
('550e8400-e29b-41d4-a716-446655440016', 'PROG_OOP', 'Object-Oriented Programming', 'Design classes, inheritance, polymorphism', 'programming', 'procedural', 'constructive', 0.5),
('550e8400-e29b-41d4-a716-446655440017', 'PROG_FUNCTIONAL', 'Functional Programming', 'Use map, filter, reduce, higher-order functions', 'programming', 'procedural', 'constructive', 0.5),
('550e8400-e29b-41d4-a716-446655440018', 'PROG_RECURSION', 'Recursion', 'Write and trace recursive functions', 'programming', 'procedural', 'constructive', 0.5),
('550e8400-e29b-41d4-a716-446655440019', 'PROG_MEMORY_MGMT', 'Memory Management', 'Understand stack, heap, garbage collection', 'programming', 'conceptual', 'active', 0.2),
('550e8400-e29b-41d4-a716-446655440020', 'PROG_TESTING', 'Unit Testing', 'Write unit tests with mocking and assertions', 'programming', 'procedural', 'constructive', 0.5);

-- Domain: Systems (SDE2)
INSERT INTO skills (id, skill_code, name, description, domain, knowledge_dimension, engagement_mode, element_interactivity_index) VALUES
('550e8400-e29b-41d4-a716-446655440021', 'SYS_REQUIREMENTS_ANALYSIS', 'Requirements Analysis', 'Elicit and document system requirements', 'systems', 'conceptual', 'constructive', 0.7),
('550e8400-e29b-41d4-a716-446655440022', 'SYS_TESTING_STRATEGY', 'Test Strategy Design', 'Design test plans and test cases', 'systems', 'procedural', 'constructive', 0.8),
('550e8400-e29b-41d4-a716-446655440023', 'SYS_ARCHITECTURE_PATTERNS', 'Architecture Pattern Application', 'Apply MVC, microservices, event-driven patterns', 'systems', 'procedural', 'constructive', 0.5),
('550e8400-e29b-41d4-a716-446655440024', 'SYS_DATABASE_DESIGN', 'Database Design', 'Normalize schemas, design indexes', 'systems', 'procedural', 'constructive', 0.8),
('550e8400-e29b-41d4-a716-446655440025', 'SYS_API_DESIGN', 'API Design', 'Design RESTful APIs with proper endpoints', 'systems', 'procedural', 'constructive', 0.8),
('550e8400-e29b-41d4-a716-446655440026', 'SYS_CI_CD', 'CI/CD Pipeline', 'Set up continuous integration and deployment', 'systems', 'procedural', 'constructive', 0.5),
('550e8400-e29b-41d4-a716-446655440027', 'SYS_MONITORING', 'System Monitoring', 'Implement logging, metrics, alerting', 'systems', 'procedural', 'constructive', 0.5),
('550e8400-e29b-41d4-a716-446655440028', 'SYS_SCALABILITY', 'Scalability Planning', 'Design for horizontal and vertical scaling', 'systems', 'procedural', 'constructive', 0.8),
('550e8400-e29b-41d4-a716-446655440029', 'SYS_SECURITY', 'System Security', 'Implement authentication, authorization, encryption', 'systems', 'procedural', 'constructive', 0.5),
('550e8400-e29b-41d4-a716-446655440030', 'SYS_DEPLOYMENT', 'Deployment Strategies', 'Blue-green, canary, rolling deployments', 'systems', 'procedural', 'constructive', 0.5);
```

## Checklist

- [ ] Create `src/db/migrations/030_skill_graph.sql`
- [ ] Create `data/skill_taxonomy_seed.sql`
- [ ] Test migration on local database
- [ ] Verify all 3 tables created
- [ ] Verify all 5 indexes created
- [ ] Load seed data (30 skills)
- [ ] Verify foreign key constraints
- [ ] Run sample queries to test indexes

## Testing

### Manual Validation

```bash
# Apply migration
psql -U postgres -d cortex_cli < src/db/migrations/030_skill_graph.sql

# Load seed data
psql -U postgres -d cortex_cli < data/skill_taxonomy_seed.sql

# Verify tables
psql -U postgres -d cortex_cli -c ".t skills atom_skill_weights learner_skill_mastery"

# Verify seed data
psql -U postgres -d cortex_cli -c "SELECT skill_code, name, domain FROM skills LIMIT 10;"

# Test index usage
psql -U postgres -d cortex_cli -c "EXPLAIN SELECT * FROM skills WHERE domain = 'networking';"
```

### BDD Testing Requirements

**See:** [BDD Testing Strategy](../explanation/bdd-testing-strategy.md)

Create integration tests to validate schema correctness:

```python
# tests/integration/test_skill_graph_schema.py

@scenario('features/skill_graph.feature', 'Skill taxonomy is created')
def test_skill_taxonomy_created():
    pass

@given('the database is initialized')
def database_initialized(db_session):
    # Migration already applied
    pass

@when('I query the skills table')
def query_skills(db_session):
    result = db_session.execute("SELECT COUNT(*) FROM skills")
    return result.scalar()

@then('all 3 skill graph tables exist')
def verify_tables_exist(db_session):
    tables = ['skills', 'atom_skill_weights', 'learner_skill_mastery']
    for table in tables:
        result = db_session.execute(f"SELECT to_regclass('{table}')")
        assert result.scalar() is not None

@then('all 5 indexes are created')
def verify_indexes_created(db_session):
    indexes = [
        'idx_atom_skill_primary',
        'idx_learner_skill_mastery_level',
        'idx_learner_skill_retrievability',
        'idx_skills_domain',
        'idx_skills_knowledge_dimension',
        'idx_skills_engagement_mode'
    ]
    for index in indexes:
        result = db_session.execute(f"SELECT to_regclass('{index}')")
        assert result.scalar() is not None
```

### CI Checks

**See:** [CI/CD Pipeline](../explanation/ci-cd-pipeline.md)

This batch must pass:
- Migration validation (`.github/workflows/pr-checks.yml` - migrations job)
- Schema verification (tables and indexes created)
- Integration tests (pytest tests/integration/test_skill_graph_schema.py)

## Commit Strategy

```bash
cd ../cortex-batch-1a-skill-database

git add src/db/migrations/030_skill_graph.sql
git commit -m "feat(batch1a): Add skill graph schema with skills, atom_skill_weights, learner_skill_mastery tables

- Generated with Claude Code

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

git add data/skill_taxonomy_seed.sql
git commit -m "feat(batch1a): Add skill taxonomy seed data (30 skills across networking, programming, systems)

- Generated with Claude Code

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

git push -u origin batch-1a-skill-database
```

## GitHub Issues

```bash
gh issue create  
  --title "[Batch 1a] Skill Graph Database Schema"  
  --body "Create skill taxonomy and atom-skill linking tables...**Files:**.- Migration 030_skill_graph.sql.- Seed data skill_taxonomy_seed.sql..**Tables:** skills, atom_skill_weights, learner_skill_mastery..**Status:** Complete"  
  --label "batch-1a,database,skill-graph,enhancement"  
  --milestone "Phase 1: Foundation"
```

## Success Metrics

- [ ] Migration runs without errors
- [ ] All 3 tables created with correct columns
- [ ] All 5 indexes created
- [ ] 30 skills loaded from seed data
- [ ] Foreign key constraints enforced
- [ ] Query performance acceptable (<10ms for indexed queries)

## Reference

### Strategy Documents
- [BDD Testing Strategy](../explanation/bdd-testing-strategy.md) - Testing approach for cognitive validity
- [CI/CD Pipeline](../explanation/ci-cd-pipeline.md) - Automated quality gates and deployment
- [Atom Type Taxonomy](../explanation/learning-atom-taxonomy.md) - 100+ atom types with ICAP classification
- [Schema Migration Plan](../explanation/schema-migration-plan.md) - Migration to polymorphic JSONB atoms

### Work Orders
- **Master Plan:** `C:.sers.hadow.claude.lans.idy-conjuring-moonbeam.md` lines 223-271
- **Parent Work Order:** `docs/agile/batch-1-skill-graph.md`

---

**Status:** Pending
**AI Coder:** Ready for assignment
## testing and ci

- add or update tests relevant to this batch
- add or update bdd scenarios where applicable
- ensure pr-checks.yml passes before merge




