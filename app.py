from flask import Flask, render_template, request, send_file, redirect, url_for, session, jsonify
from werkzeug.utils import secure_filename
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from dotenv import load_dotenv
from firebase_admin import auth, firestore
import os
import io
from datetime import datetime

from parser import extract_text
from analyzer import analyze_resume
from firebase_config import init_firebase

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key")

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'docx', 'txt'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 🔥 Firebase Init (Safe)
db = init_firebase()


# ---------------- HELPER FUNCTIONS ---------------- #

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def save_analysis(user_id, filename, score, missing_keywords):
    """Save resume analysis to Firestore"""
    if db is None:
        return

    try:
        db.collection("resume_analysis").add({
            "user_id": user_id,
            "filename": filename,
            "score": score,
            "missing_keywords": missing_keywords,
            "created_at": datetime.utcnow()
        })
    except Exception as e:
        print("❌ Error saving analysis:", e)


def get_firebase_web_config():
    return {
        "apiKey": os.getenv("FIREBASE_API_KEY", ""),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", ""),
        "projectId": os.getenv("FIREBASE_PROJECT_ID", ""),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", ""),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID", ""),
        "appId": os.getenv("FIREBASE_APP_ID", ""),
        "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID", ""),
    }


# ---------------- ROUTES ---------------- #

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    return render_template(
        'index.html',
        user_email=session.get('user_email'),
        user_name=session.get('user_name', 'User')
    )


@app.route('/login')
def login():
    if 'user_id' in session:
        return redirect(url_for('home'))

    return render_template('login.html', firebase_config=get_firebase_web_config())


@app.route('/register')
def register():
    if 'user_id' in session:
        return redirect(url_for('home'))

    return render_template('register.html', firebase_config=get_firebase_web_config())


@app.route('/session-login', methods=['POST'])
def session_login():
    data = request.get_json(silent=True) or {}
    id_token = data.get('idToken')

    if not id_token:
        return jsonify({'success': False, 'message': 'Missing ID token'}), 400

    try:
        decoded_token = auth.verify_id_token(id_token)

        email = decoded_token.get('email', '')
        name = decoded_token.get('name') or email

        session['user_id'] = decoded_token['uid']
        session['user_email'] = email
        session['user_name'] = name

        return jsonify({
            'success': True,
            'user_name': name,
            'user_email': email
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 401


@app.route('/save-user', methods=['POST'])
def save_user():
    if db is None:
        return jsonify({'success': True})  # Skip if Firebase not ready

    data = request.get_json(silent=True) or {}

    uid = data.get('uid')
    name = data.get('name', '')
    email = data.get('email')

    if not uid or not email:
        return jsonify({'success': False, 'message': 'Missing user data'}), 400

    try:
        db.collection('users').document(uid).set({
            'name': name,
            'email': email,
            'created_at': firestore.SERVER_TIMESTAMP
        }, merge=True)

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# 🔥 MAIN ANALYSIS ROUTE
@app.route('/analyze', methods=['POST'])
def analyze():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    file = request.files.get('resume')
    job_description = request.form.get('job_description', '').strip()

    if not file or file.filename == '':
        return render_template('error.html', message='Please upload a resume file.')

    if not allowed_file(file.filename):
        return render_template('error.html', message='Only PDF, DOCX, and TXT files allowed.')

    if not job_description:
        return render_template('error.html', message='Please add job description.')

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    resume_text = extract_text(filepath)

    if not resume_text.strip():
        return render_template('error.html', message='Could not read resume.')

    result = analyze_resume(resume_text, job_description)

    # 🔥 SAVE TO FIREBASE
    save_analysis(
        user_id=session.get('user_id'),
        filename=filename,
        score=result.get("score", 0),
        missing_keywords=result.get("missing_keywords", [])
    )

    return render_template(
        'result.html',
        result=result,
        filename=filename,
        user_email=session.get('user_email'),
        user_name=session.get('user_name', 'User')
    )


# 🔥 DASHBOARD ROUTE
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if db is None:
        return render_template("dashboard.html", history=[])

    try:
        docs = db.collection("resume_analysis") \
            .where("user_id", "==", session['user_id']) \
            .order_by("created_at", direction=firestore.Query.DESCENDING) \
            .stream()

        history = [doc.to_dict() for doc in docs]

    except Exception as e:
        print("Dashboard Error:", e)
        history = []

    return render_template("dashboard.html", history=history)


# ---------------- REPORT ---------------- #

@app.route('/download-report', methods=['POST'])
def download_report():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    filename = request.form.get('filename', 'resume')
    score = request.form.get('score', '0')
    matched_keywords = request.form.get('matched_keywords', '')
    missing_keywords = request.form.get('missing_keywords', '')
    found_skills = request.form.get('found_skills', '')
    suggestions = request.form.get('suggestions', '')
    ai_feedback = request.form.get('ai_feedback', '')

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    x_margin = 50
    y = height - 50
    line_height = 18
    max_width = 95

    def draw_wrapped_text(title, content):
        nonlocal y
        if y < 100:
            pdf.showPage()
            y = height - 50

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(x_margin, y, title)
        y -= line_height

        pdf.setFont("Helvetica", 10)

        if not content:
            pdf.drawString(x_margin, y, "N/A")
            y -= line_height
            return

        if isinstance(content, str):
            lines = content.split("\n")
        else:
            lines = [str(content)]

        for line in lines:
            while len(line) > max_width:
                pdf.drawString(x_margin, y, line[:max_width])
                line = line[max_width:]
                y -= line_height
                if y < 100:
                    pdf.showPage()
                    y = height - 50
                    pdf.setFont("Helvetica", 10)
            pdf.drawString(x_margin, y, line)
            y -= line_height
            if y < 100:
                pdf.showPage()
                y = height - 50
                pdf.setFont("Helvetica", 10)

        y -= 8

    pdf.setTitle("Resume Analysis Report")

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(x_margin, y, "AI Resume Analyzer Report")
    y -= 30

    pdf.setFont("Helvetica", 11)
    pdf.drawString(x_margin, y, f"Resume Name: {filename}")
    y -= line_height
    pdf.drawString(x_margin, y, f"ATS Score: {score}")
    y -= 25

    draw_wrapped_text("Matched Keywords:", matched_keywords.replace(", ", "\n"))
    draw_wrapped_text("Missing Keywords:", missing_keywords.replace(", ", "\n"))
    draw_wrapped_text("Found Skills:", found_skills.replace(", ", "\n"))
    draw_wrapped_text("Suggestions:", suggestions.replace("||", "\n"))
    draw_wrapped_text("AI Feedback:", ai_feedback)

    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="resume_report.pdf",
        mimetype="application/pdf"
    )


@app.errorhandler(413)
def too_large(_error):
    return render_template('error.html', message='File too large (max 5MB)'), 413


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)