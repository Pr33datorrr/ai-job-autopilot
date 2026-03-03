import os
import re
import json
from google import genai


class JobEvaluator:
    """
    Pre-processing logic gate that evaluates a job description against
    the candidate's master profile using Gemma 3 27B-IT.

    Returns a verdict dict with red-flag detection, match scoring,
    pain-point extraction, and a routing decision.
    """

    MODEL = "gemma-3-27b-it"
    PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "master_profile.json")

    # Safe fallback when JSON parsing fails
    _FALLBACK = {
        "red_flag_found": False,
        "red_flag_reason": None,
        "match_score": 70,
        "extracted_pain_point": "Unable to extract - LLM response was malformed.",
        "decision": "Proceed",
    }

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

    def evaluate_job(self, job_description_text: str) -> dict:
        """
        Evaluate *job_description_text* against the master profile and
        return a routing-decision dictionary.

        Keys returned:
            red_flag_found  (bool)
            red_flag_reason (str | None)
            match_score     (int 0-100)
            extracted_pain_point (str)
            decision        ("Proceed" | "Rejected - Red Flag" | "Low Match")
        """
        profile = self._load_profile()

        prompt = (
            "You are a harsh, no-nonsense technical recruiter. Your job is to "
            "evaluate whether a candidate should even APPLY to a given role. "
            "Be brutally honest.\n\n"

            "## RULES\n"
            "1. Compare the CANDIDATE PROFILE against the JOB DESCRIPTION.\n"
            "2. Identify any **hard red flags** -- requirements the candidate "
            "categorically does NOT meet and CANNOT reasonably substitute. "
            "Examples of red flags:\n"
            "   - 10+ years of professional experience required (candidate has ~3)\n"
            "   - Active security clearances (Top Secret, etc.)\n"
            "   - Legally-mandated credentials (nursing/medical degrees, CPA, bar admission)\n"
            "   - Ph.D. explicitly required (not preferred)\n"
            "   - Senior/Director/VP-level titles explicitly required\n"
            "3. Assign a `match_score` from 0 to 100 reflecting how well the "
            "candidate's skills, experience, and education match the core "
            "technical requirements.\n"
            "4. Extract the **primary technical or business problem** the company "
            "is trying to solve based on the JD.\n"
            "5. Set `decision` to one of exactly three values:\n"
            '   - `"Rejected - Red Flag"` if `red_flag_found` is true.\n'
            '   - `"Low Match"` if `match_score` < 60 and no red flag.\n'
            '   - `"Proceed"` if `match_score` >= 60 and no red flag.\n\n'

            "## OUTPUT FORMAT\n"
            "Return **only** valid JSON with exactly these keys:\n"
            "```\n"
            "{\n"
            '  "red_flag_found": true/false,\n'
            '  "red_flag_reason": "string or null",\n'
            '  "match_score": integer 0-100,\n'
            '  "extracted_pain_point": "string",\n'
            '  "decision": "Proceed" | "Rejected - Red Flag" | "Low Match"\n'
            "}\n"
            "```\n"
            "Do NOT wrap the JSON in markdown code fences or add any text "
            "outside it.\n\n"

            "## CANDIDATE PROFILE\n"
            f"```json\n{json.dumps(profile, indent=2)}\n```\n\n"

            "## JOB DESCRIPTION\n"
            f"```\n{job_description_text}\n```\n\n"

            "Now evaluate and return the JSON verdict."
        )

        response = self.client.models.generate_content(
            model=self.MODEL,
            contents=prompt,
        )

        try:
            return self._clean_response(response.text)
        except (json.JSONDecodeError, TypeError) as e:
            print(f"[JobEvaluator] WARNING: Failed to parse LLM response: {e}")
            print(f"[JobEvaluator] Raw response: {response.text[:500]}")
            return dict(self._FALLBACK)


# ======================================================================
# CLI entry-point - dual test harness
# ======================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    evaluator = JobEvaluator()

    # -- TEST 1: Red Flag JD --
    RED_FLAG_JD = """
    Senior Vice President of Cybersecurity - Pentagon Systems Inc. (Arlington, VA)

    Requirements:
    - Active Top Secret / SCI security clearance (non-negotiable).
    - Minimum 15 years of experience in a Senior VP or C-level cybersecurity role.
    - Ph.D. in Cybersecurity or Information Assurance required.
    - Must be a U.S. citizen with current polygraph on file.
    """

    print("=" * 60)
    print("TEST 1: Red Flag JD (should be REJECTED)")
    print("=" * 60)
    result1 = evaluator.evaluate_job(RED_FLAG_JD)
    for k, v in result1.items():
        print(f"  {k}: {v}")

    assert result1["red_flag_found"] is True, (
        f"FAIL: Expected red_flag_found=True, got {result1['red_flag_found']}"
    )
    assert result1["decision"] == "Rejected - Red Flag", (
        f"FAIL: Expected 'Rejected - Red Flag', got '{result1['decision']}'"
    )
    print("\n[PASS] Test 1: Red flag correctly detected.\n")

    # -- TEST 2: Good-match JD --
    GOOD_JD = """
    Junior Data Engineer - TechFlow Analytics (Vancouver, BC)

    We are hiring a Junior Data Engineer to join our growing data team.

    Responsibilities:
    - Build and maintain ETL pipelines using Python and SQL.
    - Work with cloud data platforms (AWS, GCP).
    - Collaborate with data scientists to prepare datasets for ML models.
    - Monitor data quality and implement automated testing.

    Qualifications:
    - Degree in Computer Science, Data Science, or related field.
    - Familiarity with Python, SQL, and at least one cloud platform.
    - Experience with Apache Spark or similar is a plus.
    - Strong communication and teamwork skills.
    """

    print("=" * 60)
    print("TEST 2: Good-match JD (should PROCEED)")
    print("=" * 60)
    result2 = evaluator.evaluate_job(GOOD_JD)
    for k, v in result2.items():
        print(f"  {k}: {v}")

    assert result2["decision"] == "Proceed", (
        f"FAIL: Expected 'Proceed', got '{result2['decision']}'"
    )
    assert result2["match_score"] >= 60, (
        f"FAIL: Expected match_score >= 60, got {result2['match_score']}"
    )
    print(f"\n[PASS] Test 2: Proceed with match score {result2['match_score']}.")
