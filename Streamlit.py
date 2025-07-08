import os
import re
import streamlit as st
import tempfile
import json
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
import google.generativeai as genai
import markdown2
from bs4 import BeautifulSoup

# ---- Professional App Configuration and Custom Styling ----
st.set_page_config(
    page_title="Universal Multilingual Audio Report Generator",
    layout="wide",
    page_icon="🎙️",
)
st.markdown("""
    <style>
        .main-title {font-size:2.6rem;font-weight:700;color:#1a237e;margin-bottom:0.15em;}
        .subtitle {font-size:1.2rem;color:#3949ab;margin-bottom:2.5em;}
        .stButton>button {background-color:#3949ab;color:white;font-weight:bold;border-radius:8px;}
        .stDownloadButton>button {background-color:#43a047;color:white;font-weight:bold;border-radius:8px;}
        .stSpinner {font-size:1.1rem;}
        .css-1v0mbdj {padding-top:1.2rem;}
    </style>
""", unsafe_allow_html=True)
st.markdown('<div class="main-title">🎙️ Universal Multilingual Audio Report Generator</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Transcribe, translate, and generate professional reports from audio in any language</div>', unsafe_allow_html=True)

# ---- Gemini API Key ----
if "gemini" in st.secrets and "api_key" in st.secrets["gemini"]:
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
else:
    st.error("Gemini API key not found. Please add [gemini] api_key to your .streamlit/secrets.toml.")
    st.stop()

# ---- Google Credentials (Optional) ----
def set_google_credentials_from_secrets():
    try:
        credentials_dict = dict(st.secrets["google"])
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w") as tmp_file:
            json.dump(credentials_dict, tmp_file)
            tmp_file_path = tmp_file.name
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp_file_path
        st.session_state.credentials_path = tmp_file_path
        return True
    except Exception as e:
        st.error(f"Error loading credentials from Secrets: {e}")
        return False

if "credentials_set" not in st.session_state:
    st.session_state.credentials_set = set_google_credentials_from_secrets()

def cleanup():
    if "credentials_path" in st.session_state:
        try:
            os.unlink(st.session_state.credentials_path)
        except Exception:
            pass

import atexit
atexit.register(cleanup)

def get_mimetype(ext):
    ext = ext.lower()
    if ext == ".mp3":
        return "audio/mp3"
    elif ext == ".ogg":
        return "audio/ogg"
    elif ext == ".flac":
        return "audio/flac"
    elif ext == ".m4a" or ext == ".mp4":
        return "audio/mp4"
    else:
        return "audio/wav"

# ---- Language Selection ----
LANG_OPTIONS = [
    "Auto-detect",
    "English", "Hindi", "Malayalam", "Tamil", "Telugu", "Gujarati", "Bengali", "Marathi", "Punjabi", "Kannada", "Odia",
    "French", "Spanish", "German", "Russian", "Chinese", "Japanese", "Arabic", "Portuguese", "Italian", "Korean", "Other"
]
LANG_TO_CODE = {
    "Auto-detect": "",
    "English": "en", "Hindi": "hi", "Malayalam": "ml", "Tamil": "ta", "Telugu": "te", "Gujarati": "gu", "Bengali": "bn",
    "Marathi": "mr", "Punjabi": "pa", "Kannada": "kn", "Odia": "or",
    "French": "fr", "Spanish": "es", "German": "de", "Russian": "ru", "Chinese": "zh", "Japanese": "ja",
    "Arabic": "ar", "Portuguese": "pt", "Italian": "it", "Korean": "ko"
}

with st.form(key="language_form"):
    col1, col2 = st.columns(2)
    with col1:
        input_lang = st.selectbox("Select Input (Audio) Language", LANG_OPTIONS, index=0, help="Choose 'Auto-detect' if unsure")
    with col2:
        output_lang = st.selectbox("Select Output (Report) Language", LANG_OPTIONS, index=1, help="Select the language for the generated report")
    submitted = st.form_submit_button("Apply Language Settings")

# ---- Gemini Prompts ----
def universal_gemini_prompt(transcript_text, output_lang, input_lang):
    # Compose output language instruction
    output_lang_code = LANG_TO_CODE.get(output_lang, "")
    output_lang_instruction = ""
    if output_lang_code and output_lang != "Auto-detect":
        output_lang_instruction = f"Write the report entirely in {output_lang}."
    else:
        output_lang_instruction = "Write the report in the same language as the transcript."
    # Compose input language instruction for model context if available
    input_lang_instruction = ""
    if input_lang != "Auto-detect":
        input_lang_instruction = f"The following transcript is in {input_lang}. "
    # Final prompt
    return f"""
{input_lang_instruction}
Analyze the following audio transcript and generate a professional, detailed report.
- Structure and headings of the report should be based on the content and context of the audio.
- {output_lang_instruction}
- Use appropriate professional tone, sections, and formatting.
- If the audio is about a meeting, event, or discussion, include sections such as Summary, Key Points, Issues Raised, Recommendations, etc., as relevant.
- If any section lacks sufficient information, generate plausible, professional content based on general knowledge relevant to the subject.
- DO NOT output placeholders like [Insert ... here], "---", or similar.
- Output the entire report in markdown format.

Transcript:
{transcript_text}
"""

def extract_title(md_text):
    match = re.search(r'^#\s*(.+)', md_text, re.MULTILINE)
    if match:
        return match.group(1).strip()
    p_match = re.search(r'^[^\n#][^\n]+', md_text, re.MULTILINE)
    if p_match:
        return p_match.group(0).strip()[:60]
    return "Audio Transcript Report"

def markdown_to_docx(md_text):
    html = markdown2.markdown(md_text, extras=["tables"])
    soup = BeautifulSoup(html, "html.parser")
    doc = Document()
    title_text = extract_title(md_text)
    title = doc.add_heading(title_text, 0)
    title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    style = doc.styles['Normal']
    style.font.size = Pt(12)
    body = soup.body if soup.body else soup
    if not body or not list(body.children):
        return None
    for el in body.children:
        name = getattr(el, "name", None)
        if name and name.startswith("h"):
            if name == "h1":
                continue
            level = int(name[1])
            doc.add_heading(el.text, min(level, 4))
        elif name == "ul":
            for li in el.find_all("li", recursive=False):
                doc.add_paragraph(li.text, style="List Bullet")
        elif name == "ol":
            for li in el.find_all("li", recursive=False):
                doc.add_paragraph(li.text, style="List Number")
        elif name == "p":
            doc.add_paragraph(el.text)
        elif name == "table":
            rows = el.find_all("tr")
            if not rows:
                continue
            cols = rows[0].find_all(["td", "th"])
            table = doc.add_table(rows=len(rows), cols=len(cols))
            table.style = 'Table Grid'
            for i, row in enumerate(rows):
                for j, cell in enumerate(row.find_all(["td", "th"])):
                    table.cell(i, j).text = cell.text
        elif name is None and el.string and el.string.strip():
            doc.add_paragraph(el.string.strip())
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp_file:
        doc.save(tmp_file.name)
        tmp_file.seek(0)
        docx_bytes = tmp_file.read()
    os.unlink(tmp_file.name)
    return docx_bytes

def transcribe_audio(model, audio_bytes, mimetype, input_lang):
    lang_hint = ""
    if input_lang and input_lang != "Auto-detect":
        lang_hint = f" The audio is in {input_lang}."
    transcript_response = model.generate_content([
        {"mime_type": mimetype, "data": audio_bytes},
        f"Transcribe this audio.{lang_hint} Output only the transcript, in the spoken language."
    ])
    transcript = transcript_response.text.strip()
    if not transcript or transcript.lower() in (
        "none", "no speech detected", "could not transcribe"):
        return ""
    return transcript

def generate_professional_document(model, transcript_text, output_lang, input_lang):
    doc_prompt = universal_gemini_prompt(transcript_text, output_lang, input_lang)
    doc_response = model.generate_content([doc_prompt])
    professional_doc_md = doc_response.text.strip()
    return professional_doc_md

# ---- Main App Logic ----
if st.session_state.credentials_set:
    st.header("Step 1: Upload Audio Files")
    st.markdown("Upload one or more audio files (WAV, MP3, OGG, FLAC, M4A, MP4). Once processed, download your professional multilingual reports.")
    audio_files = st.file_uploader(
        "Upload audio files",
        type=["wav", "mp3", "ogg", "flac", "m4a", "mp4"],
        accept_multiple_files=True
    )

    if "processed_files" not in st.session_state:
        st.session_state.processed_files = dict()

    if audio_files and submitted:
        model = genai.GenerativeModel("models/gemini-1.5-flash-latest")
        for audio_file in audio_files:
            fname = audio_file.name
            ext = os.path.splitext(fname)[1]
            mimetype = get_mimetype(ext)
            file_key = (fname, audio_file.size, input_lang, output_lang)
            if file_key not in st.session_state.processed_files:
                with st.spinner(f"Processing: {fname}"):
                    try:
                        audio_bytes = audio_file.read()
                        transcript_text = transcribe_audio(model, audio_bytes, mimetype, input_lang)
                        if not transcript_text.strip():
                            st.session_state.processed_files[file_key] = None
                            st.error(f"Skipping {fname}: no transcript extracted.")
                            continue
                        professional_doc_md = generate_professional_document(model, transcript_text, output_lang, input_lang)
                        if not professional_doc_md.strip():
                            st.session_state.processed_files[file_key] = None
                            st.error(f"Skipping {fname}: markdown document was not generated.")
                            continue
                        docx_bytes = markdown_to_docx(professional_doc_md)
                        if docx_bytes:
                            st.session_state.processed_files[file_key] = docx_bytes
                        else:
                            st.session_state.processed_files[file_key] = None
                            st.error(f"Failed to generate DOCX for {fname}.")
                    except Exception as e:
                        st.session_state.processed_files[file_key] = None
                        st.error(f"Error processing {fname}: {e}")

        st.header("Step 2: Download Reports")
        for audio_file in audio_files:
            fname = audio_file.name
            file_key = (fname, audio_file.size, input_lang, output_lang)
            docx_bytes = st.session_state.processed_files.get(file_key)
            if docx_bytes:
                st.download_button(
                    label=f"⬇️ Download DOCX: {fname}",
                    data=docx_bytes,
                    file_name=f"{os.path.splitext(fname)[0]}_report.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
                st.success(f"DOCX ready for download: {fname}")
