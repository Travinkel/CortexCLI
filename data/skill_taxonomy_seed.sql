-- Skill Taxonomy Seed Data
-- 30 skills across 3 domains: Networking, Programming, Systems

-- Domain: Networking (CCNA ITN)
INSERT INTO skills (id, skill_code, name, description, domain, cognitive_level) VALUES
('550e8400-e29b-41d4-a716-446655440001', 'NET_OSI_LAYERS', 'OSI Model Layers', 'Recall and identify the 7 layers of the OSI model', 'networking', 'remember'),
('550e8400-e29b-41d4-a716-446655440002', 'NET_IP_ADDRESSING', 'IP Addressing and Subnetting', 'Calculate subnet masks and IP ranges', 'networking', 'apply'),
('550e8400-e29b-41d4-a716-446655440003', 'NET_ROUTING_PROTOCOLS', 'Routing Protocol Configuration', 'Configure OSPF, EIGRP, RIP on routers', 'networking', 'apply'),
('550e8400-e29b-41d4-a716-446655440004', 'NET_VLAN_DESIGN', 'VLAN Design and Trunking', 'Design VLAN topology and configure trunks', 'networking', 'analyze'),
('550e8400-e29b-41d4-a716-446655440005', 'NET_ACL_CONFIG', 'Access Control List Configuration', 'Write ACLs to filter traffic', 'networking', 'apply'),
('550e8400-e29b-41d4-a716-446655440006', 'NET_NAT_PAT', 'NAT and PAT Configuration', 'Configure network address translation', 'networking', 'apply'),
('550e8400-e29b-41d4-a716-446655440007', 'NET_TROUBLESHOOT', 'Network Troubleshooting', 'Diagnose and fix network connectivity issues', 'networking', 'analyze'),
('550e8400-e29b-41d4-a716-446655440008', 'NET_SWITCHING', 'Ethernet Switching', 'Understand MAC learning, flooding, forwarding', 'networking', 'understand'),
('550e8400-e29b-41d4-a716-446655440009', 'NET_SECURITY_BASICS', 'Network Security Basics', 'Identify security threats and mitigations', 'networking', 'understand'),
('550e8400-e29b-41d4-a716-446655440010', 'NET_WIRELESS', 'Wireless Networking', 'Configure wireless access points and security', 'networking', 'apply');

-- Domain: Programming (PROGII)
INSERT INTO skills (id, skill_code, name, description, domain, cognitive_level) VALUES
('550e8400-e29b-41d4-a716-446655440011', 'PROG_CONTROL_FLOW', 'Control Flow Understanding', 'Trace if/else, loops, switch statements', 'programming', 'understand'),
('550e8400-e29b-41d4-a716-446655440012', 'PROG_DEBUGGING', 'Debugging and Error Tracing', 'Identify and fix syntax, logic, runtime errors', 'programming', 'analyze'),
('550e8400-e29b-41d4-a716-446655440013', 'PROG_ALGORITHM_COMPLEXITY', 'Algorithm Complexity Analysis', 'Determine Big O notation for algorithms', 'programming', 'evaluate'),
('550e8400-e29b-41d4-a716-446655440014', 'PROG_DATA_STRUCTURES', 'Data Structure Selection', 'Choose appropriate data structures for problems', 'programming', 'apply'),
('550e8400-e29b-41d4-a716-446655440015', 'PROG_REFACTORING', 'Code Refactoring', 'Improve code quality without changing behavior', 'programming', 'create'),
('550e8400-e29b-41d4-a716-446655440016', 'PROG_OOP', 'Object-Oriented Programming', 'Design classes, inheritance, polymorphism', 'programming', 'apply'),
('550e8400-e29b-41d4-a716-446655440017', 'PROG_FUNCTIONAL', 'Functional Programming', 'Use map, filter, reduce, higher-order functions', 'programming', 'apply'),
('550e8400-e29b-41d4-a716-446655440018', 'PROG_RECURSION', 'Recursion', 'Write and trace recursive functions', 'programming', 'apply'),
('550e8400-e29b-41d4-a716-446655440019', 'PROG_MEMORY_MGMT', 'Memory Management', 'Understand stack, heap, garbage collection', 'programming', 'understand'),
('550e8400-e29b-41d4-a716-446655440020', 'PROG_TESTING', 'Unit Testing', 'Write unit tests with mocking and assertions', 'programming', 'apply');

-- Domain: Systems (SDE2)
INSERT INTO skills (id, skill_code, name, description, domain, cognitive_level) VALUES
('550e8400-e29b-41d4-a716-446655440021', 'SYS_REQUIREMENTS_ANALYSIS', 'Requirements Analysis', 'Elicit and document system requirements', 'systems', 'analyze'),
('550e8400-e29b-41d4-a716-446655440022', 'SYS_TESTING_STRATEGY', 'Test Strategy Design', 'Design test plans and test cases', 'systems', 'create'),
('550e8400-e29b-41d4-a716-446655440023', 'SYS_ARCHITECTURE_PATTERNS', 'Architecture Pattern Application', 'Apply MVC, microservices, event-driven patterns', 'systems', 'apply'),
('550e8400-e29b-41d4-a716-446655440024', 'SYS_DATABASE_DESIGN', 'Database Design', 'Normalize schemas, design indexes', 'systems', 'create'),
('550e8400-e29b-41d4-a716-446655440025', 'SYS_API_DESIGN', 'API Design', 'Design RESTful APIs with proper endpoints', 'systems', 'create'),
('550e8400-e29b-41d4-a716-446655440026', 'SYS_CI_CD', 'CI/CD Pipeline', 'Set up continuous integration and deployment', 'systems', 'apply'),
('550e8400-e29b-41d4-a716-446655440027', 'SYS_MONITORING', 'System Monitoring', 'Implement logging, metrics, alerting', 'systems', 'apply'),
('550e8400-e29b-41d4-a716-446655440028', 'SYS_SCALABILITY', 'Scalability Planning', 'Design for horizontal and vertical scaling', 'systems', 'create'),
('550e8400-e29b-41d4-a716-446655440029', 'SYS_SECURITY', 'System Security', 'Implement authentication, authorization, encryption', 'systems', 'apply'),
('550e8400-e29b-41d4-a716-446655440030', 'SYS_DEPLOYMENT', 'Deployment Strategies', 'Blue-green, canary, rolling deployments', 'systems', 'apply');
