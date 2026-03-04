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


def _find_folder(service, name: str, parent_id: str) -> str | None:
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
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def _find_or_create_folder(service, name: str, parent_id: str) -> str:
    folder_id = _find_folder(service, name, parent_id)
    if folder_id:
        return folder_id
    return _create_folder(service, name, parent_id)


def upload_pdf_to_drive(file_path: str, company_name: str, user_email: str) -> str:
    root_folder_id = os.environ.get("DRIVE_ROOT_FOLDER_ID")
    if not root_folder_id:
        raise ValueError("Environment variable DRIVE_ROOT_FOLDER_ID is not set.")
    service = _get_drive_service()
    month_folder_name = datetime.now().strftime("%Y-%m")
    month_folder_id = _find_or_create_folder(service, month_folder_name, root_folder_id)
    company_folder_id = _find_or_create_folder(service, company_name, month_folder_id)
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
