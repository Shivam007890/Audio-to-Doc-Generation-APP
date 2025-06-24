import os
import re
import streamlit as st
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
import google.generativeai as genai
import markdown2
from bs4 import BeautifulSoup
import tempfile
import json

# Streamlit page configuration
st.set_page_config(page_title="Panchayat Audio Report Generator", layout="wide")

# Title and description
st.title("Panchayat Audio Report Generator")
st.write("Upload multiple audio files to transcribe, translate to Malayalam, and generate professional Panchayat reports in DOCX format.")

# Set Google API credentials from Streamlit Secrets
def set_credentials():
    try:
        # Access credentials from Streamlit Secrets
        credentials_json = st.secrets["google"]["credentials"]
        # Write credentials to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp_file:
            tmp_file.write(credentials_json.encode('utf-8'))
            tmp_file_path = tmp_file.name
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp_file_path
        st.session_state.credentials_path = tmp_file_path
        st.success("Google API credentials loaded successfully from Streamlit Secrets!")
        return True
    except Exception as e:
        st.error(f"Error loading credentials from Secrets: {e}")
        return False

# Initialize credentials
if 'credentials_set' not in st.session_state:
    st.session_state.credentials_set = set_credentials()

# Proceed only if credentials are set
if st.session_state.credentials_set:
    # Audio file upload
    st.header("Step 1: Upload Audio Files")
    st.write("Supported formats: WAV, MP3, OGG, FLAC, M4A, MP4")
    audio_files = st.file_uploader("Upload audio files", type=["wav", "mp3", "ogg", "flac", "m4a", "mp4"], accept_multiple_files=True)

    # Output folder configuration
    st.header("Step 2: Configure Output")
    default_output = os.path.join(os.path.expanduser("~"), "Desktop", "GEMINI_OUTPUT")
    output_folder = st.text_input("Output Folder Path", value=default_output)
    if st.button("Create Output Folder"):
        os.makedirs(output_folder, exist_ok=True)
        st.success(f"Output folder created/verified at: {output_folder}")

    # Function to get MIME type
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

    # Improved Gemini prompt (unchanged from your script)
    def improved_gemini_prompt(mal_text):
        return f"""
        ഈ transcript-ന്റെ അടിസ്ഥാനത്തിൽ, താഴെ പറയുന്ന ഘടനയും നിർദേശങ്ങളും കർശനമായി പാലിച്ചുകൊണ്ട് ഒരു ഗ്രാമപഞ്ചായത്ത് വിശദമായ, ഔദ്യോഗിക ഭാഷയിൽ എഴുതിയ, പ്രൊഫഷണൽ വിശകലന റിപ്പോർട്ട് markdown format-ൽ തയ്യാറാക്കുക.

        **If any section lacks sufficient information in the transcript, create representative, plausible, and professional content for that section, using your general knowledge of Panchayat reports in Kerala.**

        # ഗ്രാമപഞ്ചായത്തിന്റെ യഥാർത്ഥ പേര്, ജില്ല (audio/transcript-ൽ ലഭ്യമായെങ്കിൽ മാത്രം; placeholder ഉപയോഗിക്കരുത്.)

        ## മോദി സർക്കാരിന്റെ നേട്ടങ്ങൾ
        - transcript-ൽ നിന്നുള്ള പ്രധാന നേട്ടങ്ങൾ, പദ്ധതികൾ, അവയുടെ ഫലപ്രാപ്തി, ഉദാഹരണങ്ങൾ
        - subheadings (ഉപശീർഷികങ്ങൾ) transcript-ൽ നിന്നുണ്ടെങ്കിൽ bold smaller headings ആയി ഉപയോഗിക്കുക; ഇവയില്ലെങ്കിൽ, സാധാരണയായി കാണുന്ന ഉപശീർഷികൾ ചേർക്കുക.
        - body government report style-ൽ, വിശദീകരണം, context, statistics, examples എന്നിവയോടെ എഴുതുക.

        ## ആരോപണങ്ങൾ / അടിസ്ഥാന പ്രശ്നങ്ങൾ
        - transcript-ൽ നിന്നുള്ള പ്രധാന പ്രശ്നങ്ങൾ, ഉദാഹരണങ്ങൾ, സ്ഥലങ്ങൾ, പരിഹാരങ്ങൾ
        - subheadings transcript-ൽ നിന്ന് കണ്ടെത്തി bold smaller headings ആയി എഴുതുക; ഇവയില്ലെങ്കിൽ, സാധാരണ പ്രശ്നങ്ങൾ ചേർക്കുക.
        - body content paragraph-ൽ വിശദമായ വിവരണം, background, example, implication ഉൾപ്പെടുത്തുക.

        ## വികസന രേഖ/ദർശനം
        - transcript-ൽ നിന്നുള്ള വികസന ലക്ഷ്യങ്ങൾ, പദ്ധതികൾ, നിർദേശങ്ങൾ, പുതിയ ആശയങ്ങൾ
        - subheadings transcript-ൽ നിന്ന് bold smaller headings ആയി ഉപയോഗിച്ച്, ഇവയില്ലെങ്കിൽ സാധാരണ vision headings ചേർക്കുക.
        - body content professional, visionary, policy-oriented language-ൽ paragraph-ൽ വിശദമായി എഴുതുക.

        - Section headings bold, left aligned; subheadings bold, left aligned, smaller font; body justified alignment, bullet points/numbered lists ആവശ്യമായിടത്ത് മാത്രം ഉപയോഗിക്കുക.
        - Report-ൽ ഒരു ഭാഗത്തും [Insert ... here], "---", “audio does not provide”, “audio indicates”, “audio mentions”, “not mentioned”, “unavailable”, “lack. of data”, “audio-യിൽ” എന്നൊന്നും എഴുതരുത്.

        Transcript:
        {mal_text}
        """

    # Function to extract Panchayat name
    def extract_panchayat_name(md_text):
        match = re.search(r'^#\s*(.+)', md_text, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return "ഗ്രാമപഞ്ചായത്ത് ഡോക്യുമെന്റ്"

    # Function to convert Markdown to DOCX
    def markdown_to_docx(md_text, out_path):
        html = markdown2.markdown(md_text, extras=["tables"])
        soup = BeautifulSoup(html, "html.parser")
        doc = Document()

        panchayat_name = extract_panchayat_name(md_text)
        title = doc.add_heading(panchayat_name, 0)
        title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        style = doc.styles['Normal']
        style.font.name = 'Noto Sans Malayalam'
        style.font.size = Pt(12)

        body = soup.body if soup.body else soup
        if not body or not list(body.children):
            st.warning("No content available to write to DOCX.")
            return False

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
                    docස്‍
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
        doc.save(out_path)
        return True

    # Function to transcribe and translate audio
    def transcribe_and_translate(model, audio_bytes, mimetype, fname):
        with st.spinner(f"Transcribing {fname}..."):
            transcript_response = model.generate_content([
                {"mime_type": mimetype, "data": audio_bytes},
                "Transcribe this audio. Output only the transcript."
            ])
            transcript = transcript_response.text.strip()
            if not transcript or transcript.strip().lower() in (
                "none", "no speech detected", "could not transcribe"):
                st.warning(f"No valid transcript extracted for {fname}.")
                return ""
            st.write(f"**Transcript for {fname}:**\n{transcript}")
        
        with st.spinner(f"Translating {fname} to Malayalam..."):
            translation_response = model.generate_content([
                f"ഇത് മലയാളത്തിലേക്ക് വിവർത്തനം ചെയ്യുക:\n{transcript}"
            ])
            mal_text = translation_response.text.strip()
            st.write(f"**Malayalam Translation for {fname}:**\n{mal_text}")
            return mal_text

    # Function to generate professional document
    def generate_professional_document(model, mal_text, fname):
        with st.spinner(f"Generating professional document for {fname}..."):
            doc_prompt = improved_gemini_prompt(mal_text)
            doc_response = model.generate_content([doc_prompt])
            professional_doc_md = doc_response.text.strip()
            if not professional_doc_md.strip():
                st.warning(f"No markdown content generated for {fname}.")
                return ""
            st.write(f"**Generated Markdown for {fname}:**\n{professional_doc_md}")
            return professional_doc_md

    # Process audio files
    if audio_files and st.button("Process Audio Files"):
        model = genai.GenerativeModel("models/gemini-1.5-flash-latest")
        st.header("Processing Results")
        for audio_file in audio_files:
            fname = audio_file.name
            ext = os.path.splitext(fname)[1]
            mimetype = get_mimetype(ext)
            st.subheader(f"Processing: {fname}")

            try:
                audio_bytes = audio_file.read()
                mal_text = transcribe_and_translate(model, audio_bytes, mimetype, fname)
                if not mal_text.strip():
                    st.error(f"Skipping {fname} as no transcript/translation was extracted.")
                    continue

                professional_doc_md = generate_professional_document(model, mal_text, fname)
                if not professional_doc_md.strip():
                    st.error(f"Skiping {fname} as no markdown document was generated.")
                    continue

                # Save DOCX to output folder
                out_base = os.path.splitext(fname)[0]
                docx_path = os.path.join(output_folder, f"{out_base}_panchayat_document.docx")
                if markdown_to_docx(professional_doc_md, docx_path):
                    # Provide download link
                    with open(docx_path, "rb") as f:
                        st.download_button(
                            label=f"Download {fname} DOCX",
                            data=f,
                            file_name=f"{out_base}_panchayat_document.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                        )
                    st.success(f"DOCX created: {docx_path}")
            except Exception as e:
                st.error(f"Error processing {fname}: {e}")

# Clean up temporary credentials file on app exit
def cleanup():
    if 'credentials_path' in st.session_state:
        try:
            os.unlink(st.session_state.credentials_path)
        except:
            pass

import atexit
atexit.register(cleanup)
