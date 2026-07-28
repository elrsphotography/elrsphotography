import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from app import cache
from flask import current_app

def get_drive_service():
    """Initializes and returns the Google Drive API service."""
    creds_file = current_app.config.get("SERVICE_ACCOUNT_FILE", "credentials.json")
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    
    env_json = current_app.config.get("SERVICE_ACCOUNT_JSON_ENV")
    
    try:
        if env_json:
            creds_dict = json.loads(env_json)
            credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)
        elif os.path.exists(creds_file):
            credentials = service_account.Credentials.from_service_account_file(creds_file, scopes=scopes)
        else:
            return None
        return build("drive", "v3", credentials=credentials, cache_discovery=False)
    except Exception as e:
        print(f"Drive Auth Error: {e}")
        return None

@cache.memoize(timeout=1800)
def fetch_paginated_images(folder_id, page_token=None):
    """Fetches images and uses Google's high-speed CDN for thumbnails."""
    service = get_drive_service()
    if not service:
        return {"images": [], "next_page_token": None, "error": "Drive service unavailable"}

    try:
        query = f"'{folder_id}' in parents and mimeType contains 'image/' and trashed = false"
        # UPDATED: Request 'thumbnailLink' directly from the API
        results = service.files().list(
            q=query, 
            pageSize=50, 
            pageToken=page_token,
            fields="nextPageToken, files(id, name, thumbnailLink)",
            orderBy="name"
        ).execute()

        files = results.get("files", [])
        next_page_token = results.get("nextPageToken")

        images = []
        for f in files:
            # Extract CDN link. Default is 220px (=s220). We replace it with 800px (=s800) for high quality.
            fast_thumbnail = f.get("thumbnailLink", "").replace("=s220", "=s800")
            
            # Fallback just in case the CDN link isn't generated yet
            if not fast_thumbnail:
                fast_thumbnail = f"https://drive.google.com/uc?id={f['id']}"

            images.append({
                "id": f["id"],
                "name": f["name"],
                "thumbnail": fast_thumbnail,
                "full": f"https://drive.google.com/uc?export=view&id={f['id']}"
            })

        return {"images": images, "next_page_token": next_page_token}
    except Exception as e:
        print(f"Drive API Error: {e}")
        return {"images": [], "next_page_token": None, "error": str(e)}