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

    def _load_profile(self) -> dict:
        with open(self.PROFILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _clean_response(text: str) -> dict:
        cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
        cleaned = re.sub(r"```\s*$", "", cleaned.strip())
        return json.loads(cleaned)

    def tailor_application(
        self,
        job_description_text: str,
        company_name: str,
        job_title: str,
    ) -> dict:
        profile = self._load_profile()

        prompt = (
            "You are an elite career strategist with deep expertise in Data Engineering, "
            "Machine Learning, Analytics, and modern AI-infrastructure hiring.\n\n"

            "## RULES\n"
            "1. **No Hallucination.** You must NEVER fabricate skills, tools, metrics, or "
            "experiences the candidate does NOT possess. Only reference what exists in "
            "their CANDIDATE PROFILE below.\n\n"

            "2. **Strict JSON Output.** Return **only** valid JSON with exactly two keys:\n"
            '   - `"tailored_bullet_points"`: a JSON array of exactly 5 powerful, '
            "ATS-optimised resume bullet points (strings).\n"
            '   - `"cold_email_body"`: a single string containing a concise, 3-paragraph '
            "cold email targeted at a hiring manager.\n"
            "   Do NOT wrap the JSON in markdown code fences or add any text outside it.\n\n"

            "3. **PLACEHOLDER BAN (CRITICAL).** The company you are writing for is "
            f'**"{company_name}"** and the role title is **"{job_title}"**. '
            "You MUST weave these exact names naturally into the cold email body. "
            "Under **NO circumstances** may you use ANY bracketed placeholder "
            "tokens anywhere in your output. This includes, but is not limited to: "
            "`[Company Name]`, `[Startup]`, `[Your Name]`, `[Hiring Manager Name]`, "
            "`[Platform]`, `[Link to Portfolio]`, `[Link to LinkedIn/Portfolio]`, "
            "`[Job Board]`, or ANY other `[...]` token. "
            "Use the candidate's actual name from the profile (not a placeholder). "
            "If you do not know a specific piece of information (e.g., the hiring "
            "manager's name or where the job was found), simply omit it or write "
            "around it gracefully.\n\n"

            "4. **STAR+ Narrative Pivot.** When generating bullet points from the "
            "candidate's past corporate data-engineering experience, dynamically reframe "
            "each accomplishment as \"Data Readiness for AI/ML.\" Retain every original "
            "quantitative metric exactly as stated in the profile.\n\n"

            "5. **Self-Referencing Portfolio Injection.** Evaluate the job title "
            f'"{job_title}":\n'
            "   - **IF technical** (Data Engineer, ML Engineer, etc.): highlight the "
            "candidate's \"AI Job Application Pipeline\" project emphasising Python "
            "orchestration, GenAI SDK integration, and automated multi-stage routing.\n"
            "   - **IF business-focused** (Product Manager, Analyst, etc.): highlight the "
            "same project but emphasise process optimisation and cycle-time reduction.\n\n"

            "6. **Salutation Fallback.** Never use placeholders like "
            "'[Hiring Manager Name]'. If a specific person is not mentioned in the "
            "job description, you must strictly use "
            f"'Dear Hiring Team at {company_name},' as the opening salutation.\n\n"

            "7. **No Markdown Links.** Under NO circumstances are you allowed to use "
            "Markdown hyperlink syntax (e.g., `[text](url)`) in the email body. "
            "If you reference a URL, output it as raw plain text.\n\n"

            "## CANDIDATE PROFILE\n"
            f"```json\n{json.dumps(profile, indent=2)}\n```\n\n"

            f"## TARGET COMPANY: {company_name}\n"
            f"## TARGET ROLE: {job_title}\n\n"
            "## JOB DESCRIPTION\n"
            f"```\n{job_description_text}\n```\n\n"

            "Now generate the JSON output."
        )

        response = self.client.models.generate_content(
            model=self.MODEL,
            contents=prompt,
        )

        return self._clean_response(response.text)
