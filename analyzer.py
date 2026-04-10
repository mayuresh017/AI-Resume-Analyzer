import json
import os
import re
from collections import Counter

import requests
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

load_dotenv()

OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'openai/gpt-4o-mini')

COMMON_SKILLS = [
    'python', 'sql', 'excel', 'power bi', 'tableau', 'machine learning',
    'data analysis', 'html', 'css', 'javascript', 'flask', 'django',
    'java', 'c++', 'communication', 'teamwork', 'problem solving',
    'git', 'github', 'mongodb', 'mysql', 'pandas', 'numpy', 'react',
    'fastapi', 'api', 'rest', 'data visualization', 'deep learning',
    'statistics', 'oracle', 'firebase', 'node.js', 'bootstrap'
]

ACTION_VERBS = [
    'developed', 'built', 'created', 'implemented', 'analyzed', 'improved',
    'designed', 'led', 'optimized', 'managed', 'delivered', 'automated',
    'engineered', 'launched', 'streamlined'
]

SECTION_KEYWORDS = {
    'Summary': ['summary', 'profile', 'objective', 'professional summary'],
    'Skills': ['skills', 'technical skills', 'core competencies'],
    'Education': ['education', 'academic'],
    'Experience': ['experience', 'work experience', 'employment', 'internship'],
    'Projects': ['projects', 'project'],
    'Certifications': ['certifications', 'certificates', 'licenses']
}


def clean_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9+#./ -]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()



def tokenize(text: str) -> list[str]:
    return re.findall(r'\b[a-zA-Z][a-zA-Z0-9+#./-]*\b', text.lower())



def extract_top_keywords(text: str, limit: int = 20) -> list[str]:
    stopwords = {
        'the', 'and', 'for', 'with', 'you', 'your', 'are', 'this', 'that', 'will', 'from',
        'have', 'has', 'our', 'their', 'who', 'what', 'when', 'where', 'how', 'job', 'role',
        'resume', 'candidate', 'work', 'years', 'year', 'using', 'ability', 'strong', 'team',
        'experience', 'skills', 'knowledge', 'preferred', 'required', 'including', 'plus'
    }
    words = [word for word in tokenize(text) if len(word) > 2 and word not in stopwords]
    counts = Counter(words)
    return [word for word, _ in counts.most_common(limit)]



def find_sections(text: str) -> dict:
    lowered = text.lower()
    found = {}
    for section, options in SECTION_KEYWORDS.items():
        found[section] = any(option in lowered for option in options)
    return found



def find_skills(text: str) -> list[str]:
    lowered = text.lower()
    return sorted([skill for skill in COMMON_SKILLS if skill in lowered])



def similarity_score(resume_text: str, jd_text: str) -> float:
    if not resume_text.strip() or not jd_text.strip():
        return 0.0
    vectorizer = TfidfVectorizer(stop_words='english')
    vectors = vectorizer.fit_transform([resume_text, jd_text])
    return float(cosine_similarity(vectors[0], vectors[1])[0][0])



def score_label(score: float) -> str:
    if score >= 85:
        return 'Excellent match'
    if score >= 70:
        return 'Good match'
    if score >= 55:
        return 'Average match'
    return 'Needs improvement'



def get_ai_feedback(resume_text: str, job_description: str) -> str:
    if not OPENROUTER_API_KEY:
        return 'OpenRouter feedback is disabled. Add OPENROUTER_API_KEY in your environment variables or .env file to enable AI suggestions.'

    prompt = f"""
You are an expert ATS resume coach.
Review the resume against the job description and write concise, practical feedback.

Resume:
{resume_text[:3000]}

Job Description:
{job_description[:2000]}

Return plain text with these headings:
1. Strengths
2. Gaps
3. ATS Tips
4. Better Summary Suggestion
""".strip()

    try:
        response = requests.post(
            url='https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json',
            },
            data=json.dumps({
                'model': OPENROUTER_MODEL,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ]
            }),
            timeout=60
        )
        data = response.json()
        return data['choices'][0]['message']['content'].strip()
    except Exception as exc:
        return f'AI feedback unavailable right now: {exc}'



def analyze_resume(resume_text: str, job_description: str) -> dict:
    resume_clean = clean_text(resume_text)
    jd_clean = clean_text(job_description)

    jd_keywords = extract_top_keywords(jd_clean, 25)
    resume_words = set(tokenize(resume_clean))

    matched_keywords = [word for word in jd_keywords if word in resume_words]
    missing_keywords = [word for word in jd_keywords if word not in resume_words]

    sections = find_sections(resume_text)
    found_skills = find_skills(resume_text)
    action_verbs_found = sorted({verb for verb in ACTION_VERBS if verb in resume_clean})

    similarity = similarity_score(resume_clean, jd_clean) if jd_clean else 0.0
    keyword_match_ratio = len(matched_keywords) / len(jd_keywords) if jd_keywords else 0.0
    section_ratio = sum(sections.values()) / len(sections)
    verb_ratio = min(len(action_verbs_found) / 4, 1.0)

    score = round((similarity * 40 + keyword_match_ratio * 35 + section_ratio * 15 + verb_ratio * 10), 2)
    matched_percent = round(keyword_match_ratio * 100)

    strengths = []
    if found_skills:
        strengths.append('Relevant skills are present in the resume.')
    if action_verbs_found:
        strengths.append('Bullet points include action-oriented language.')
    if sum(sections.values()) >= 4:
        strengths.append('Resume structure is ATS-friendly with key sections included.')
    if similarity >= 0.45:
        strengths.append('Resume content aligns reasonably well with the job description.')

    suggestions = []
    if missing_keywords:
        suggestions.append('Add missing job-description keywords naturally in your skills, projects, and experience sections.')
    if not sections['Summary']:
        suggestions.append('Add a short professional summary at the top of the resume.')
    if not sections['Skills']:
        suggestions.append('Add a dedicated skills section for better ATS readability.')
    if not sections['Certifications']:
        suggestions.append('Add certifications only if they are relevant to the target job.')
    if not any(char.isdigit() for char in resume_text):
        suggestions.append('Add measurable achievements using numbers, percentages, or impact.')
    if not action_verbs_found:
        suggestions.append('Start bullet points with action verbs like Developed, Built, Designed, or Implemented.')
    if score >= 85:
        suggestions.append('Strong ATS alignment. Focus on polishing formatting and tailoring for each job.')
    elif score >= 70:
        suggestions.append('Good resume match. Improve missing keywords and quantified achievements.')
    else:
        suggestions.append('The resume needs more tailoring to the job description for a stronger ATS score.')

    ai_feedback = get_ai_feedback(resume_text, job_description)

    return {
        'score': score,
        'score_label': score_label(score),
        'matched_percent': matched_percent,
        'matched_keywords': matched_keywords[:15],
        'missing_keywords': missing_keywords[:15],
        'sections': sections,
        'found_skills': found_skills[:18],
        'action_verbs': action_verbs_found[:10],
        'suggestions': suggestions[:6],
        'strengths': strengths[:4],
        'ai_feedback': ai_feedback,
    }
