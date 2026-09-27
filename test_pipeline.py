import os
import sys
from pathlib import Path

# Ensure root directory is on python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Ensure UTF-8 output on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.matcher import ResumeAnalyzerPipeline
from backend.models import RoleType

SAMPLE_AMAZON_JD = """
Amazon - Software Development Engineer I (SDE-I)
Basic Qualifications:
- Experience with at least one general-purpose programming language such as Java, Python, C++, C#, Go, Rust, or TypeScript
- Experience with data structure implementation, basic algorithm development, and/or object-oriented design principles
- Currently has, or in process of obtaining bachelor's degree in CS, Computer Engineering, or related STEM field
- Backend API development, database interaction (SQL/NoSQL), microservices architecture
Preferred Qualifications:
- Experience from previous technical internship(s) or demonstrated project experience
- Experience with cloud platforms (preferably AWS), database systems, version control (Git)
- Basic understanding of software development lifecycle (SDLC)
- Strong problem-solving and analytical skills
"""

def main():
    print("=" * 70)
    print("RESUME ANALYZER PIPELINE TEST (TYPESAFE STAGE 1 + GROQ STAGE 2)")
    print("=" * 70)

    pipeline = ResumeAnalyzerPipeline()

    test_files = [
        ("backend_resume.pdf", Path("resumes/backend_resume.pdf").read_bytes()),
        ("frontend_resume.pdf", Path("resumes/frontend_resume.pdf").read_bytes()),
        ("devops_resume.pdf", Path("resumes/devops_resume.pdf").read_bytes()),
        ("backend_resume_2.pdf", Path("resumes/backend_resume_2.pdf").read_bytes()),
        ("corrupted_sample.pdf", b"NOT_A_REAL_PDF_DATA_TESTING_FAULT_TOLERANCE"),
    ]

    target_role_display = "Junior Backend Developer"
    print(f"\nTarget Role Selected: {target_role_display}")
    print(f"Total Files in Batch: {len(test_files)}")

    response = pipeline.analyze_batch(
        files=test_files,
        job_description_text=SAMPLE_AMAZON_JD,
        target_role_display=target_role_display,
    )

    print("\n" + "-" * 70)
    print("BATCH METRICS:")
    print(f"Total Resumes: {response.total_resumes}")
    print(f"Passed Stage 1: {response.passed_count}")
    print(f"Filtered at Stage 1: {response.filtered_count}")
    print(f"Errors (handled gracefully): {response.error_count}")
    print(f"Groq API Calls Saved: {((response.filtered_count / response.total_resumes) * 100):.1f}%")
    print("-" * 70)

    print("\n[STAGE 2 RESULTS - PASSED CANDIDATES]")
    passed = [c for c in response.candidates if c.status == "passed"]
    for c in passed:
        print(f"[PASSED] Candidate: {c.name} ({c.filename})")
        print(f"  Stage 1 Role: {c.screening.role_type.value} (Conf: {c.screening.role_confidence})")
        print(f"  Stage 1 Exp Prob: {c.screening.experience_probability}")
        if c.match:
            print(f"  Stage 2 Groq Match Score: {c.match.score}%")
            print(f"  Matching Skills: {c.match.matching_skills}")
            print(f"  Missing Skills: {c.match.missing_skills}")
            print(f"  Verdict: {c.match.verdict}")
        else:
            print("  Stage 2 Match: None")
        print()

    print("\n[STAGE 1 FILTERED CANDIDATES - STOPPED BEFORE GROQ]")
    filtered = [c for c in response.candidates if c.status == "filtered"]
    for c in filtered:
        detected = c.screening.role_type.value if c.screening.role_type else "None"
        print(f"[FILTERED] Candidate: {c.name} ({c.filename})")
        print(f"  Detected Role: {detected}")
        print(f"  Role Confidence: {c.screening.role_confidence}")
        print(f"  Filter Reason: {c.screening.reason}")
        assert c.match is None, "ERROR: Filtered candidate must NOT have Groq Stage 2 MatchResult!"
        print()

    print("\n[HANDLED ERRORS]")
    errors = [c for c in response.candidates if c.status == "error"]
    for c in errors:
        print(f"! File: {c.filename} | Error: {c.error}")

    # Assertions
    print("\n" + "=" * 70)
    print("VERIFYING PIPELINE ARCHITECTURAL INVARIANTS:")
    assert len(passed) == 2, f"Expected exactly 2 passed backend candidates, got {len(passed)}"
    assert len(filtered) == 2, f"Expected exactly 2 filtered candidates (frontend, devops), got {len(filtered)}"
    assert len(errors) == 1, f"Expected exactly 1 handled error, got {len(errors)}"
    for p in passed:
        assert p.screening.role_type == RoleType.BACKEND, "Passed candidate must be backend"
        assert p.match is not None, "Passed candidate must have Stage 2 Groq match"
    for f in filtered:
        assert f.match is None, "Filtered candidate must NOT reach Stage 2 Groq"
    print("ALL ARCHITECTURAL INVARIANTS VERIFIED!")
    print("=" * 70)

if __name__ == "__main__":
    main()
