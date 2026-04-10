import os
import re
import pdfplumber
from docx import Document


def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.pdf':
        text = extract_pdf_text(file_path)
    elif ext == '.docx':
        text = extract_docx_text(file_path)
    elif ext == '.txt':
        text = extract_txt_text(file_path)
    else:
        return ''

    text = text.replace('\x00', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()



def extract_pdf_text(file_path: str) -> str:
    text_parts = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ''
                if page_text.strip():
                    text_parts.append(page_text)
    except Exception:
        return ''
    return '\n'.join(text_parts)



def extract_docx_text(file_path: str) -> str:
    try:
        doc = Document(file_path)
        return '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:
        return ''



def extract_txt_text(file_path: str) -> str:
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            return file.read()
    except Exception:
        return ''
