import os
import requests
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import List

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- 1. THE MODERN V2 SCHEMA ---
class VerseNode(BaseModel):
    num: str
    text: str

class Annotation(BaseModel):
    term: str
    definition: str

class CommentarySection(BaseModel):
    heading: str
    content: str

class FPBibleStudy(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    title: str
    immediate_context: str
    fulfillment_notes: List[str]
    annotations: List[Annotation]
    commentary_sections: List[CommentarySection]
    new_creation_reality: str
    reflection: str

    @field_validator("fulfillment_notes")
    @classmethod
    def check_notes_count(cls, v):
        if not (3 <= len(v) <= 5):
            raise ValueError("fulfillment_notes must contain 3–5 items")
        return v

# --- 2A. SIMPLE HTML PRINTER ---
def save_master_page(data, raw_verses, book, ch, total_chapters=None):
    filename = os.path.join(OUTPUT_DIR, f"{book.lower()}_{ch}.html")

    bolded_verses = ""
    for v in raw_verses:
        text = v['text']
        for anno in data.annotations:
            text = text.replace(anno.term, f"<strong>{anno.term}</strong>")
        bolded_verses += f'<p><span class="v-num">{v["num"]}</span>{text}</p>'

    html_out = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>{data.title}</title>
    <style>
    body{{font-family: system-ui, sans-serif; line-height:1.65; margin:24px;}}
    .scripture{{background:#fafafa; padding:12px; border:1px solid #ddd;}}
    h2{{margin-top:24px;}}
    </style></head><body>
    <h1>{data.title}</h1>
    <h2>Immediate Context</h2><p>{data.immediate_context}</p>
    <h2>Scripture (WEB)</h2><div class="scripture">{bolded_verses}</div>
    <h2>Fulfillment Notes</h2>{"".join([f'<p>{n}</p>' for n in data.fulfillment_notes])}
    <h2>Annotations</h2>{"".join([f'<p><strong>{a.term}</strong>: {a.definition}</p>' for a in data.annotations])}
    <h2>Fulfillment Commentary</h2>{"".join([f'<h3>{c.heading}</h3><p>{c.content}</p>' for c in data.commentary_sections])}
    <h2>New Creation Reality</h2><p>{data.new_creation_reality}</p>
    <h2>Reflection</h2><p>{data.reflection}</p>
    </body></html>"""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_out)


# --- THE INCOME-READY AUDIT ---
def verify_and_save(data, verses, book, ch):
    content = " ".join([c.content for c in data.commentary_sections])

    # HARD LOCK: Catch any futurist "perhaps/maybe" language
    junk_words = ["perhaps", "might", "historically seen", "possibly", "lens"]
    found_junk = [w for w in junk_words if w in content.lower()]

    if found_junk:
        print(f"❌ REJECTED: Futurist Creep found ({found_junk}). Regenerating...")
        return False  # Triggers a retry

    word_count = len(content.split())
    if word_count < 750:  # Raising the bar for the eBook
        print(f"❌ REJECTED: Low Volume ({word_count} words). Regenerating...")
        return False

    save_master_page(data, verses, book, ch, 28)
    return True

# --- 2. THE PRODUCTION ENGINE ---
def generate_fpbible_chapter(book, ch_num):
    print(f"📡 Processing {book} {ch_num} (Enforcing 700+ Words)...")
    
    url = f"https://raw.githubusercontent.com/TehShrike/world-english-bible/master/json/{book.lower()}.json"
    raw_data = requests.get(url).json()
    verses = [{"num": str(v.get('verseNumber', '')), "text": v['value']} 
              for v in raw_data if v.get('chapterNumber') == ch_num and 'text' in v['type']]
    full_text = " ".join([v['text'] for v in verses])

    # TRIGGER: We explicitly demand 200+ words per section to ensure we pass the 700-word audit.
    volume_prompt = """
    MANDATORY DEPTH REQUIREMENT:
    - You must write 5 Commentary Sections. 
    - Each section MUST be at least 160 words long. 
    - Total Commentary MUST exceed 800 words total.
    - Be exhaustive, scholarly, and assertive.
    - DO NOT SUMMARIZE. Provide deep covenantal breakdown.
    """

    attempts = 0
    while attempts < 3:
        try:
            response = client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06", # Or gpt-5.2-codex
                messages=[
                    {"role": "system", "content": f"LOCKED FPBIBLE PROTOCOL: Authoritative voice. AD 70 fulfillment only. No meta-language. {volume_prompt}"},
                    {"role": "user", "content": f"Produce the MASTER STUDY for {book} {ch_num}: {full_text}"}
                ],
                response_format=FPBibleStudy
            )
            
            data = response.choices[0].message.parsed
            word_count = sum(len(c.content.split()) for c in data.commentary_sections)
            
            if word_count >= 700:
                print(f"✅ Audit Passed ({word_count} words). Verifying...")
                if verify_and_save(data, verses, book, ch_num):
                    return
            print(f"❌ Audit Failed ({word_count} words). Retrying for depth...")
            attempts += 1
        except Exception as e:
            print(f"⚠️ Error: {e}")
            attempts += 1

if __name__ == "__main__":
    generate_fpbible_chapter("john", 1)