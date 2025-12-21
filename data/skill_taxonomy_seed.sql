-- Skill Taxonomy Seed Data
-- Defines initial skill hierarchy for networking, programming, and systems domains
-- Bloom's Taxonomy Levels: remember, understand, apply, analyze, evaluate, create

-- ============================================================
-- Networking Domain Skills (CCNA-focused)
-- ============================================================

-- Remember level (recall facts)
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('NET_OSI_LAYERS', 'OSI Model Layers', 'Recall the 7 layers of the OSI model and their functions', 'networking', 'remember'),
('NET_TCP_UDP', 'TCP vs UDP Protocols', 'Identify differences between TCP and UDP transport protocols', 'networking', 'remember'),
('NET_PORT_NUMBERS', 'Common Port Numbers', 'Recall standard port numbers for common services (HTTP, HTTPS, SSH, etc.)', 'networking', 'remember');

-- Understand level (explain concepts)
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('NET_IP_CLASSES', 'IP Address Classes', 'Explain IP address classes (A, B, C) and their ranges', 'networking', 'understand'),
('NET_SUBNET_CONCEPT', 'Subnetting Concepts', 'Explain the purpose and benefits of subnetting', 'networking', 'understand'),
('NET_ROUTING_CONCEPT', 'Routing Principles', 'Explain how routing tables and routing protocols work', 'networking', 'understand');

-- Apply level (use in practice)
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('NET_IP_ADDRESSING', 'IP Addressing and Subnetting', 'Calculate network addresses, broadcast addresses, and VLSM', 'networking', 'apply'),
('NET_VLAN_CONFIG', 'VLAN Configuration', 'Configure VLANs on switches and implement trunk ports', 'networking', 'apply'),
('NET_ACL_CONFIG', 'Access Control Lists', 'Create and apply ACLs for traffic filtering', 'networking', 'apply');

-- Analyze level (troubleshoot and diagnose)
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('NET_TROUBLESHOOT_CONNECTIVITY', 'Network Connectivity Troubleshooting', 'Diagnose and resolve network connectivity issues using ping, traceroute, etc.', 'networking', 'analyze'),
('NET_PACKET_ANALYSIS', 'Packet Analysis', 'Analyze packet captures to identify network problems', 'networking', 'analyze'),
('NET_ROUTING_TROUBLESHOOT', 'Routing Troubleshooting', 'Diagnose routing table issues and path selection problems', 'networking', 'analyze');

-- Evaluate level (assess and optimize)
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('NET_SECURITY_ASSESSMENT', 'Network Security Assessment', 'Evaluate network security posture and identify vulnerabilities', 'networking', 'evaluate'),
('NET_PERFORMANCE_OPTIMIZATION', 'Network Performance Optimization', 'Assess network performance bottlenecks and propose solutions', 'networking', 'evaluate');

-- Create level (design networks)
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('NET_NETWORK_DESIGN', 'Network Architecture Design', 'Design scalable and secure network architectures', 'networking', 'create'),
('NET_DISASTER_RECOVERY', 'Disaster Recovery Planning', 'Design network redundancy and failover strategies', 'networking', 'create');

-- ============================================================
-- Programming Domain Skills (PROGII-focused)
-- ============================================================

-- Remember level
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('PROG_SYNTAX_BASICS', 'Language Syntax Basics', 'Recall basic syntax for variables, loops, and conditionals', 'programming', 'remember'),
('PROG_DATA_STRUCTURES', 'Data Structure Types', 'Identify different data structures (arrays, lists, stacks, queues)', 'programming', 'remember');

-- Understand level
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('PROG_OOP_CONCEPTS', 'Object-Oriented Programming', 'Explain OOP principles (encapsulation, inheritance, polymorphism)', 'programming', 'understand'),
('PROG_ALGORITHM_COMPLEXITY', 'Algorithm Complexity', 'Explain time and space complexity (Big O notation)', 'programming', 'understand');

-- Apply level
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('PROG_IMPLEMENT_ALGORITHMS', 'Algorithm Implementation', 'Implement common algorithms (sorting, searching, recursion)', 'programming', 'apply'),
('PROG_USE_APIS', 'API Integration', 'Integrate and use third-party APIs in applications', 'programming', 'apply'),
('PROG_ERROR_HANDLING', 'Error Handling and Exceptions', 'Implement proper error handling and exception management', 'programming', 'apply');

-- Analyze level
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('PROG_DEBUGGING', 'Debugging and Error Tracing', 'Diagnose and fix bugs using debuggers and logging', 'programming', 'analyze'),
('PROG_CODE_REVIEW', 'Code Review and Analysis', 'Analyze code for bugs, inefficiencies, and style violations', 'programming', 'analyze');

-- Evaluate level
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('PROG_PERFORMANCE_PROFILING', 'Performance Profiling', 'Evaluate code performance and identify optimization opportunities', 'programming', 'evaluate'),
('PROG_ARCHITECTURE_EVALUATION', 'Software Architecture Evaluation', 'Assess software design patterns and architectural decisions', 'programming', 'evaluate');

-- Create level
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('PROG_SYSTEM_DESIGN', 'System Design', 'Design scalable software systems and architectures', 'programming', 'create'),
('PROG_FRAMEWORK_DESIGN', 'Framework and Library Design', 'Create reusable frameworks and libraries', 'programming', 'create');

-- ============================================================
-- Systems Domain Skills (SDE2-focused)
-- ============================================================

-- Remember level
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('SYS_LINUX_COMMANDS', 'Linux Command Basics', 'Recall common Linux/Unix commands and their options', 'systems', 'remember'),
('SYS_PROCESS_MANAGEMENT', 'Process Management Concepts', 'Identify process states and lifecycle in operating systems', 'systems', 'remember');

-- Understand level
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('SYS_MEMORY_MANAGEMENT', 'Memory Management Principles', 'Explain virtual memory, paging, and memory allocation', 'systems', 'understand'),
('SYS_FILE_SYSTEMS', 'File System Architecture', 'Explain file system structures and journaling', 'systems', 'understand');

-- Apply level
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('SYS_SHELL_SCRIPTING', 'Shell Scripting', 'Write shell scripts for automation and system administration', 'systems', 'apply'),
('SYS_CONTAINERIZATION', 'Containerization (Docker)', 'Create and manage containers using Docker and orchestration tools', 'systems', 'apply');

-- Analyze level
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('SYS_PERFORMANCE_ANALYSIS', 'System Performance Analysis', 'Diagnose system performance bottlenecks using profiling tools', 'systems', 'analyze'),
('SYS_LOG_ANALYSIS', 'Log Analysis and Troubleshooting', 'Analyze system logs to diagnose issues and security events', 'systems', 'analyze');

-- Evaluate level
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('SYS_CAPACITY_PLANNING', 'Capacity Planning', 'Evaluate system resource needs and plan for scaling', 'systems', 'evaluate');

-- Create level
INSERT INTO skills (skill_code, name, description, domain, cognitive_level) VALUES
('SYS_TESTING_STRATEGY', 'Test Strategy Design', 'Design comprehensive testing strategies (unit, integration, E2E)', 'systems', 'create'),
('SYS_CI_CD_PIPELINE', 'CI/CD Pipeline Design', 'Design and implement continuous integration and deployment pipelines', 'systems', 'create');

-- ============================================================
-- Summary
-- ============================================================
-- Total skills created: 35
-- - Networking: 16 skills
-- - Programming: 13 skills
-- - Systems: 6 skills
-- Cognitive levels coverage: All 6 Bloom's levels represented
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