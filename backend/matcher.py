import hashlib
import logging
from typing import List, Tuple, Optional, Dict
from backend.models import (
    RoleType,
    ROLE_DISPLAY_MAP,
    JobD,
    CandidateResult,
    ScreeningResult,
    MatchResult,
    BatchAnalysisResponse,
)
from backend.parser import read_resume, extract_quick_name
from backend.typesafe_client import TypeSafeScreeningClient
from backend.screening import evaluate_screening
from backend.groq_client import GroqMatcherClient

logger = logging.getLogger("resume_analyzer.matcher")


class ResumeAnalyzerPipeline:
    """
    Two-Stage Resume Analyzer Pipeline:
    Stage 1: TypeSafe System One (Choice, Noul, Score) + Deterministic Python Filtering.
    Stage 2: Groq LLM Detailed Analysis (ONLY for Stage 1 passing candidates).
    """

    def __init__(self):
        self.typesafe = TypeSafeScreeningClient()
        self.groq = GroqMatcherClient()
        self._cache: Dict[str, CandidateResult] = {}

    def analyze_batch(
        self,
        files: List[Tuple[str, bytes]],
        job_description_text: str,
        target_role_display: str,
    ) -> BatchAnalysisResponse:
        """
        Process a batch of uploaded resumes through the two-stage pipeline.
        Ensures 100 resumes != 100 Groq calls.
        """
        target_role = ROLE_DISPLAY_MAP.get(target_role_display, RoleType.BACKEND)
        total_resumes = len(files)
        jd_hash = hashlib.sha256(job_description_text.strip().encode("utf-8")).hexdigest()
        logger.info(
            f"Starting pipeline for {total_resumes} resumes against role: {target_role_display} ({target_role.value})"
        )

        candidates: List[CandidateResult] = []
        passed_stage_1_items: List[Tuple[CandidateResult, str, str]] = []  # (CandidateResult, resume_text, cache_key)

        # -----------------------------------------------------------------
        # STAGE 1: Text Extraction & TypeSafe Screening + Python Filtering
        # -----------------------------------------------------------------
        for filename, content_bytes in files:
            file_hash = hashlib.sha256(content_bytes).hexdigest()
            cache_key = f"{file_hash}_{target_role.value}_{jd_hash}"

            if cache_key in self._cache:
                logger.info(f"Returning deterministic cached result for {filename}")
                cached_candidate = self._cache[cache_key].model_copy(deep=True)
                cached_candidate.filename = filename
                candidates.append(cached_candidate)
                continue
            # 1. Text extraction
            try:
                resume_text = read_resume(content_bytes, filename=filename)
                if not resume_text or not resume_text.strip():
                    candidates.append(
                        CandidateResult(
                            filename=filename,
                            name=extract_quick_name("", filename),
                            screening=ScreeningResult(
                                passes_screening=False,
                                reason="File is empty or contains no extractable text",
                            ),
                            status="error",
                            error="Empty or unreadable document content",
                        )
                    )
                    continue
            except Exception as e:
                logger.error(f"Error reading file {filename}: {e}")
                candidates.append(
                    CandidateResult(
                        filename=filename,
                        name=extract_quick_name("", filename),
                        screening=ScreeningResult(
                            passes_screening=False,
                            reason=f"Failed to read file: {str(e)}",
                        ),
                        status="error",
                        error=f"Extraction failure: {str(e)}",
                    )
                )
                continue

            quick_name = extract_quick_name(resume_text, filename)

            # 2. TypeSafe Stage 1 Evaluation
            try:
                raw_screening = self.typesafe.screen_resume(
                    resume_text=resume_text,
                    target_role=target_role,
                    target_role_display=target_role_display,
                    candidate_name=quick_name,
                )
            except Exception as e:
                logger.error(f"TypeSafe screening failed for {filename}: {e}")
                candidates.append(
                    CandidateResult(
                        filename=filename,
                        name=quick_name,
                        screening=ScreeningResult(
                            passes_screening=False,
                            reason=f"TypeSafe API error: {str(e)}",
                        ),
                        status="error",
                        error=f"TypeSafe API error: {str(e)}",
                    )
                )
                continue

            # 3. Deterministic Python Filtering
            final_screening = evaluate_screening(raw_screening, target_role)

            cand_result = CandidateResult(
                filename=filename,
                name=quick_name,
                screening=final_screening,
                status="passed" if final_screening.passes_screening else "filtered",
            )

            candidates.append(cand_result)

            if final_screening.passes_screening:
                passed_stage_1_items.append((cand_result, resume_text, cache_key))
            else:
                self._cache[cache_key] = cand_result.model_copy(deep=True)
                logger.info(
                    f"Candidate {quick_name} ({filename}) FILTERED at Stage 1. Reason: {final_screening.reason}"
                )

        passed_count = len(passed_stage_1_items)
        filtered_count = sum(1 for c in candidates if c.status == "filtered")
        error_count = sum(1 for c in candidates if c.status == "error")

        logger.info(
            f"Stage 1 Complete. Total: {total_resumes}, Passed: {passed_count}, "
            f"Filtered: {filtered_count}, Errors: {error_count}"
        )

        # -----------------------------------------------------------------
        # STAGE 2: Groq Detailed Analysis (ONLY for Stage 1 passed candidates)
        # -----------------------------------------------------------------
        if passed_stage_1_items:
            # Parse Job Description once for the batch
            try:
                job_d = self.groq.parse_job_description(
                    job_description_text=job_description_text,
                    fallback_role=target_role_display,
                )
            except Exception as e:
                logger.error(f"Failed to parse Job Description with Groq: {e}")
                job_d = JobD(
                    role=target_role_display,
                    required_skills=[],
                    preferred_skills=[],
                    education_requirements=[],
                    responsibilities=[],
                )

            for cand_result, resume_text, item_cache_key in passed_stage_1_items:
                try:
                    # Groq Call 1: Structured Resume Extraction
                    parsed_resume = self.groq.parse_resume(resume_text)
                    if parsed_resume.name:
                        cand_result.name = parsed_resume.name
                        cand_result.screening.candidate_name = parsed_resume.name

                    # Groq Call 2: Final Detailed Match Score
                    match_result = self.groq.final_score(job_d, parsed_resume)
                    cand_result.match = match_result
                    cand_result.status = "passed"
                    logger.info(
                        f"Candidate {cand_result.name} Groq Stage 2 Match Score: {match_result.score}%"
                    )
                except Exception as e:
                    logger.error(f"Groq Stage 2 failed for {cand_result.filename}: {e}")
                    cand_result.error = f"Groq Stage 2 analysis error: {str(e)}"
                    # Candidate still retains Stage 1 passed info

                # Save passed/scored result in cache
                self._cache[item_cache_key] = cand_result.model_copy(deep=True)

        # Sort: Passed candidates first by match score descending, then filtered, then errors
        def sort_key(c: CandidateResult):
            if c.status == "passed" and c.match:
                return (3, c.match.score)
            elif c.status == "passed":
                return (2, 0.0)
            elif c.status == "filtered":
                return (1, c.screening.role_confidence or 0.0)
            else:
                return (0, 0.0)

        candidates.sort(key=sort_key, reverse=True)

        return BatchAnalysisResponse(
            target_role=target_role,
            target_role_display=target_role_display,
            total_resumes=total_resumes,
            passed_count=passed_count,
            filtered_count=filtered_count,
            error_count=error_count,
            candidates=candidates,
        )
