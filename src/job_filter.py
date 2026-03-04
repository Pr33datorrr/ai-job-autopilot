import os
import re
import json
from google import genai


class JobEvaluator:
    """
    Pre-processing logic gate that evaluates a job description against
    the candidate's master profile using Gemma 3 12B-IT (lighter model
    to stay within the 15k TPM budget).

    Returns a verdict dict with red-flag detection, match scoring,
    pain-point extraction, evaluation reasoning, and a routing decision.
    """

    MODEL = "gemma-3-12b-it"
    PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "master_profile.json")

    # Safe fallback when JSON parsing fails
    _FALLBACK = {
        "red_flag_found": False,
        "red_flag_reason": None,
        "match_score": 70,
        "extracted_pain_point": "Unable to extract - LLM response was malformed.",
        "evaluation_reason": "Fallback: LLM response could not be parsed.",
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
            evaluation_reason (str)
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
            "5. Provide an `evaluation_reason`: a 1-2 sentence bulleted summary "
            "of exactly why this job is a Proceed, Low Match, or Red Flag.\n"
            "6. Set `decision` to one of exactly three values:\n"
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
            '  "evaluation_reason": "string",\n'
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
