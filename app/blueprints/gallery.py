from flask import Blueprint, render_template, redirect, url_for, current_app
from pymongo import MongoClient

gallery_bp = Blueprint("gallery", __name__)

def get_db():
    client = MongoClient(current_app.config["MONGO_URI"])
    return client[current_app.config["MONGO_DB_NAME"]]

@gallery_bp.route("/<special_id>")
def client_gallery(special_id):
    special_id_clean = special_id.strip().upper()
    db = get_db()
    client_data = db["clients"].find_one({"special_id": special_id_clean})
    
    if not client_data:
        return render_template("landing.html", error="Client portal not found.")
        
    return render_template("gallery.html", client=client_data)