import os
from flask import Blueprint, current_app, flash, redirect, url_for
from pymongo import MongoClient
from app.services.drive_service import get_drive_service
from googleapiclient.errors import HttpError

downloads_bp = Blueprint("downloads", __name__)

def get_db():
    client = MongoClient(current_app.config["MONGO_URI"])
    return client[current_app.config["MONGO_DB_NAME"]]

def create_drive_folder(service, folder_name, parent_id=None):
    """Creates a folder in Google Drive and returns its ID."""
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    if parent_id:
        file_metadata['parents'] = [parent_id]
        
    folder = service.files().create(body=file_metadata, fields='id, webViewLink').execute()
    return folder

# A callback function for batch requests to catch isolated file errors without crashing the whole process
def batch_callback(request_id, response, exception):
    if exception:
        print(f"Error copying file in batch: {exception}")

@downloads_bp.route("/zip/<special_id>")
def sync_to_drive(special_id):
    """
    CLOUD NATIVE APPROACH:
    Instead of pulling bytes through Render, this instructs Google Drive to clone 
    the selected files into a new structured folder and redirects the Admin to it.
    """
    special_id_clean = special_id.strip().upper()
    db = get_db()
    
    # 1. Fetch Client and Selections
    client = db["clients"].find_one({"special_id": special_id_clean})
    if not client:
        flash("Client not found.", "error")
        return redirect(url_for("admin.admin_dashboard"))

    selections = list(db["selections"].find({"special_id": special_id_clean}))
    if not selections:
        flash("No photos have been selected yet.", "error")
        return redirect(url_for("admin.admin_dashboard"))

    drive_service = get_drive_service()
    if not drive_service:
        flash("Google Drive integration error.", "error")
        return redirect(url_for("admin.admin_dashboard"))

    # 2. Pre-fetch original filenames (bypasses Google's Query length limit)
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
            except HttpError as e:
                print(f"Error fetching names for folder {folder_id}: {e}")
                break

    # 3. Create Root "Final Selections" Folder in Google Drive
    root_folder_name = f"{client['client_name'].replace(' ', '_')} - Final Selections"
    try:
        root_folder = create_drive_folder(drive_service, root_folder_name)
        root_folder_id = root_folder['id']
        root_folder_link = root_folder['webViewLink']
    except Exception as e:
        flash("Failed to create root folder in Google Drive.", "error")
        return redirect(url_for("admin.admin_dashboard"))

    # 4. Create Subfolders and Execute BATCH Copy
    # Batching groups up to 100 copy requests into 1 network call, taking just seconds.
    for sel in selections:
        event_name = event_map.get(sel["event_id"], "Other")
        file_ids = sel.get("selected_file_ids", [])
        
        if not file_ids:
            continue
            
        # Create subfolder for the event (e.g., "Pre Wedding")
        subfolder = create_drive_folder(drive_service, event_name, parent_id=root_folder_id)
        subfolder_id = subfolder['id']
        
        # Setup Google API Batch Request
        batch = drive_service.new_batch_http_request(callback=batch_callback)
        request_count = 0
        
        for file_id in file_ids:
            file_name = file_names_map.get(file_id, f"{file_id}.jpg")
            body = {
                'name': file_name,
                'parents': [subfolder_id]
            }
            
            # Queue the file duplication on Google's servers
            batch.add(drive_service.files().copy(fileId=file_id, body=body, fields='id'))
            request_count += 1
            
            # Google API limits batches to 100 requests max. Execute and reset if we hit 100.
            if request_count % 100 == 0:
                batch.execute()
                batch = drive_service.new_batch_http_request(callback=batch_callback)
        
        # Execute any remaining requests in the final batch
        if request_count % 100 != 0:
            batch.execute()

    # 5. Redirect the Admin straight to the new Google Drive folder!
    flash(f"Success! Google Drive has cloned the files. Opening folder...", "success")
    return redirect(root_folder_link)