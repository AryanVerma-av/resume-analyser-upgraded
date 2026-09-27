import logging
import backend.config as cfg
from backend.models import RoleType, ScreeningResult

logger = logging.getLogger("resume_analyzer.screening")


def evaluate_screening(screening: ScreeningResult, target_role: RoleType) -> ScreeningResult:
    """
    Deterministic Python filtering logic (Stage 1).
    Evaluates TypeSafe's structured outputs against deterministic rules and thresholds.
    """
    # 1. Unrecognized or missing role
    if screening.role_type is None:
        screening.passes_screening = False
        screening.reason = "Unrecognized technical role classification"
        return screening

    # 2. Strict Role Matching (Deterministic Python check)
    if screening.role_type != target_role:
        screening.passes_screening = False
        screening.reason = f"Role mismatch (Detected: {screening.role_type.value}, Target: {target_role.value})"
        return screening

    # 3. Role Confidence Threshold
    if screening.role_confidence is not None and screening.role_confidence < cfg.ROLE_CONFIDENCE_THRESHOLD:
        screening.passes_screening = False
        screening.reason = (
            f"Uncertain role classification (Confidence {screening.role_confidence:.2f} "
            f"< threshold {cfg.ROLE_CONFIDENCE_THRESHOLD:.2f})"
        )
        return screening

    # 4. Relevant Experience Probability Check (from Noul)
    if screening.experience_probability is not None and screening.experience_probability < cfg.EXPERIENCE_THRESHOLD:
        screening.passes_screening = False
        screening.reason = (
            f"Insufficient relevant role experience (Confidence {screening.experience_probability:.2f} "
            f"< threshold {cfg.EXPERIENCE_THRESHOLD:.2f})"
        )
        return screening

    # 5. Basic Skill Fit Score Check (Normalized to 0.0 - 1.0 from 0-3 level scale)
    if screening.basic_fit_score is not None:
        normalized_fit = screening.basic_fit_score / 3.0
        if normalized_fit < cfg.BASIC_FIT_THRESHOLD:
            screening.passes_screening = False
            screening.reason = (
                f"Basic skill fit below requirement (Score {normalized_fit * 100:.0f}% "
                f"< threshold {cfg.BASIC_FIT_THRESHOLD * 100:.0f}%)"
            )
            return screening

    # All criteria passed
    screening.passes_screening = True
    screening.reason = "Passed Stage 1 screening"
    return screening
