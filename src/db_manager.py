import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

class SheetManager:
    """
    Manager class for interacting with Google Sheets database.
    Authenticates using a Service Account JSON file.

    Schema (11 columns):
    Job_Hash_ID | Company | Job_Title | Status | Match_Score |
    Evaluation_Reason | Pain_Point | Email_Draft_Body |
    PDF_Cloud_Link | Job_Link | Applied_To_Email
    """
    def __init__(self):
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        creds_path = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
        if not creds_path:
            raise ValueError("Environment variable GOOGLE_SHEETS_CREDENTIALS is not set.")
        sheet_id = os.environ.get('GOOGLE_SHEETS_ID')
        if not sheet_id:
            raise ValueError("Environment variable GOOGLE_SHEETS_ID is not set.")
        self.creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
        self.client = gspread.authorize(self.creds)
        self.sheet = self.client.open_by_key(sheet_id).sheet1
        self._initialize_headers()

    def _initialize_headers(self):
        try:
            first_row = self.sheet.row_values(1)
            if not first_row:
                headers = [
                    "Job_Hash_ID", "Company", "Job_Title", "Status",
                    "Match_Score", "Evaluation_Reason", "Pain_Point",
                    "Email_Draft_Body", "PDF_Cloud_Link", "Job_Link",
                    "Applied_To_Email",
                ]
                self.sheet.insert_row(headers, 1)
                print("Initialized Google Sheet with 11-column headers.")
        except Exception as e:
            print(f"Error checking/initializing headers: {e}")

    def job_exists(self, job_hash_id: str) -> bool:
        try:
            col_a_values = self.sheet.col_values(1)
            return job_hash_id in col_a_values
        except Exception as e:
            print(f"Error checking if job exists: {e}")
            return False

    def log_job(
        self,
        job_hash_id: str,
        company: str,
        title: str,
        status: str,
        match_score: str = "",
        evaluation_reason: str = "",
        pain_point: str = "",
        email_draft_body: str = "",
        pdf_cloud_link: str = "",
        job_link: str = "",
        applied_to_email: str = "",
    ) -> None:
        try:
            self.sheet.append_row([
                job_hash_id, company, title, status,
                str(match_score), evaluation_reason, pain_point,
                email_draft_body, pdf_cloud_link, job_link,
                applied_to_email,
            ])
        except Exception as e:
            print(f"Error logging job: {e}")

    def update_status(
        self,
        job_hash_id: str,
        new_status: str,
        applied_to_email: str = "",
    ) -> None:
        try:
            cell = self.sheet.find(job_hash_id, in_column=1)
            if cell:
                self.sheet.update_cell(cell.row, 4, new_status)
                if applied_to_email:
                    self.sheet.update_cell(cell.row, 11, applied_to_email)
            else:
                print(f"[SheetManager] Hash '{job_hash_id}' not found.")
        except Exception as e:
            print(f"Error updating status: {e}")
