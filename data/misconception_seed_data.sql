-- Misconception Seed Data: 50+ Common Learning Errors
--
-- Organized by domain: networking, programming, systems, security, algorithms
-- Categories: overgeneralization, surface_feature, intuitive_physics, rote_application,
--             feature_confusion, boundary_case, semantic_confusion, procedural_error

-- Clear existing seed data (for re-running)
-- DELETE FROM misconception_library WHERE is_active = TRUE;

-- ========================================
-- NETWORKING MISCONCEPTIONS (15 entries)
-- ========================================

INSERT INTO misconception_library (misconception_code, name, category, domain, prevalence_rate, severity, correct_mental_model, remediation_strategy, example_errors)
VALUES

('NET_COLLISION_DOMAIN_CONFUSION', 'Collision Domain vs Broadcast Domain Confusion', 'feature_confusion', 'networking', 0.65, 'medium',
'A collision domain is where frames can collide (shared medium), separated by switches. A broadcast domain is where broadcasts propagate, separated by routers.',
'Use visual diagrams showing hubs (single collision domain) vs switches (multiple collision domains). Practice identifying domains in mixed topologies.',
ARRAY['Thinking a switch creates one collision domain', 'Believing broadcasts are stopped by switches', 'Confusing VLAN isolation with collision domains']),

('NET_SUBNET_MASK_REVERSED', 'Subnet Mask Binary Reversal', 'procedural_error', 'networking', 0.45, 'high',
'Subnet masks have 1s in the network portion (left) and 0s in the host portion (right). E.g., 255.255.255.0 = 11111111.11111111.11111111.00000000',
'Practice binary conversion drills. Use visual "mask overlays" showing how 1s preserve network bits and 0s allow host variation.',
ARRAY['Writing /24 as 0.0.0.255 instead of 255.255.255.0', 'Inverting wildcard masks with subnet masks', 'Thinking more 0s = more networks']),

('NET_DEFAULT_GATEWAY_ROUTER', 'Default Gateway IS the Router', 'overgeneralization', 'networking', 0.55, 'medium',
'The default gateway is the IP address OF the router interface on the local network, not the router itself. The router has multiple interfaces.',
'Emphasize that routers have multiple IPs (one per interface). Draw topology showing router with eth0 (192.168.1.1) and eth1 (10.0.0.1).',
ARRAY['Saying "the default gateway is 192.168.1.1 router" (it IS the router's IP)', 'Believing routers have one IP address']),

('NET_SWITCH_ROUTES_PACKETS', 'Switches Route Packets', 'semantic_confusion', 'networking', 0.50, 'high',
'Switches forward FRAMES (Layer 2) based on MAC addresses. Routers route PACKETS (Layer 3) based on IP addresses.',
'Create side-by-side comparison: switch (MAC table, frames, same network) vs router (routing table, packets, different networks).',
ARRAY['Saying "switch routes to port 3"', 'Using "route" and "forward" interchangeably at Layer 2']),

('NET_PING_TESTS_BANDWIDTH', 'Ping Tests Bandwidth', 'rote_application', 'networking', 0.40, 'medium',
'Ping tests REACHABILITY and latency (round-trip time), not bandwidth. Use tools like iperf or speed tests for bandwidth.',
'Explain ping sends small ICMP packets. Demonstrate with iperf showing high throughput despite slow ping (distance-based latency).',
ARRAY['Saying "slow ping = slow network"', 'Using only ping to diagnose performance issues']),

('NET_PRIVATE_IPS_NOT_ROUTABLE', 'Private IPs Are Not Routable', 'overgeneralization', 'networking', 0.50, 'medium',
'Private IPs (10.x, 172.16.x, 192.168.x) are not routable ON THE INTERNET, but ARE routable within private networks by internal routers.',
'Clarify distinction: "not routable on public internet" vs "not routable at all". Show NAT converting private → public at edge.',
ARRAY['Thinking private IPs cannot be used with routers', 'Believing Layer 3 switching does not work with private IPs']),

('NET_HUB_INTELLIGENT_FORWARDING', 'Hubs Forward Intelligently', 'overgeneralization', 'networking', 0.35, 'low',
'Hubs are "dumb repeaters" that flood all frames to all ports. Switches learn MAC addresses and forward selectively.',
'Demo with packet sniffer: hub shows all traffic on all ports, switch shows only relevant frames.',
ARRAY['Expecting hubs to reduce collisions', 'Believing hubs have MAC address tables']),

('NET_VLAN_PHYSICAL_SEPARATION', 'VLANs Require Physical Separation', 'intuitive_physics', 'networking', 0.40, 'medium',
'VLANs are LOGICAL segmentation on the SAME physical switch. No separate hardware needed.',
'Show single switch with multiple VLANs configured. Emphasize "virtual" in VLAN = software-defined boundaries.',
ARRAY['Thinking you need multiple switches for VLANs', 'Believing VLAN isolation requires cables']),

('NET_OSPF_BROADCASTS_ROUTES', 'OSPF Broadcasts All Routes', 'overgeneralization', 'networking', 0.45, 'medium',
'OSPF uses MULTICAST (224.0.0.5/6) to send updates, not broadcast (255.255.255.255). Only OSPF-enabled routers listen.',
'Compare RIPv1 (broadcast) vs OSPF (multicast). Explain multicast = targeted group communication.',
ARRAY['Believing OSPF floods broadcasts to all devices', 'Confusing multicast with broadcast']),

('NET_STATIC_BETTER_THAN_DYNAMIC', 'Static Routes Are Always Better', 'overgeneralization', 'networking', 0.30, 'low',
'Static routes are better for SMALL, STABLE networks. Dynamic routing (OSPF, EIGRP) scales better and adapts to failures.',
'Show scenario: 100-router network with topology changes. Calculate manual static route updates vs automatic OSPF convergence.',
ARRAY['Always choosing static routes in scalable networks', 'Believing dynamic routing is "lazy"']),

('NET_SUBNET_ZERO_INVALID', 'Subnet Zero Is Invalid', 'rote_application', 'networking', 0.35, 'low',
'Subnet zero (e.g., 192.168.0.0/24) IS valid in modern networking (post-RFC 1878). Older Cisco devices disabled it by default.',
'Explain historical context: old restriction lifted in 1995. Modern equipment uses "ip subnet-zero" by default.',
ARRAY['Avoiding 192.168.0.0/24 as "reserved"', 'Thinking first subnet must be skipped']),

('NET_MAC_ADDRESS_CHANGES', 'MAC Addresses Change Between Networks', 'procedural_error', 'networking', 0.40, 'high',
'MAC addresses change at EACH ROUTER HOP (L2 rewrite). IP addresses stay the same end-to-end (L3 routing).',
'Trace packet through topology: src MAC changes from A→R1, R1→R2, R2→B, but src IP stays constant.',
ARRAY['Believing MAC addresses are end-to-end identifiers', 'Thinking switches change MAC addresses']),

('NET_TRUNK_CARRIES_ONE_VLAN', 'Trunk Ports Carry One VLAN', 'semantic_confusion', 'networking', 0.50, 'medium',
'Trunk ports carry MULTIPLE VLANs (tagged with 802.1Q). Access ports carry ONE VLAN (untagged).',
'Show trunk config with "switchport mode trunk" allowing VLAN 10, 20, 30 on one cable.',
ARRAY['Configuring trunk for single VLAN', 'Confusing trunk with access ports']),

('NET_DNS_RESOLVES_MAC', 'DNS Resolves MAC Addresses', 'feature_confusion', 'networking', 0.25, 'low',
'DNS resolves hostnames → IP addresses. ARP resolves IP → MAC addresses (Layer 2).',
'Create lookup table: DNS (www.example.com → 93.184.216.34) vs ARP (192.168.1.1 → aa:bb:cc:dd:ee:ff).',
ARRAY['Expecting DNS to return MAC addresses', 'Confusing DNS cache with ARP cache']),

('NET_PACKET_LOSS_ALWAYS_BAD', 'Any Packet Loss Is Catastrophic', 'overgeneralization', 'networking', 0.30, 'low',
'Some packet loss (<1%) is normal. TCP retransmits lost packets. VoIP tolerates ~1% loss. >5% is problematic.',
'Show TCP congestion control: packet loss triggers slowdown, not failure. Demonstrate VoIP quality degradation curve.',
ARRAY['Panicking at 0.1% packet loss', 'Thinking UDP applications fail at first dropped packet']);

-- ========================================
-- PROGRAMMING MISCONCEPTIONS (15 entries)
-- ========================================

INSERT INTO misconception_library (misconception_code, name, category, domain, prevalence_rate, severity, correct_mental_model, remediation_strategy, example_errors)
VALUES

('PROG_LOOP_RUNS_N_PLUS_ONE', 'For Loops Run N+1 Times', 'boundary_case', 'programming', 0.60, 'medium',
'for (int i = 0; i < n; i++) runs EXACTLY n times (i = 0, 1, ..., n-1). Off-by-one errors come from <= or starting at 1.',
'Trace execution by hand for n=3: i=0, i=1, i=2 (stops at i=3). Practice < vs <= distinction.',
ARRAY['Using i <= n instead of i < n', 'Thinking "loop 10 times" means i <= 10']),

('PROG_EQUALS_IS_ASSIGNMENT', '= Is Comparison, == Is Assignment', 'semantic_confusion', 'programming', 0.55, 'critical',
'= is ASSIGNMENT (x = 5 sets x to 5). == is COMPARISON (x == 5 tests if x equals 5).',
'Use "gets" for =, "equals" for ==. Create mnemonic: "one equals is ASSIGN, two equals is TEST".',
ARRAY['Writing if (x = 5) instead of if (x == 5)', 'Setting variables with ==']),

('PROG_RETURN_EXITS_PROGRAM', 'Return Exits the Program', 'overgeneralization', 'programming', 0.45, 'medium',
'return exits the CURRENT FUNCTION, not the entire program. Execution continues in the caller.',
'Trace call stack: main() calls foo(), foo() returns, main() continues. Show debugger stepping through.',
ARRAY['Thinking return stops all execution', 'Not expecting code after function call to run']),

('PROG_ARRAY_SIZE_IS_LENGTH', 'Array Size = Array Length in All Languages', 'overgeneralization', 'programming', 0.40, 'low',
'C/C++: no built-in length, use sizeof(arr)/sizeof(arr[0]). Python/Java/JS: len(arr) or arr.length.',
'Show language-specific examples. Emphasize C arrays are "just pointers" without metadata.',
ARRAY['Using arr.length in C', 'Thinking sizeof(arr) returns element count in C']),

('PROG_PASS_BY_VALUE_COPIES_OBJECT', 'Pass-by-Value Always Copies', 'overgeneralization', 'programming', 0.50, 'high',
'Pass-by-value copies the REFERENCE (pointer), not the object. Mutating the object affects the original.',
'Draw memory diagram: variable holds reference (arrow), copying arrow still points to same object.',
ARRAY['Thinking lists/objects are deep-copied in Java/Python', 'Expecting mutations to not affect original']),

('PROG_RECURSION_IS_LOOP', 'Recursion Is Just a Loop', 'overgeneralization', 'programming', 0.35, 'medium',
'Recursion uses the CALL STACK for state, loops use variables. Recursion can solve problems loops cannot (tree traversal).',
'Show factorial recursively vs iteratively. Explain call stack frames vs loop iterations.',
ARRAY['Thinking all recursion can be trivially converted to loops', 'Not understanding stack overflow']),

('PROG_NULL_EQUALS_ZERO', 'null == 0', 'semantic_confusion', 'programming', 0.45, 'medium',
'null/None/nil represents ABSENCE of value. 0 is a VALUE. In most languages, null != 0.',
'Use analogy: empty box (null) vs box with zero items (0). Different states.',
ARRAY['Initializing pointers to 0 instead of nullptr', 'Thinking null is falsy because 0 is']),

('PROG_FLOAT_EXACT_PRECISION', 'Floats Store Exact Decimals', 'intuitive_physics', 'programming', 0.50, 'high',
'Floats use binary approximation. 0.1 + 0.2 != 0.3 exactly. Use epsilon comparison or Decimal types for precision.',
'Show IEEE 754 representation. Demonstrate: print(0.1 + 0.2) → 0.30000000000000004. Use abs(a - b) < epsilon.',
ARRAY['Comparing floats with ==', 'Expecting 0.1 + 0.2 == 0.3']),

('PROG_SCOPE_IS_GLOBAL', 'All Variables Are Global', 'overgeneralization', 'programming', 0.40, 'medium',
'Variables have SCOPE: local (function), block ({}), global. Inner scopes shadow outer scopes.',
'Trace variable lookups: local → enclosing function → global. Show shadowing example.',
ARRAY['Expecting local variables to be accessible everywhere', 'Not understanding variable shadowing']),

('PROG_COMPILE_EQUALS_RUN', 'Compiling Runs the Program', 'procedural_error', 'programming', 0.30, 'low',
'Compiling translates source → machine code. Running executes machine code. Separate steps.',
'Show: gcc file.c -o program (compile), then ./program (run). Emphasize compile-time vs run-time errors.',
ARRAY['Expecting compilation to execute code', 'Confusing syntax errors with runtime errors']),

('PROG_STRING_MUTATION', 'Strings Are Mutable', 'rote_application', 'programming', 0.45, 'medium',
'In Java/Python/C#, strings are IMMUTABLE. str[0] = "x" creates a NEW string, does not modify the original.',
'Show string pool: "hello" is stored once, all references point to it. Mutation would break this.',
ARRAY['Trying str[0] = "H" in Python', 'Expecting string methods to mutate in-place']),

('PROG_INDEX_STARTS_AT_ONE', 'Array Indexes Start at 1', 'rote_application', 'programming', 0.35, 'medium',
'Most languages use ZERO-BASED indexing: arr[0] is first, arr[n-1] is last. Exceptions: MATLAB, Lua, R.',
'Practice tracing: arr = [10, 20, 30], arr[0] = 10, arr[2] = 30. Mnemonic: "0 is the loneliest number".',
ARRAY['Using arr[1] for first element', 'Off-by-one errors from 1-based thinking']),

('PROG_BREAK_EXITS_FUNCTION', 'break Exits Function', 'semantic_confusion', 'programming', 0.40, 'low',
'break exits the CURRENT LOOP/SWITCH, not the function. Use return to exit function.',
'Show nested loops: break in inner loop only exits inner, outer continues.',
ARRAY['Using break to return from function', 'Expecting break to exit nested structures']),

('PROG_EXCEPTIONS_ARE_ERRORS', 'Exceptions = Errors = Bad Code', 'overgeneralization', 'programming', 0.30, 'low',
'Exceptions handle EXPECTED exceptional cases (file not found, network timeout). Not all exceptions are bugs.',
'Show legitimate uses: try opening file (may not exist), catch FileNotFoundError. Normal control flow.',
ARRAY['Never using exceptions', 'Treating all exceptions as programmer mistakes']),

('PROG_CONCATENATION_IS_ADDITION', '+ Always Means Addition', 'semantic_confusion', 'programming', 0.35, 'medium',
'In dynamic languages, + can mean CONCATENATION (strings) or ADDITION (numbers). "1" + "2" = "12", 1 + 2 = 3.',
'Show type coercion examples: "5" + 3 in JS = "53", in Python = TypeError. Emphasize type matters.',
ARRAY['Expecting "5" + 3 = 8', 'Confusing string and numeric operations']);

-- ========================================
-- SYSTEMS/OS MISCONCEPTIONS (10 entries)
-- ========================================

INSERT INTO misconception_library (misconception_code, name, category, domain, prevalence_rate, severity, correct_mental_model, remediation_strategy, example_errors)
VALUES

('SYS_PROCESS_IS_THREAD', 'Processes and Threads Are the Same', 'feature_confusion', 'systems', 0.50, 'high',
'Processes have SEPARATE memory spaces. Threads SHARE memory within a process. Processes are heavier, threads are lighter.',
'Draw memory diagram: Process A (Thread 1, Thread 2 sharing heap) vs Process B (separate heap).',
ARRAY['Using threads when isolation is needed', 'Expecting thread crash to not affect other threads']),

('SYS_MORE_THREADS_FASTER', 'More Threads = Faster Execution', 'intuitive_physics', 'systems', 0.55, 'medium',
'Beyond CPU core count, more threads = MORE OVERHEAD (context switching). Diminishing returns, then slowdown.',
'Benchmark: 4-core machine with 4 threads vs 100 threads. Show context switch overhead.',
ARRAY['Creating 1000 threads for 4 cores', 'Ignoring thread pool limits']),

('SYS_MALLOC_INITIALIZES_ZERO', 'malloc() Initializes Memory to Zero', 'rote_application', 'systems', 0.40, 'high',
'malloc() allocates UNinitialized memory (garbage values). Use calloc() for zero-initialization.',
'Show: int* p = malloc(sizeof(int)); print(*p) → garbage. Compare to calloc() → 0.',
ARRAY['Reading malloc-ed memory without initialization', 'Expecting consistent initial values']),

('SYS_CACHE_IS_SMALL_RAM', 'Cache Is Just Small RAM', 'overgeneralization', 'systems', 0.35, 'medium',
'Cache is FASTER (nanoseconds) than RAM (100s of ns) due to proximity to CPU. Hierarchy: L1, L2, L3, RAM.',
'Show latency numbers: L1 = 1ns, RAM = 100ns. Explain locality principle for cache hits.',
ARRAY['Thinking cache speed = RAM speed', 'Not understanding cache misses']),

('SYS_FILE_DELETE_IS_IMMEDIATE', 'Deleting a File Erases It Immediately', 'intuitive_physics', 'systems', 0.45, 'medium',
'Deleting removes the DIRECTORY ENTRY, not the data. Data remains until overwritten. Hence "undelete" tools work.',
'Show filesystem internals: inode pointer removed, data blocks marked free but not wiped.',
ARRAY['Believing deleted files are unrecoverable', 'Not understanding secure delete (shred)']),

('SYS_DEADLOCK_IS_CRASH', 'Deadlock = Crash', 'semantic_confusion', 'systems', 0.40, 'low',
'Deadlock is LIVELOCK of waiting resources (program hangs, not crashes). No process can proceed.',
'Dining philosophers demo: all grab left fork, wait for right → stuck forever (no crash).',
ARRAY['Expecting deadlock to throw exceptions', 'Thinking restart fixes deadlock']),

('SYS_VIRTUAL_MEMORY_IS_SWAP', 'Virtual Memory = Swap Space', 'semantic_confusion', 'systems', 0.50, 'medium',
'Virtual memory is ADDRESS SPACE mapping (physical + swap). Swap is DISK SPACE used when RAM is full.',
'Show VM as abstraction layer: process sees continuous address space, OS maps to RAM/swap.',
ARRAY['Thinking VM only activates when RAM full', 'Confusing paging with swapping']),

('SYS_ROOT_CAN_DO_ANYTHING', 'Root User Can Do Anything', 'overgeneralization', 'systems', 0.30, 'low',
'Root bypasses PERMISSION checks, but cannot violate HARDWARE/KERNEL limits (unmount busy FS, kill init).',
'Show: root cannot kill PID 1, cannot eject mounted CD. Explain kernel enforces some rules.',
ARRAY['Expecting rm -rf / to delete running kernel', 'Thinking root has no restrictions']),

('SYS_HARD_LINK_IS_COPY', 'Hard Link = File Copy', 'feature_confusion', 'systems', 0.45, 'medium',
'Hard link is ANOTHER NAME for the same inode (data). Changes to one affect the other. Symlink is a pointer.',
'Show inode diagram: file1 and file2 point to inode 1234 (same data). Delete one, other still works.',
ARRAY['Expecting hard links to create separate copies', 'Confusing hard links with symbolic links']),

('SYS_SCHEDULING_IS_FIFO', 'OS Schedules Processes FIFO', 'rote_application', 'systems', 0.35, 'low',
'Modern OSes use PRIORITY-BASED scheduling (CFS, etc.), not FIFO. Interactive tasks get priority over batch.',
'Show scheduler timeline: high-priority task preempts low-priority even if low started first.',
ARRAY['Expecting processes to run in start order', 'Not understanding priority inversion']);

-- ========================================
-- SECURITY MISCONCEPTIONS (5 entries)
-- ========================================

INSERT INTO misconception_library (misconception_code, name, category, domain, prevalence_rate, severity, correct_mental_model, remediation_strategy, example_errors)
VALUES

('SEC_AUTH_VS_AUTHZ', 'Authentication = Authorization', 'feature_confusion', 'security', 0.60, 'high',
'Authentication = WHO you are (login). Authorization = WHAT you can do (permissions). Separate concerns.',
'Example: You authenticate as "alice" (prove identity), then check if alice is authorized to delete files.',
ARRAY['Conflating login with permissions', 'Expecting authentication to grant access']),

('SEC_ENCRYPTION_IS_HASHING', 'Encryption = Hashing', 'feature_confusion', 'security', 0.50, 'critical',
'Encryption is REVERSIBLE (decrypt with key). Hashing is ONE-WAY (cannot reverse). Use hashing for passwords.',
'Show: encrypt("hello", key) → "Xj2k", decrypt("Xj2k", key) → "hello". hash("hello") → "5d41...", no reverse.',
ARRAY['Storing passwords encrypted instead of hashed', 'Trying to decrypt bcrypt hashes']),

('SEC_HTTPS_ENCRYPTS_URL', 'HTTPS Encrypts the Entire URL', 'overgeneralization', 'security', 0.45, 'medium',
'HTTPS encrypts PATH and QUERY, but NOT the DOMAIN (visible in DNS/SNI). ISP sees you visited "example.com".',
'Show network trace: domain in SNI handshake (plaintext), /private?token=123 encrypted.',
ARRAY['Believing ISPs cannot see visited domains with HTTPS', 'Thinking HTTPS hides all metadata']),

('SEC_LONGER_PASSWORD_UNCRACKABLE', 'Long Passwords Are Uncrackable', 'overgeneralization', 'security', 0.40, 'medium',
'Length helps, but "passwordpasswordpassword" is weak. Need ENTROPY (randomness), not just length.',
'Compare: "Tr0ub4dor&3" (weak, common pattern) vs "correct horse battery staple" (strong, random words).',
ARRAY['Using long but common phrases', 'Thinking length alone guarantees security']),

('SEC_SQL_INJECTION_ONLY_QUERIES', 'SQL Injection Only Affects Queries', 'overgeneralization', 'security', 0.35, 'high',
'SQL injection can lead to DATA EXFILTRATION, DELETION, or even OS COMMAND EXECUTION (xp_cmdshell in MSSQL).',
'Show escalation: " OR 1=1; DROP TABLE users;-- " (deletion) and xp_cmdshell exploitation.',
ARRAY['Only sanitizing SELECT queries', 'Thinking SQLi is limited to data reads']);

-- ========================================
-- ALGORITHMS & DATA STRUCTURES (5 entries)
-- ========================================

INSERT INTO misconception_library (misconception_code, name, category, domain, prevalence_rate, severity, correct_mental_model, remediation_strategy, example_errors)
VALUES

('ALGO_BIG_O_IS_RUNTIME', 'Big-O Is Exact Runtime', 'semantic_confusion', 'algorithms', 0.50, 'medium',
'Big-O describes GROWTH RATE (how time scales with input size), not absolute time. O(n) can be slower than O(n²) for small n.',
'Show: 1000n vs n² for n=10 → 10000 vs 100. Big-O is about LARGE n, not constant factors.',
ARRAY['Expecting O(n) to always beat O(n²)', 'Ignoring constant factors']),

('ALGO_RECURSION_ALWAYS_SLOW', 'Recursion Is Always Slower Than Loops', 'overgeneralization', 'algorithms', 0.40, 'low',
'Tail-call optimized recursion is AS FAST as loops. Some problems (tree traversal) are clearer recursively.',
'Show tail-recursive factorial compiled to same machine code as loop. Explain TCO in functional languages.',
ARRAY['Always converting recursion to loops', 'Avoiding recursion for performance without profiling']),

('ALGO_SORTED_MEANS_UNIQUE', 'Sorted Arrays Have Unique Elements', 'overgeneralization', 'algorithms', 0.30, 'low',
'Sorted means ORDER (ascending/descending), not uniqueness. [1, 2, 2, 3] is sorted.',
'Show sort([3, 1, 2, 2]) → [1, 2, 2, 3]. Unique requires additional step.',
ARRAY['Expecting binary search to fail on duplicates', 'Thinking sort removes duplicates']),

('ALGO_HASH_TABLE_O1_ALWAYS', 'Hash Tables Are Always O(1)', 'overgeneralization', 'algorithms', 0.45, 'medium',
'Hash tables are O(1) AVERAGE case. Worst case (all collisions) is O(n). Good hash functions minimize this.',
'Show pathological case: all keys hash to same bucket → linked list O(n) lookup.',
ARRAY['Expecting constant time in all scenarios', 'Not handling collision resolution']),

('ALGO_GREEDY_ALWAYS_OPTIMAL', 'Greedy Algorithms Always Give Optimal Solutions', 'overgeneralization', 'algorithms', 0.35, 'high',
'Greedy works for SPECIFIC problems (MST, Huffman). Counterexample: coin change with {1, 3, 4} for 6 → greedy gives {4,1,1}, optimal is {3,3}.',
'Show greedy failure on non-canonical coin systems. Emphasize: greedy needs PROOF of optimality.',
ARRAY['Applying greedy to all optimization problems', 'Not recognizing when greedy fails']);

-- Update timestamp for all inserted rows
UPDATE misconception_library SET updated_at = now();
