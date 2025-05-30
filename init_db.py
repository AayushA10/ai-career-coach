from dotenv import load_dotenv
import os

# Load environment variables before importing app
load_dotenv()

from app import app, db

with app.app_context():
    db.create_all()
    print("✅ Database initialized.")
