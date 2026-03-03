"""
Dummy Job Routing Test
Sends 3 hardcoded jobs through the full HITL pipeline:
  JobEvaluator -> ResumeTailor -> PDF -> Drive Upload -> Sheet Log
"""
import os
import sys
import hashlib
from dotenv import load_dotenv

# Ensure project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

from src.job_filter import JobEvaluator
from src.ai_tailor import ResumeTailor
from src.pdf_generator import generate_pdf
from src.cloud_storage import upload_pdf_to_drive
from src.db_manager import SheetManager

# -- Dummy Jobs --
dummy_jobs = [
    {
        "employer_name": "CyberDyne Systems",
        "job_title": "Principal Cyber Operations",
        "job_apply_link": "https://example.com/cyberdyne",
        "job_description": (
            "STRICT REQUIREMENTS: Must possess an active Top Secret Canadian "
            "Security Clearance. Minimum 12+ years of enterprise DevOps experience. "
            "Expert in Rust, C++, and bare-metal Kubernetes. Medical background required."
        ),
    },
    {
        "employer_name": "Global FinTech Corp",
        "job_title": "Data Analyst",
        "job_apply_link": "https://example.com/fintech",
        "job_description": (
            "Looking for a Data Analyst with 2-3 years of experience. Must know "
            "SQL and Python. Experience with Tableau or PowerBI is highly preferred. "
            "Will be writing reports and basic data pipelines. Bachelor's degree required."
        ),
    },
    {
        "employer_name": "Nexus AI Analytics",
        "job_title": "Junior AI Data Engineer",
        "job_apply_link": "https://example.com/nexus",
        "job_description": (
            "Perfect for a recent Big Data grad! We need a Junior Data Engineer in "
            "Vancouver to build AI data pipelines. Required: Python, SQL, GCP experience, "
            "and familiarity with LLMs and Streamlit. 0-1 years experience."
        ),
    },
]


def main():
    print("=" * 60)
    print("  DUMMY JOB ROUTING TEST")
    print("=" * 60)

    safe_mode_email = os.environ.get("SAFE_MODE_EMAIL", "hello@yashanalytics.pro")

    print("\n[init] Instantiating services...")
    sheet_manager = SheetManager()
    job_evaluator = JobEvaluator()
    resume_tailor = ResumeTailor()

    for idx, job in enumerate(dummy_jobs, start=1):
        company = job["employer_name"]
        title = job["job_title"]
        description = job["job_description"]
        link = job["job_apply_link"]
        job_hash = hashlib.md5(f"{company}{title}".encode()).hexdigest()[:12]

        print(f"\n{'=' * 60}")
        print(f"  JOB {idx}/3: {company} - {title}")
        print(f"{'=' * 60}")

        # -- Step 1: Evaluate --
        print("  -> Evaluating job compatibility...")
        try:
            verdict = job_evaluator.evaluate_job(description)
            decision = verdict.get("decision", "Proceed")
            match_score = verdict.get("match_score", 0)
            pain_point = verdict.get("extracted_pain_point", "N/A")
            red_flag_reason = verdict.get("red_flag_reason", "")
        except Exception as e:
            print(f"  [!] Evaluation failed: {e}. Defaulting to Proceed.")
            decision, match_score, pain_point, red_flag_reason = "Proceed", 0, "N/A", ""

        print(f"  Decision: {decision}")
        print(f"  Match Score: {match_score}")
        print(f"  Pain Point: {pain_point}")

        # -- Route: Rejected --
        if decision == "Rejected - Red Flag":
            print(f"  [X] REJECTED - Red Flag: {red_flag_reason}")
            sheet_manager.log_job(
                job_hash_id=job_hash,
                company=company,
                title=title,
                status="Rejected - Red Flag",
                match_score=str(match_score),
                pain_point=pain_point,
                job_link=link,
            )
            print("  -> Logged to Sheet as 'Rejected - Red Flag'")
            continue

        # -- Route: Low Match --
        if isinstance(match_score, int) and match_score < 60:
            print(f"  [~] LOW MATCH (Score: {match_score} < 60). Skipping.")
            sheet_manager.log_job(
                job_hash_id=job_hash,
                company=company,
                title=title,
                status="Low Match",
                match_score=str(match_score),
                pain_point=pain_point,
                job_link=link,
            )
            print("  -> Logged to Sheet as 'Low Match'")
            continue

        # -- Route: VIP Lounge (Score >= 60) --
        print(f"  [OK] PROCEED (Score: {match_score}) - entering VIP lounge")

        # Tailor
        print("  -> Tailoring application...")
        tailored = resume_tailor.tailor_application(description, company, title)
        bullets = tailored.get("tailored_bullet_points", [])
        cold_email = tailored.get("cold_email_body", "")
        print(f"     Bullets: {len(bullets)} | Email: {len(cold_email)} chars")

        # PDF
        print("  -> Generating PDF...")
        pdf_result = generate_pdf(company, bullets)
        if pdf_result.get("status") != "success":
            err = pdf_result.get("error", "unknown")
            print(f"  [!] PDF failed: {err} - creating dummy PDF for Drive test")
            pdf_path = os.path.join("output", f"Resume_Yash_{company.replace(' ', '_')}.pdf")
            os.makedirs("output", exist_ok=True)
            with open(pdf_path, "wb") as f:
                f.write(
                    b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
                    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
                    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
                    b"xref\n0 4\n0000000000 65535 f \n"
                    b"0000000009 00000 n \n0000000058 00000 n \n0000000107 00000 n \n"
                    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF"
                )
        else:
            pdf_path = pdf_result["pdf_path"]

        # Drive Upload
        print("  -> Uploading to Google Drive...")
        try:
            pdf_cloud_link = upload_pdf_to_drive(pdf_path, company, safe_mode_email)
            print(f"     webViewLink: {pdf_cloud_link}")
        except Exception as e:
            print(f"  [!] Drive upload failed: {e}")
            pdf_cloud_link = ""

        # Sheet Log
        print("  -> Logging to Sheet as 'Pending Review'...")
        sheet_manager.log_job(
            job_hash_id=job_hash,
            company=company,
            title=title,
            status="Pending Review",
            match_score=str(match_score),
            pain_point=pain_point,
            email_draft_body=cold_email,
            pdf_cloud_link=pdf_cloud_link,
            job_link=link,
        )
        print("  -> Logged.")

    print(f"\n{'=' * 60}")
    print("  ALL 3 JOBS PROCESSED")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
