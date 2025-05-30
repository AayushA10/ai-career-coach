from flask import Flask, render_template, request
import os
import docx2txt
import fitz  # PyMuPDF
import openai
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dotenv import load_dotenv

# ✅ Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Database config
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///submissions.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# DB model
class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    resume_name = db.Column(db.String(120))
    jd_snippet = db.Column(db.Text)
    score = db.Column(db.Float)
    feedback = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# GPT feedback function
def get_gpt_feedback(resume_text, jd_text):
    if not openai.api_key:
        raise ValueError("❌ OPENAI_API_KEY not found in environment variables.")

    prompt = f"""
You're an expert career advisor. Analyze the following resume and job description, and provide specific feedback to the candidate. Suggest:
1. Skills or experiences missing from resume.
2. Sections or keywords to improve.
3. Overall match insight.

Resume:
{resume_text[:1500]}

Job Description:
{jd_text[:1500]}
"""

    # ✅ NEW way to call OpenAI API (Compatible with openai>=1.0.0)
    client = openai.Client()

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300
    )
    return response.choices[0].message.content

# Home route
@app.route('/')
def index():
    return render_template('index.html')

# Analyze route
@app.route('/analyze', methods=['POST'])
def analyze():
    resume_file = request.files['resume']
    jd_text = request.form['jd']

    # Save file
    filename = secure_filename(resume_file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    resume_file.save(path)

    # Extract text
    resume_text = ""
    if filename.endswith('.txt'):
        with open(path, 'r') as file:
            resume_text = file.read()
    elif filename.endswith('.docx'):
        resume_text = docx2txt.process(path)
    elif filename.endswith('.pdf'):
        with fitz.open(path) as doc:
            resume_text = "\n".join([page.get_text() for page in doc])
    else:
        resume_text = "Unsupported file type"

    # Match score
    resume_words = set(resume_text.lower().split())
    jd_words = set(jd_text.lower().split())
    overlap = resume_words.intersection(jd_words)
    match_score = round(len(overlap) / len(jd_words) * 100, 2) if jd_words else 0

    # GPT feedback
    feedback = get_gpt_feedback(resume_text, jd_text)

    # Save to DB
    submission = Submission(
        resume_name=filename,
        jd_snippet=jd_text[:300],
        score=match_score,
        feedback=feedback
    )
    db.session.add(submission)
    db.session.commit()

    return render_template('index.html', score=match_score, feedback=feedback)

# Dashboard route
@app.route('/dashboard')
def dashboard():
    all_submissions = Submission.query.order_by(Submission.timestamp.desc()).all()
    return render_template('dashboard.html', submissions=all_submissions)

if __name__ == '__main__':
    app.run(debug=True)
