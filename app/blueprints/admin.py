import os
import json
import re
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session
from pymongo import MongoClient
from bson.objectid import ObjectId
from app.blueprints.auth import login_required

admin_bp = Blueprint("admin", __name__)

# --- HELPERS ---

def get_db():
    client = MongoClient(current_app.config["MONGO_URI"])
    return client[current_app.config["MONGO_DB_NAME"]]

def get_service_account_email():
    """Extracts client_email from credentials.json or Environment variable."""
    env_json = current_app.config.get("SERVICE_ACCOUNT_JSON_ENV")
    if env_json:
        try:
            return json.loads(env_json).get("client_email", "Email not found in ENV")
        except Exception:
            pass

    creds_file = current_app.config.get("SERVICE_ACCOUNT_FILE", "credentials.json")
    if os.path.exists(creds_file):
        try:
            with open(creds_file, "r") as f:
                return json.load(f).get("client_email", "Email not found in credentials.json")
        except Exception:
            pass
            
    return "credentials.json not configured"

def extract_folder_id(url_or_id):
    """Extracts raw Google Drive Folder ID from standard share links or raw strings."""
    if not url_or_id:
        return ""
    url_or_id = url_or_id.strip()
    folder_match = re.search(r"folders/([a-zA-Z0-9_-]+)", url_or_id)
    if folder_match:
        return folder_match.group(1)
    param_match = re.search(r"id=([a-zA-Z0-9_-]+)", url_or_id)
    if param_match:
        return param_match.group(1)
    return url_or_id

# --- ROUTES ---

@admin_bp.route("/")
@login_required
def admin_dashboard():
    db = get_db()
    clients_col = db["clients"]
    selections_col = db["selections"]

    # Fetch all clients
    clients = list(clients_col.find())
    
    # Calculate stats
    total_clients = len(clients)
    total_events = sum(len(c.get("events", [])) for c in clients)
    
    # Map selection counts to clients and events
    selections_raw = list(selections_col.find())
    selection_map = {}
    total_selected_images = 0

    for sel in selections_raw:
        key = f"{sel.get('special_id')}_{sel.get('event_id')}"
        count = len(sel.get("selected_file_ids", []))
        selection_map[key] = count
        total_selected_images += count

    # Attach selection counts dynamically
    for client in clients:
        c_special_id = client.get("special_id")
        client["total_selections"] = 0
        for event in client.get("events", []):
            event_key = f"{c_special_id}_{event.get('event_id')}"
            event["selection_count"] = selection_map.get(event_key, 0)
            client["total_selections"] += event["selection_count"]

    service_email = get_service_account_email()

    return render_template(
        "admin.html",
        clients=clients,
        total_clients=total_clients,
        total_events=total_events,
        total_selected_images=total_selected_images,
        service_email=service_email,
        username=session.get("username", "Admin")
    )


@admin_bp.route("/client/add", methods=["POST"])
@login_required
def add_client():
    special_id = request.form.get("special_id", "").strip().upper()
    client_name = request.form.get("client_name", "").strip()
    email = request.form.get("email", "").strip()

    if not special_id or not client_name:
        flash("Special ID and Client Name are required.", "error")
        return redirect(url_for("admin.admin_dashboard"))
        
    # NEW: Prevent URLs, spaces, or special characters in the ID
    if not special_id.isalnum():
        flash("Special ID must contain ONLY letters and numbers (no spaces, links, or symbols).", "error")
        return redirect(url_for("admin.admin_dashboard"))

    db = get_db()
    clients_col = db["clients"]

    # Prevent duplicate Special IDs
    if clients_col.find_one({"special_id": special_id}):
        flash(f"Special ID '{special_id}' already exists!", "error")
        return redirect(url_for("admin.admin_dashboard"))

    new_client = {
        "special_id": special_id,
        "client_name": client_name,
        "email": email,
        "events": []
    }
    clients_col.insert_one(new_client)
    flash(f"Client '{client_name}' ({special_id}) created successfully!", "success")
    return redirect(url_for("admin.admin_dashboard"))

@admin_bp.route("/client/delete/<path:special_id>", methods=["POST"])
@login_required
def delete_client(special_id):
    db = get_db()
    db["clients"].delete_one({"special_id": special_id})
    db["selections"].delete_many({"special_id": special_id})
    flash(f"Client and associated selections removed.", "success")
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/event/add", methods=["POST"])
@login_required
def add_event():
    special_id = request.form.get("special_id", "").strip().upper()
    event_name = request.form.get("event_name", "").strip()
    drive_url = request.form.get("drive_url", "").strip()

    folder_id = extract_folder_id(drive_url)

    if not event_name or not folder_id:
        flash("Event name and valid Drive Link/Folder ID are required.", "error")
        return redirect(url_for("admin.admin_dashboard"))

    db = get_db()
    clients_col = db["clients"]

    event_id = f"evt_{uuid.uuid4().hex[:8]}"
    new_event = {
        "event_id": event_id,
        "event_name": event_name,
        "folder_id": folder_id
    }

    clients_col.update_one(
        {"special_id": special_id},
        {"$push": {"events": new_event}}
    )

    flash(f"Event '{event_name}' added to client {special_id}.", "success")
    return redirect(url_for("admin.admin_dashboard"))


@admin_bp.route("/event/delete/<special_id>/<event_id>", methods=["POST"])
@login_required
def delete_event(special_id, event_id):
    db = get_db()
    db["clients"].update_one(
        {"special_id": special_id},
        {"$pull": {"events": {"event_id": event_id}}}
    )
    db["selections"].delete_one({"special_id": special_id, "event_id": event_id})
    flash("Event removed successfully.", "success")
    return redirect(url_for("admin.admin_dashboard"))