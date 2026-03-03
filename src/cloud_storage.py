import os
import io
import re
from datetime import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload


_SCOPES = ["https://www.googleapis.com/auth/drive.file"]
_TOKEN_PATH = os.path.join(os.path.dirname(__file__), "..", "req_files", "token.json")


def _get_drive_service():
    """Authenticate with Drive API v3 using the user's OAuth token."""
    if not os.path.exists(_TOKEN_PATH):
        raise FileNotFoundError(
            f"{_TOKEN_PATH} not found. Run 'python tools/oauth_setup.py' first."
        )

    creds = Credentials.from_authorized_user_file(_TOKEN_PATH, _SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(_TOKEN_PATH, "w") as f:
            f.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _find_folder(service, name: str, parent_id: str) -> str | None:
    """Return the ID of a folder named *name* under *parent_id*, or None."""
    query = (
        f"name = '{name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false "
        f"and '{parent_id}' in parents"
    )
    results = service.files().list(
        q=query, spaces="drive", fields="files(id)", pageSize=1,
    ).execute()
    files = results.get("files", [])
    return files[0]["id"] if files else None


def _create_folder(service, name: str, parent_id: str) -> str:
    """Create a folder under *parent_id* and return its ID."""
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def _find_or_create_folder(service, name: str, parent_id: str) -> str:
    """Find an existing folder or create one. Returns folder ID."""
    folder_id = _find_folder(service, name, parent_id)
    if folder_id:
        return folder_id
    return _create_folder(service, name, parent_id)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def upload_pdf_to_drive(
    file_path: str,
    company_name: str,
    user_email: str,
) -> str:
    """
    Upload a PDF to Google Drive with dynamic folder routing.

    Authenticates as the user via OAuth refresh token.
    Files are owned by the user -- no permissions patch needed.

    Requires DRIVE_ROOT_FOLDER_ID env var.

    Folder structure:  <root> / YYYY-MM / company_name /
    Returns:           webViewLink (str) of the uploaded file.
    """
    root_folder_id = os.environ.get("DRIVE_ROOT_FOLDER_ID")
    if not root_folder_id:
        raise ValueError(
            "Environment variable DRIVE_ROOT_FOLDER_ID is not set. "
            "Create a folder in Google Drive and set this env var to its ID."
        )

    service = _get_drive_service()

    # -- Dynamic Routing: root / YYYY-MM / company_name / --
    month_folder_name = datetime.now().strftime("%Y-%m")
    month_folder_id = _find_or_create_folder(service, month_folder_name, root_folder_id)
    company_folder_id = _find_or_create_folder(service, company_name, month_folder_id)

    # -- Upload PDF --
    file_name = os.path.basename(file_path)
    media = MediaFileUpload(file_path, mimetype="application/pdf", resumable=True)

    uploaded = service.files().create(
        body={"name": file_name, "parents": [company_folder_id]},
        media_body=media,
        fields="id, webViewLink",
    ).execute()

    web_link = uploaded["webViewLink"]

    print(f"   [Drive] Uploaded '{file_name}' -> {month_folder_name}/{company_name}/")

    return web_link


def download_pdf_from_drive(web_view_link: str, output_path: str) -> str:
    """
    Download a PDF from Google Drive using its webViewLink.

    Extracts the file_id from the link (the segment between /d/ and /view),
    downloads the file via the Drive API, and saves it to *output_path*.

    Returns the output_path on success.
    """
    # Extract file ID from URL like:
    # https://drive.google.com/file/d/1jHbeb.../view?usp=drivesdk
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", web_view_link)
    if not match:
        raise ValueError(f"Could not extract file_id from link: {web_view_link}")

    file_id = match.group(1)
    service = _get_drive_service()

    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(buffer.getvalue())

    return output_path
