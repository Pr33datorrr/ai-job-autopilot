import os
import re
import json
from google import genai


class ResumeTailor:
    """
    Uses the Google GenAI SDK (Gemma 3 27B-IT) to generate
    tailored resume bullet points and a cold email from a
    job description, grounded strictly in the user's master profile.
    """

    MODEL = "gemma-3-27b-it"
    PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "master_profile.json")

    def __init__(self):
        api_key = os.environ.get("GEMMA_API_KEY")
        if not api_key:
            raise ValueError("Environment variable GEMMA_API_KEY is not set.")

        self.client = genai.Client(api_key=api_key)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_profile(self) -> dict:
        """Read and return the master profile JSON."""
        with open(self.PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _clean_response(text: str) -> dict:
        """
        Strip markdown code fences (```json ... ```) if present,
        then parse the resulting string as JSON.
        """
        cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
        cleaned = re.sub(r"```\s*$", "", cleaned.strip())
        return json.loads(cleaned)

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def tailor_application(self, job_description_text: str) -> dict:
        """
        Compare *job_description_text* against the master profile and
        return a dict with ``tailored_bullet_points`` and ``cold_email_body``.
        """
        profile = self._load_profile()

        prompt = (
            "You are an elite career strategist with deep expertise in Data Engineering, "
            "Machine Learning, and Analytics hiring.\n\n"
            "## RULES\n"
            "1. You must NEVER hallucinate or invent skills, tools, or experiences the "
            "candidate does NOT possess. Only reference what exists in their profile.\n"
            "2. Return **strictly valid JSON** with exactly two keys:\n"
            '   - "tailored_bullet_points": a JSON array of exactly 5 powerful, '
            "ATS-optimized resume bullet points (strings).\n"
            '   - "cold_email_body": a single string containing a concise, 3-paragraph '
            "cold email targeted at a hiring manager for a Data/ML Internship.\n\n"
            "## CANDIDATE PROFILE\n"
            f"```json\n{json.dumps(profile, indent=2)}\n```\n\n"
            "## JOB DESCRIPTION\n"
            f"```\n{job_description_text}\n```\n\n"
            "Now generate the JSON output."
        )

        response = self.client.models.generate_content(
            model=self.MODEL,
            contents=prompt,
        )

        return self._clean_response(response.text)


# ======================================================================
# CLI entry-point
# ======================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    FAKE_JOB_DESCRIPTION = """
    Data Engineer Intern - Acme Corp (Vancouver, BC)

    We are looking for a Data Engineer Intern to join our Analytics Engineering
    team for Summer 2026.

    Responsibilities:
    - Build and maintain scalable ETL pipelines using Python and SQL.
    - Work with cloud data warehouses (BigQuery, Snowflake, or Redshift).
    - Collaborate with data scientists to operationalize ML models.
    - Monitor data quality and implement automated testing.

    Qualifications:
    - Pursuing a degree in Computer Science, Data Science, or related field.
    - Experience with Python, SQL, and at least one cloud platform (AWS/GCP).
    - Familiarity with Apache Spark or similar distributed compute frameworks.
    - Strong communication and teamwork skills.
    """

    tailor = ResumeTailor()
    result = tailor.tailor_application(FAKE_JOB_DESCRIPTION)

    print("\n===== Tailored Bullet Points =====")
    for i, bullet in enumerate(result["tailored_bullet_points"], 1):
        print(f"  {i}. {bullet}")

    print("\n===== Cold Email =====")
    print(result["cold_email_body"])
