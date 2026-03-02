import os
from dotenv import load_dotenv
from src.db_manager import SheetManager
from src.job_fetcher import JobFetcher
from src.ai_tailor import ResumeTailor
from src.pdf_generator import generate_pdf
from src.email_dispatcher import send_cold_email

def main():
    # Load environment variables
    load_dotenv()
    
    # 1. Instantiate Managers
    print("\n[main] Initializing services...")
    try:
        sheet_manager = SheetManager()
        job_fetcher = JobFetcher()
        resume_tailor = ResumeTailor()
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

    print(f"\n[main] Processing {len(new_jobs)} new jobs in SAFE MODE...\n")
    
    # 3. Process each job
    safe_mode_email = os.environ.get("SAFE_MODE_EMAIL")
    if not safe_mode_email:
        print("[main] ERROR: SAFE_MODE_EMAIL environment variable is not set. Exiting to prevent real dispatches.")
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
            
        # AI Tailoring
        print("   -> Tailoring application with Gemini...")
        try:
            tailored_data = resume_tailor.tailor_application(description)
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
        
        # Dispatch Email (Safe Mode)
        print(f"   -> Dispatching SAFE MODE email to {safe_mode_email}...")
        email_subject = f"Application: {title} - Yash Gupta"
        
        email_success = send_cold_email(
            to_email=safe_mode_email,
            subject=email_subject,
            body_text=cold_email,
            pdf_attachment_path=pdf_path,
            test_mode=False  # Keep human jitter enabled!
        )
        
        if email_success:
            print("   -> Email sent successfully. Logging to Google Sheet...")
            sheet_manager.log_job(
                job_hash_id=job_hash,
                company=company,
                title=title,
                status="Emailed (Safe Mode)",
                link=link
            )
            print("   -> Logged.")
        else:
            print("   [!] Email dispatch failed.")

    print("\n[main] Pipeline execution complete.")

if __name__ == "__main__":
    main()
