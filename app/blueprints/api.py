from flask import Blueprint, request, jsonify, current_app
from pymongo import MongoClient
from app.services.drive_service import fetch_paginated_images, get_drive_service

api_bp = Blueprint("api", __name__)

def get_db():
    client = MongoClient(current_app.config["MONGO_URI"])
    return client[current_app.config["MONGO_DB_NAME"]]

@api_bp.route("/images/<folder_id>", methods=["GET"])
def get_images(folder_id):
    """Endpoint for the Intersection Observer to fetch the next 50 images."""
    page_token = request.args.get("pageToken")
    data = fetch_paginated_images(folder_id, page_token)
    return jsonify(data)

@api_bp.route("/selections/<special_id>/<event_id>", methods=["GET"])
def get_selections(special_id, event_id):
    """Retrieves already selected image IDs so they persist when returning."""
    db = get_db()
    selection_doc = db["selections"].find_one({"special_id": special_id, "event_id": event_id})
    selected_ids = selection_doc.get("selected_file_ids", []) if selection_doc else []
    return jsonify({"selected_ids": selected_ids})

@api_bp.route("/selections/save", methods=["POST"])
def save_selections():
    """Saves the array of selected image IDs to MongoDB."""
    data = request.get_json()
    special_id = data.get("special_id")
    event_id = data.get("event_id")
    selected_ids = data.get("selected_ids", [])

    if not special_id or not event_id:
        return jsonify({"status": "error", "message": "Missing identifiers"}), 400

    db = get_db()
    db["selections"].update_one(
        {"special_id": special_id, "event_id": event_id},
        {"$set": {"selected_file_ids": selected_ids}},
        upsert=True
    )
    return jsonify({"status": "success", "message": "Selections saved securely."})

@api_bp.route("/selections/complete", methods=["POST"])
def complete_client_selection():
    """Marks the entire client portfolio as fully selected."""
    data = request.get_json()
    special_id = data.get("special_id")

    if not special_id:
        return jsonify({"status": "error", "message": "Missing ID"}), 400

    db = get_db()
    db["clients"].update_one(
        {"special_id": special_id},
        {"$set": {"selection_status": "COMPLETED"}}
    )
    return jsonify({"status": "success", "message": "Admin notified."})

# ==========================================
# NEW ROUTES FOR GALLERY & REVIEW PAGE
# ==========================================

@api_bp.route("/selections/all/<special_id>", methods=["GET"])
def get_all_selections(special_id):
    """Returns the selections for all events under a client at once."""
    db = get_db()
    selections = {}
    records = db["selections"].find({"special_id": special_id.strip().upper()})
    for record in records:
        # Matches your DB schema: selected_file_ids
        selections[record["event_id"]] = record.get("selected_file_ids", [])
    return jsonify({"selections": selections})

@api_bp.route("/selections/details/<special_id>", methods=["GET"])
def get_selection_details(special_id):
    """
    Optimized: Fetches the actual image metadata for EVERY selected file from Google Drive in BULK.
    Prevents 502 Gateway Timeouts by grouping requests into chunks of 40.
    """
    db = get_db()
    client_data = db["clients"].find_one({"special_id": special_id.strip().upper()})
    if not client_data:
        return jsonify({"error": "Client not found"}), 404

    drive_service = get_drive_service()
    events_data = []
    
    for event in client_data.get("events", []):
        event_id = event["event_id"]
        selection_record = db["selections"].find_one({"special_id": special_id, "event_id": event_id})
        selected_ids = selection_record.get("selected_file_ids", []) if selection_record else []
        
        if not selected_ids:
            continue
            
        event_images = []
        
        # CHUNKING LOGIC: Group IDs into batches of 40 to avoid URI length limits and 502 Timeouts
        chunk_size = 40
        for i in range(0, len(selected_ids), chunk_size):
            chunk = selected_ids[i:i + chunk_size]
            
            # Construct a bulk search query for Google Drive: id='123' or id='456'
            query_parts = [f"id='{file_id}'" for file_id in chunk]
            query_string = " or ".join(query_parts)
            
            try:
                # Fetch up to 40 files in a SINGLE request
                results = drive_service.files().list(
                    q=query_string,
                    fields="files(id, name, webContentLink, thumbnailLink)",
                    pageSize=100
                ).execute()
                
                files = results.get('files', [])
                for file in files:
                    event_images.append({
                        "id": file.get("id"),
                        "name": file.get("name"),
                        "thumbnail": file.get("thumbnailLink", "").replace("s220", "s800") if file.get("thumbnailLink") else "",
                        "full": file.get("webContentLink", "")
                    })
            except Exception as e:
                print(f"Failed to fetch chunk in event {event_id}: {e}")

        events_data.append({
            "event_id": event_id,
            "event_name": event["event_name"],
            "images": event_images
        })

    return jsonify({"events": events_data})