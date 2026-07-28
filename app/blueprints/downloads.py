import os
import requests
from datetime import datetime
from flask import Blueprint, Response, stream_with_context, current_app, flash, redirect, url_for
from pymongo import MongoClient
from stream_zip import stream_zip, ZIP_64
from app.services.drive_service import get_drive_service
import google.auth.transport.requests

downloads_bp = Blueprint("downloads", __name__)

def get_db():
    client = MongoClient(current_app.config["MONGO_URI"])
    return client[current_app.config["MONGO_DB_NAME"]]

def get_drive_access_token():
    """Generates a raw access token for direct HTTP streaming from Google Drive."""
    service = get_drive_service()
    if not service:
        return None
    credentials = service._http.credentials
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)
    return credentials.token

def get_file_name(service, file_id):
    """Fetches the original file name from Google Drive."""
    try:
        meta = service.files().get(fileId=file_id, fields="name").execute()
        return meta.get("name", f"{file_id}.jpg")
    except Exception:
        return f"{file_id}.jpg"

@downloads_bp.route("/zip/<special_id>")
def download_zip(special_id):
    special_id_clean = special_id.strip().upper()
    db = get_db()
    
    # 1. Fetch Client and Event Structure
    client = db["clients"].find_one({"special_id": special_id_clean})
    if not client:
        flash("Client not found.", "error")
        return redirect(url_for("admin.admin_dashboard"))

    # 2. Collect all selected files across all events
    selections = list(db["selections"].find({"special_id": special_id_clean}))
    if not selections:
        flash("No photos have been selected yet.", "error")
        return redirect(url_for("admin.admin_dashboard"))

    # Build a map of event_id -> event_name for folder creation
    event_map = {evt["event_id"]: evt["event_name"] for evt in client.get("events", [])}
    
    access_token = get_drive_access_token()
    drive_service = get_drive_service()

    if not access_token:
        flash("Google Drive integration error.", "error")
        return redirect(url_for("admin.admin_dashboard"))

    # 3. Generator function to stream files chunk-by-chunk
    def zip_file_generator():
        # Get the current time to stamp all downloaded files
        current_time = datetime.now() 
        
        for sel in selections:
            event_name = event_map.get(sel["event_id"], "Other")
            file_ids = sel.get("selected_file_ids", [])
            
            for file_id in file_ids:
                file_name = get_file_name(drive_service, file_id)
                zip_path = f"{client['client_name'].replace(' ', '_')}/{event_name}/{file_name}"
                
                # Fetch image from Google Drive via REST API for chunked streaming
                url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
                headers = {"Authorization": f"Bearer {access_token}"}
                
                with requests.get(url, headers=headers, stream=True) as r:
                    if r.status_code == 200:
                        # Yield the file path, the timestamp, file mode, and the byte chunks
                        # UPDATED: Increased chunk_size to 1MB (1048576 bytes) for ultra-fast throughput
                        yield zip_path, current_time, 0o600, ZIP_64, r.iter_content(chunk_size=1048576)
                    else:
                        print(f"Failed to fetch {file_id}: Status {r.status_code}")

    # 4. Stream the response directly to the browser
    filename = f"{client['client_name'].replace(' ', '_')}_Selections.zip"
    
    return Response(
        stream_with_context(stream_zip(zip_file_generator())),
        mimetype="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )