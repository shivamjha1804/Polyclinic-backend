import voyageai
from app.config import settings
import re

vo = voyageai.Client(api_key= settings.VOYAGE_API_KEY)

def embed_documents(texts: list[str]) -> list[list[float]]:
    out = []
    for i in range(0, len(texts), 128):
        r = vo.embed(texts[i:i+128], model=settings.EMBED_MODEL, input_type="document")
        out.extend(r.embeddings)
    return out

def embed_query(text: str) -> list[float]:
    return vo.embed([text], model=settings.EMBED_MODEL, input_type="query").embeddings[0]

SECTIONS = ["Chief Complaint", "History of Present Illness", "Past Medical History", "Medications", "Allergies", "Examination", "Investigations", "Assessment", "Plan", "Impression", "Findings"]

SECTION_PATTERN = re.compile(
    r"^(" + "|".join(re.escape(s) for s in SECTIONS) + r")\s*:?\s*$",
    re.MULTILINE | re.IGNORECASE
)

MAX_WORDS = 800
OVERLAP_WORDS = 100

def _split_by_words(text: str, max_words: int, overlap_words: int) -> list[str]:
    words= text.split()
    if len(words) <= max_words:
        return [text]
    chunks = []
    start = 0
    while start < len(words):
        end = start + max_words
        chunks.append(" ".join(words[start:end]))
        start = end - overlap_words
    return chunks

def chunk_document(text: str) -> list[dict]:
    matches = list(SECTION_PATTERN.finditer(text))

    if not matches:
        pieces = _split_by_words(text, MAX_WORDS, OVERLAP_WORDS)
        return[{"section": None, "content": p} for p in pieces]

    chunks = []

    for i, match in enumerate(matches):
        section_name = match.group(1)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section_text = text[start:end].strip()

        for piece in _split_by_words(section_text, MAX_WORDS, OVERLAP_WORDS):
            chunks.append({"section": section_name, "content": f"{section_name} : {piece}"})

    return chunks
