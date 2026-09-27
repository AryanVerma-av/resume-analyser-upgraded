import json
import logging
from typing import Optional
from groq import Groq
from backend.config import GROQ_API_KEY, GROQ_MODEL
from backend.models import JobD, Resume, MatchResult

logger = logging.getLogger("resume_analyzer.groq")


class GroqMatcherClient:
    """
    Stage 2 Detailed Matching Client powered by Groq.
    Preserves and refactors existing codebase methods:
    - parse_job_description()
    - parse_resume()
    - final_score()
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or GROQ_API_KEY
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not configured in .env")
        self.model = model or GROQ_MODEL
        self.client = Groq(api_key=self.api_key)

    def parse_job_description(self, job_description_text: str, fallback_role: str = "Software Engineer") -> JobD:
        """Extract structured JobD from free-form job description text."""
        jobd_schema = JobD.model_json_schema()
        system_prompt = f"""
You are an expert HR assistant.
Your job is to analyze job descriptions and extract structured information from them.
Return ONLY valid JSON matching this schema:
{json.dumps(jobd_schema, indent=2)}

IMPORTANT:
Do NOT return the schema itself.
Fill the schema with actual information extracted from the job description.
If minimum experience is not mentioned, return null.
If information for a list is missing, return an empty list.
Do not invent information.
"""
        user_prompt = f"""Analyze the following job description:\n\n{job_description_text}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            raw_json = response.choices[0].message.content
            job_data = json.loads(raw_json)
            if not job_data.get("role"):
                job_data["role"] = fallback_role
            return JobD(**job_data)
        except Exception as e:
            logger.warning(f"Error parsing JobD with Groq, falling back to minimal JobD: {e}")
            return JobD(
                role=fallback_role,
                required_skills=[],
                preferred_skills=[],
                minimum_experience=None,
                education_requirements=[],
                responsibilities=[],
            )

    def parse_resume(self, resume_text: str) -> Resume:
        """Extract structured Resume from resume text using Groq."""
        resume_schema = Resume.model_json_schema()
        system_prompt = f"""
You are an expert resume parser.
Extract information from the resume based on its meaning, not only based on exact section headings.
Different resumes may use different headings (Experience, Work History, Internships, etc.).
Skills may also appear in work experience, internships, or projects.

Return ONLY valid JSON matching this schema:
{json.dumps(resume_schema, indent=2)}

Important rules:
1. Do not invent information.
2. If a value is not available, return null.
3. If a list has no information, return an empty list.
4. Include internships inside experiences.
5. Extract skills mentioned across the entire resume.
"""
        user_prompt = f"""Parse the following resume:\n\n{resume_text}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        raw_output = response.choices[0].message.content
        data = json.loads(raw_output)
        return Resume(**data)

    def final_score(self, job: JobD, resume: Resume) -> MatchResult:
        """
        Stage 2 detailed matching comparing JobD with Resume.
        Returns validated MatchResult with score, matching skills, missing skills, and verdict.
        """
        prompt = f"""
You are an HR recruiter.
Compare the candidate's resume with the job description.

JOB DESCRIPTION:
{job.model_dump_json(indent=2)}

CANDIDATE RESUME:
{resume.model_dump_json(indent=2)}

Return JSON matching this exact structure:
{{
  "candidate_name": "Candidate's full name",
  "score": 85.0,
  "matching_skills": ["Skill1", "Skill2"],
  "missing_skills": ["Skill3"],
  "experience_met": true,
  "verdict": "Concise 1-2 sentence final verdict summarizing candidate fit.",
  "details": {{
      "summary": "Detailed summary of candidate match",
      "experience_summary": "Summary of relevant experience"
  }}
}}

Rules:
1. "score" MUST be a float from 0 to 100 representing overall percentage match.
2. List actual matching and missing skills.
3. Keep the verdict concise, accurate, and easy to read.
"""
        messages = [{"role": "user", "content": prompt}]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0,
        )
        data = json.loads(response.choices[0].message.content)

        # Ensure candidate_name is populated if available on resume
        if not data.get("candidate_name") and resume.name:
            data["candidate_name"] = resume.name

        score_val = float(data.get("score", 0.0))
        # Ensure score is within 0-100
        score_val = max(0.0, min(100.0, score_val))
        data["score"] = score_val

        return MatchResult(**data)
