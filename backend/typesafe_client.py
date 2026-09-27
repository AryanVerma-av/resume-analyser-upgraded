import logging
from typing import Optional, Dict, Any
from typesafe_sdk import TypeSafeClient, Choice, Noul, Score, TypeSafeError, TypeSafeAPIError
from backend.config import TYPESAFE_API_KEY, TYPESAFE_MODEL, EXPERIENCE_THRESHOLD
from backend.models import RoleType, ScreeningResult, parse_role_type

logger = logging.getLogger("resume_analyzer.typesafe")


class TypeSafeScreeningClient:
    """
    TypeSafe System One Screening Client.
    Evaluates atomic primitives (Choice, Noul, Score) in a single parallel API call.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or TYPESAFE_API_KEY
        if not self.api_key:
            raise ValueError("TYPESAFE_API_KEY is not configured in .env")
        self.model = model or TYPESAFE_MODEL
        self.client = TypeSafeClient(api_key=self.api_key, model=self.model)

    def screen_resume(
        self,
        resume_text: str,
        target_role: RoleType,
        target_role_display: str,
        candidate_name: Optional[str] = None,
    ) -> ScreeningResult:
        """
        Screen a candidate's resume using TypeSafe System One atomic questions.
        - Question 1 (Choice): Candidate's primary technical role
        - Question 2 (Noul): Relevant experience for target role
        - Question 3 (Score): Basic technical skill fit for target role
        """
        if not resume_text or not resume_text.strip():
            return ScreeningResult(
                candidate_name=candidate_name,
                passes_screening=False,
                reason="Empty or unreadable resume text",
            )

        questions = {
            "role": Choice(
                instructions="What is this candidate's primary technical role or engineering specialization based on their resume?",
                criteria={
                    "backend": "Backend software engineering, server-side APIs, databases, microservices, server logic",
                    "frontend": "Frontend development, UI/UX, web interfaces, client-side frameworks like React/Vue/Angular",
                    "fullstack": "Full stack software development combining both backend services and frontend interfaces",
                    "devops": "DevOps, infrastructure, CI/CD pipelines, cloud deployment, Kubernetes, Docker, site reliability",
                    "data": "Data analysis, data engineering, ETL, business intelligence, SQL analytics, data pipelines",
                    "ai_ml": "Machine learning, AI, data science, deep learning, NLP, computer vision, AI model training",
                },
            ),
            "experience": Noul(
                instructions=f"Does this candidate have practical experience, internships, or substantive projects relevant to a {target_role_display} role?",
            ),
            "skill_fit": Score(
                instructions=f"How well do the technical skills in this resume match the essential requirements of a {target_role_display}?",
                criteria=[
                    "Unrelated skills or no relevant technical foundation",
                    "Minimal or adjacent skills with weak alignment to the role",
                    "Moderate skill alignment meeting several fundamental requirements",
                    "Strong technical skill alignment with core requirements",
                ],
            ),
        }

        try:
            response = self.client.system_one(
                state=resume_text,
                questions=questions,
                model=self.model,
            )

            # 1. Parse Choice (Role)
            role_choice = response.choices["role"]
            raw_role_str = role_choice.choice
            detected_role = parse_role_type(raw_role_str)
            role_confidence = float(role_choice.confidence) if role_choice.confidence is not None else None
            role_probabilities = {k: float(v) for k, v in role_choice.probabilities.items()}

            # 2. Parse Noul (Experience)
            exp_noul = response.nouls["experience"]
            exp_prob = float(exp_noul.noul)
            has_experience = exp_prob >= EXPERIENCE_THRESHOLD

            # 3. Parse Score (Skill Fit: 0 to 3 scale)
            score_fit = response.scores["skill_fit"]
            fit_score = float(score_fit.score)
            fit_confidence = float(score_fit.confidence) if score_fit.confidence is not None else None
            fit_probabilities = {str(k): float(v) for k, v in score_fit.probabilities.items()}

            return ScreeningResult(
                candidate_name=candidate_name,
                role_type=detected_role,
                role_confidence=role_confidence,
                role_probabilities=role_probabilities,
                has_relevant_experience=has_experience,
                experience_probability=exp_prob,
                basic_fit_score=fit_score,
                basic_fit_confidence=fit_confidence,
                basic_fit_probabilities=fit_probabilities,
                passes_screening=False,  # Evaluated by Python deterministic logic
                reason=None,
            )

        except (TypeSafeError, TypeSafeAPIError) as e:
            logger.error(f"TypeSafe API error screening candidate {candidate_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in TypeSafe screening for {candidate_name}: {e}")
            raise
