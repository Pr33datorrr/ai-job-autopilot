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
        If it is, inserts the exact headers: Job_Hash_ID, Company, Job_Title, Status, Apply_Link.
        """
        try:
            # We look at the first row to determine if headers exist
            first_row = self.sheet.row_values(1)
            if not first_row:
                headers = ["Job_Hash_ID", "Company", "Job_Title", "Status", "Apply_Link"]
                self.sheet.insert_row(headers, 1)
                print("Initialized Google Sheet with headers.")
        except Exception as e:
            print(f"Error checking/initializing headers: {e}")

    def job_exists(self, job_hash_id: str) -> bool:
        """
        Checks if a job hash already exists in column A of the sheet.
        """
        try:
            # Gets all values in column A (1-indexed)
            # col_values(1) returns ['Job Hash (Header)', 'hash1', 'hash2', ...]
            col_a_values = self.sheet.col_values(1)
            return job_hash_id in col_a_values
        except Exception as e:
            print(f"Error checking if job exists: {e}")
            # If there's an error (e.g. rate limit), safely assume we don't have it to potentially retry?
            # actually better to return False or raise, returning False is safest for logging.
            return False

    def log_job(self, job_hash_id: str, company: str, title: str, status: str, link: str) -> None:
        """
        Appends a new row to the sheet.
        """
        try:
            self.sheet.append_row([job_hash_id, company, title, status, link])
        except Exception as e:
            print(f"Error logging job: {e}")
