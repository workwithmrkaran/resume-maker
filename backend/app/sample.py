"""A fictional sample resume, used for template previews and tests."""

from .schema import (
    Contact,
    Education,
    Experience,
    Link,
    Project,
    Publication,
    Resume,
    SkillGroup,
)

SAMPLE_RESUME = Resume(
    contact=Contact(
        full_name="Alex Rivera",
        headline="Backend Engineer — distributed systems & developer tooling",
        email="alex.rivera@example.com",
        phone="+1 (555) 014-2288",
        location="Austin, TX",
        links=[
            Link(label="linkedin.com/in/alexrivera",
                 url="https://linkedin.com/in/alexrivera"),
            Link(label="github.com/alexrivera", url="https://github.com/alexrivera"),
        ],
    ),
    summary=(
        "Backend engineer with six years building high-throughput services. "
        "Comfortable owning a system end to end, from schema design through "
        "on-call. Recent focus on cutting latency and cost in data-heavy "
        "pipelines."
    ),
    experience=[
        Experience(
            title="Senior Software Engineer",
            company="Northwind Data",
            location="Austin, TX",
            start_date="Mar 2022",
            end_date="Present",
            bullets=[
                "Rebuilt the ingestion pipeline around a partitioned queue, "
                "raising sustained throughput from 4k to 26k events/second.",
                "Cut p99 API latency by 63% by replacing per-request joins "
                "with a materialised read model.",
                "Led the migration of 40+ services to structured logging, "
                "reducing mean incident triage time from 22 to 8 minutes.",
                "Mentored three engineers; two were promoted within the year.",
            ],
        ),
        Experience(
            title="Software Engineer",
            company="Cobalt Systems",
            location="Remote",
            start_date="Jul 2019",
            end_date="Feb 2022",
            bullets=[
                "Designed and shipped the public REST API now used by 1,200+ "
                "integration partners.",
                "Introduced contract testing across service boundaries, "
                "eliminating a recurring class of deploy-time regressions.",
                "Reduced cloud spend 18% by right-sizing workloads and "
                "consolidating idle clusters.",
            ],
        ),
    ],
    education=[
        Education(
            degree="B.S. Computer Science",
            institution="University of Texas at Austin",
            location="Austin, TX",
            start_date="2015",
            end_date="2019",
            grade="GPA 3.8/4.0",
            details="Coursework: Distributed Systems, Databases, Compilers.",
        ),
    ],
    skills=[
        SkillGroup(category="Languages",
                   skills=["Python", "Go", "TypeScript", "SQL"]),
        SkillGroup(category="Infrastructure",
                   skills=["PostgreSQL", "Kafka", "Redis", "Kubernetes", "Terraform"]),
        SkillGroup(category="Practices",
                   skills=["Distributed systems design", "Observability",
                           "CI/CD", "Incident response"]),
    ],
    projects=[
        Project(
            name="queuelite",
            role="Author",
            url="https://github.com/alexrivera/queuelite",
            start_date="2023",
            end_date="Present",
            description="A dependency-free job queue for Postgres, 2.1k stars.",
            bullets=[
                "Exactly-once delivery via advisory locks and a visibility "
                "timeout, with no external broker.",
            ],
        ),
    ],
    publications=[
        Publication(
            title="Backpressure Without Tears: Practical Flow Control in "
                  "Event Pipelines",
            authors="A. Rivera, J. Okonkwo",
            venue="USENIX SREcon Americas",
            year="2024",
        ),
    ],
)
