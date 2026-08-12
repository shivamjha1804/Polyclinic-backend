import fitz

def extract_text(raw_bytes: bytes) -> str:
    if raw_bytes[:4] == b"%PDF":
        doc = fitz.open(stream=raw_bytes, filetype="pdf")
        return "\n".join(page.get_text() for page in doc)
    return raw_bytes.decode("utf-8", errors="ignore")
