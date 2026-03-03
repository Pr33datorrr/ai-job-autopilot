import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

class SheetManager:
    """
    Manager class for interacting with Google Sheets database.
    Authenticates using a Service Account JSON file.
    """
    def __init__(self):
        # Define the scope of access
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Load credentials path
        creds_path = os.environ.get('GOOGLE_SHEETS_CREDENTIALS')
        if not creds_path:
            raise ValueError("Environment variable GOOGLE_SHEETS_CREDENTIALS is not set.")
        
        # Load Google Sheet ID
        sheet_id = os.environ.get('GOOGLE_SHEETS_ID')
        if not sheet_id:
            raise ValueError("Environment variable GOOGLE_SHEETS_ID is not set.")
            
        # Authenticate with Google
        self.creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
        self.client = gspread.authorize(self.creds)
        
        # Open the specific Google Sheet by ID
        # Assumes the first worksheet (index 0) is the target
        self.sheet = self.client.open_by_key(sheet_id).sheet1
        
        # Initialize headers if sheet is empty
        self._initialize_headers()

    def _initialize_headers(self):
        """
        Checks if the first row is empty. 
        If it is, inserts the exact headers.
        """
        try:
            first_row = self.sheet.row_values(1)
            if not first_row:
                headers = [
                    "Job_Hash_ID", "Company", "Job_Title", "Status",
                    "Match_Score", "Pain_Point", "Email_Draft_Body",
                    "PDF_Cloud_Link", "Job_Link",
                ]
                self.sheet.insert_row(headers, 1)
                print("Initialized Google Sheet with headers.")
        except Exception as e:
            print(f"Error checking/initializing headers: {e}")

    def job_exists(self, job_hash_id: str) -> bool:
        """
        Checks if a job hash already exists in column A of the sheet.
        """
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
        pain_point: str = "",
        email_draft_body: str = "",
        pdf_cloud_link: str = "",
        job_link: str = "",
    ) -> None:
        """
        Appends a new row to the sheet.

        Column order:
        Job_Hash_ID | Company | Job_Title | Status | Match_Score |
        Pain_Point | Email_Draft_Body | PDF_Cloud_Link | Job_Link
        """
        try:
            self.sheet.append_row([
                job_hash_id, company, title, status,
                str(match_score), pain_point, email_draft_body,
                pdf_cloud_link, job_link,
            ])
        except Exception as e:
            print(f"Error logging job: {e}")

    def update_status(self, job_hash_id: str, new_status: str) -> None:
        """
        Find the row whose column A matches *job_hash_id* and update
        its Status cell (column D) to *new_status*.
        """
        try:
            cell = self.sheet.find(job_hash_id, in_column=1)
            if cell:
                self.sheet.update_cell(cell.row, 4, new_status)
            else:
                print(f"[SheetManager] Hash '{job_hash_id}' not found.")
        except Exception as e:
            print(f"Error updating status: {e}")
