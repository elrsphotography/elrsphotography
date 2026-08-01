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

def get_drive_access_token(service):
    """Generates a raw access token for direct HTTP streaming from Google Drive."""
    if not service:
        return None
    credentials = service._http.credentials
    request = google.auth.transport.requests.Request()
    credentials.refresh(request)
    return credentials.token

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

    drive_service = get_drive_service()
    access_token = get_drive_access_token(drive_service)

    if not access_token:
        flash("Google Drive integration error.", "error")
        return redirect(url_for("admin.admin_dashboard"))

    # 3. OPTIMIZATION: Pre-fetch all file names by folder to prevent 5000+ individual API calls
    file_names_map = {}
    event_map = {}
    
    for event in client.get("events", []):
        event_id = event["event_id"]
        event_map[event_id] = event["event_name"]
        folder_id = event.get("folder_id")
        
        if not folder_id:
            continue
            
        page_token = None
        while True:
            try:
                results = drive_service.files().list(
                    q=f"'{folder_id}' in parents and trashed = false",
                    fields="nextPageToken, files(id, name)",
                    pageSize=1000,
                    pageToken=page_token
                ).execute()
                
                for f in results.get('files', []):
                    file_names_map[f['id']] = f['name']
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            except Exception as e:
                print(f"Error fetching names for folder {folder_id}: {e}")
                break

    # 4. Generator function to stream files chunk-by-chunk
    def zip_file_generator():
        current_time = datetime.now() 
        
        for sel in selections:
            event_name = event_map.get(sel["event_id"], "Other")
            file_ids = sel.get("selected_file_ids", [])
            
            for file_id in file_ids:
                # INSTANT LOOKUP: No API call needed here anymore!
                file_name = file_names_map.get(file_id, f"{file_id}.jpg")
                zip_path = f"{client['client_name'].replace(' ', '_')}/{event_name}/{file_name}"
                
                url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
                headers = {"Authorization": f"Bearer {access_token}"}
                
                with requests.get(url, headers=headers, stream=True) as r:
                    if r.status_code == 200:
                        yield zip_path, current_time, 0o600, ZIP_64, r.iter_content(chunk_size=1048576)
                    else:
                        print(f"Failed to fetch {file_id}: Status {r.status_code}")

    # 5. Stream the response directly to the browser
    filename = f"{client['client_name'].replace(' ', '_')}_Selections.zip"
    
    return Response(
        stream_with_context(stream_zip(zip_file_generator())),
        mimetype="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )