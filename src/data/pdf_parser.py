from pypdf import PdfReader

def extract_text_from_pdf(filepath: str) -> str:
    """Extracts raw text from a PDF file."""
    try:
        reader = PdfReader(filepath)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"Error parsing PDF {filepath}: {e}")
        return ""
