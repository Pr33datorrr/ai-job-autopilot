import os
from dotenv import load_dotenv
from src.db_manager import SheetManager
from src.job_fetcher import JobFetcher
from src.ai_tailor import ResumeTailor
from src.job_filter import JobEvaluator
from src.pdf_generator import generate_pdf
from src.cloud_storage import upload_pdf_to_drive

def main():
    # Load environment variables
    load_dotenv()
    
    # 1. Instantiate Managers
    print("\n[main] Initializing services...")
    try:
        sheet_manager = SheetManager()
        job_fetcher = JobFetcher()
        resume_tailor = ResumeTailor()
        job_evaluator = JobEvaluator()
    except Exception as e:
        print(f"[main] Initialization failed: {e}")
        return

    # 2. Fetch jobs
    print("\n[main] Fetching jobs from JSearch API...")
    try:
        new_jobs = job_fetcher.fetch_jobs()
    except Exception as e:
        print(f"[main] Failed to fetch jobs: {e}")
        return

    if not new_jobs:
        print("[main] No new jobs found. Exiting.")
        return

    print(f"\n[main] Processing {len(new_jobs)} new jobs in HUMAN-IN-THE-LOOP mode...\n")
    
    # 3. Process each job
    safe_mode_email = os.environ.get("SAFE_MODE_EMAIL")
    if not safe_mode_email:
        print("[main] ERROR: SAFE_MODE_EMAIL environment variable is not set. Exiting.")
        return

    for idx, job in enumerate(new_jobs, start=1):
        job_hash = job["job_hash_id"]
        company = job["company_name"]
        title = job["job_title"]
        description = job["job_description"]
        link = job["apply_link"]
        
        print(f"--- Job {idx}/{len(new_jobs)}: {company} - {title} ---")
        
        # Double check if it exists (job_fetcher already checks, but good to be safe)
        if sheet_manager.job_exists(job_hash):
            print(f"   [!] Job {job_hash} already exists in Sheet. Skipping.")
            continue

        # Job Evaluation Gate
        print("   -> Evaluating job compatibility...")
        try:
            verdict = job_evaluator.evaluate_job(description)
            decision = verdict.get("decision", "Proceed")
            match_score = verdict.get("match_score", "N/A")
            pain_point = verdict.get("extracted_pain_point", "N/A")
        except Exception as e:
            print(f"   [!] Job evaluation failed: {e}. Proceeding anyway.")
            decision = "Proceed"
            match_score = "N/A"
            pain_point = "N/A"

        if decision == "Rejected - Red Flag":
            reason = verdict.get("red_flag_reason", "Unknown")
            print(f"   [X] REJECTED (Red Flag): {reason}")
            sheet_manager.log_job(
                job_hash_id=job_hash,
                company=company,
                title=title,
                status="Rejected - Red Flag",
                match_score=match_score,
                pain_point=pain_point,
                job_link=link,
            )
            continue

        if decision == "Low Match":
            print(f"   [~] LOW MATCH (Score: {match_score}). Skipping.")
            sheet_manager.log_job(
                job_hash_id=job_hash,
                company=company,
                title=title,
                status="Low Match",
                match_score=match_score,
                pain_point=pain_point,
                job_link=link,
            )
            continue

        # Numeric safety net: catch anything the evaluator missed
        try:
            score_int = int(match_score)
        except (ValueError, TypeError):
            score_int = 0

        if score_int < 60:
            print(f"   [~] LOW MATCH (Score: {score_int} < 60). Skipping.")
            sheet_manager.log_job(
                job_hash_id=job_hash,
                company=company,
                title=title,
                status="Low Match",
                match_score=match_score,
                pain_point=pain_point,
                job_link=link,
            )
            continue

        print(f"   [OK] PROCEED (Score: {match_score}) | Pain Point: {pain_point}")

        # AI Tailoring
        print("   -> Tailoring application with Gemini...")
        try:
            tailored_data = resume_tailor.tailor_application(description, company, title)
            bullets = tailored_data.get("tailored_bullet_points", [])
            cold_email = tailored_data.get("cold_email_body", "")
        except Exception as e:
            print(f"   [!] Failed to tailor application: {e}")
            continue
            
        # PDF Generation
        print("   -> Generating tailored PDF resume...")
        pdf_result = generate_pdf(company, bullets)
        if pdf_result.get("status") != "success":
            print(f"   [!] PDF generation failed: {pdf_result.get('error')}")
            continue
            
        pdf_path = pdf_result["pdf_path"]
        
        # Upload to Google Drive
        print(f"   -> Uploading PDF to Google Drive...")
        try:
            pdf_cloud_link = upload_pdf_to_drive(pdf_path, company, safe_mode_email)
        except Exception as e:
            print(f"   [!] Drive upload failed: {e}")
            pdf_cloud_link = ""

        # Log to Google Sheet as Pending Review
        print("   -> Logging to Google Sheet as 'Pending Review'...")
        sheet_manager.log_job(
            job_hash_id=job_hash,
            company=company,
            title=title,
            status="Pending Review",
            match_score=match_score,
            pain_point=pain_point,
            email_draft_body=cold_email,
            pdf_cloud_link=pdf_cloud_link,
            job_link=link,
        )
        print("   -> Logged.")

    print("\n[main] Pipeline execution complete.")

if __name__ == "__main__":
    main()
