from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from pymongo import MongoClient

auth_bp = Blueprint("auth", __name__)

# --- DATABASE CONNECTION HELPER ---
def get_users_collection():
    client = MongoClient(current_app.config["MONGO_URI"])
    db = client[current_app.config["MONGO_DB_NAME"]]
    return db["users"]

# --- AUTHENTICATION DECORATOR ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access the admin dashboard.", "error")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function

# --- ROUTES ---

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password")

        users_col = get_users_collection()
        user = users_col.find_one({"username": username})

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = str(user["_id"])
            session["username"] = user["username"]
            session["role"] = user.get("role", "admin")
            return redirect(url_for("admin.admin_dashboard"))
        else:
            flash("Invalid username or password.", "error")

    # Both GET requests and failed login POSTs render this single page
    return render_template("login.html")


@auth_bp.route("/register", methods=["POST"])
def register():
    # Only processes the form submission from the toggle UI
    username = request.form.get("username").strip()
    password = request.form.get("password")
    secret_key = request.form.get("secret_key")

    if secret_key != "ELRS2019@co":
        flash("Invalid registration key. Access denied.", "error")
        return redirect(url_for("auth.login"))

    users_col = get_users_collection()
    
    if users_col.find_one({"username": username}):
        flash("Username already exists. Please choose another.", "error")
        return redirect(url_for("auth.login"))

    new_user = {
        "username": username,
        "password_hash": generate_password_hash(password),
        "role": "admin"
    }
    users_col.insert_one(new_user)
    
    flash("Admin account created successfully! You can now log in.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been securely logged out.", "success")
    return redirect(url_for("auth.login"))