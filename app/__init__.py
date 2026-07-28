import os
from flask import Flask
from flask_caching import Cache
from pymongo import MongoClient
from app.config import config_by_name

cache = Cache()
mongo_client = None
db = None

def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "dev")

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Initialize Extensions
    cache.init_app(app)

    # Initialize MongoDB Connection
    global mongo_client, db
    mongo_client = MongoClient(app.config["MONGO_URI"])
    db = mongo_client[app.config["MONGO_DB_NAME"]]

    # Register Blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.gallery import gallery_bp
    from app.blueprints.api import api_bp
    from app.blueprints.downloads import downloads_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(gallery_bp, url_prefix="/gallery")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(downloads_bp, url_prefix="/downloads")

    # Base Root Handler
    @app.route("/")
    def index():
        from flask import render_template
        return render_template("landing.html")

    return app