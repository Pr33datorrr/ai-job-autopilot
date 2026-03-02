import os
import time
import hashlib
import requests
from src.db_manager import SheetManager


class JobFetcher:
    """
    Fetches jobs from the RapidAPI JSearch endpoint and
    deduplicates them against the Google Sheet via SheetManager.
    """

    ENDPOINT = "https://jsearch.p.rapidapi.com/search"

    def __init__(self):
        api_key = os.environ.get("RAPIDAPI_KEY")
        if not api_key:
            raise ValueError("Environment variable RAPIDAPI_KEY is not set.")

        self.headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": os.environ.get("RAPIDAPI_HOST", "jsearch.p.rapidapi.com"),
        }

        self.queries = [
            "Data Engineer Intern in Vancouver",
            "Part Time Data Analyst in Vancouver",
            "Remote Machine Learning Intern in Canada",
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_hash(company: str, title: str) -> str:
        """Return a SHA-256 hex digest from (company + title), lowered & stripped."""
        raw = f"{company.lower().strip()}{title.lower().strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def fetch_jobs(self) -> list[dict]:
        """
        Iterate through each query, hit JSearch, collect results,
        then deduplicate the combined list against the Sheet.
        """
        all_jobs: list[dict] = []

        for idx, query in enumerate(self.queries):
            print(f"[{idx + 1}/{len(self.queries)}] Searching: {query}")

            params = {
                "query": query,
                "num_pages": "1",  # ~5-7 results per query
            }

            response = requests.get(
                self.ENDPOINT,
                headers=self.headers,
                params=params,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json().get("data", [])
            print(f"   -> Received {len(data)} jobs.")

            for item in data:
                company = item.get("employer_name", "")
                title = item.get("job_title", "")
                description = item.get("job_description", "")
                link = item.get("job_apply_link", "")

                job_hash = self._generate_hash(company, title)
                all_jobs.append({
                    "job_hash_id": job_hash,
                    "company_name": company,
                    "job_title": title,
                    "job_description": description,
                    "apply_link": link,
                })

            # Respect API rate limits between calls
            if idx < len(self.queries) - 1:
                time.sleep(2)

        print(f"\nTotal jobs fetched: {len(all_jobs)}")

        # Deduplicate against Google Sheet
        print("Checking for duplicates against Google Sheet...")
        sheet = SheetManager()
        new_jobs = [j for j in all_jobs if not sheet.job_exists(j["job_hash_id"])]
        print(f"{len(new_jobs)} new (deduplicated) jobs found.")

        return new_jobs


# ======================================================================
# CLI entry-point
# ======================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()  # loads .env into os.environ

    fetcher = JobFetcher()
    deduplicated = fetcher.fetch_jobs()

    if not deduplicated:
        print("\nNo new jobs to log.")
    else:
        print(f"\n--- {len(deduplicated)} Deduplicated Jobs ---\n")
        for idx, job in enumerate(deduplicated, start=1):
            print(f"{idx}. {job['company_name']} - {job['job_title']}")
            print(f"   Hash:  {job['job_hash_id']}")
            print(f"   Link:  {job['apply_link']}")
            print()

        # Log every new job to Google Sheet with status "Scraped"
        print("Logging jobs to Google Sheet...")
        sheet = SheetManager()
        for job in deduplicated:
            sheet.log_job(
                job["job_hash_id"],
                job["company_name"],
                job["job_title"],
                "Scraped",
                job["apply_link"],
            )
        print("Done - all jobs logged.")
