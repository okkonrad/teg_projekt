import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve()
for parent in REPO_ROOT.parents:
    if (parent / "pyproject.toml").exists():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break

from src.data.pdf_generator import PDFGenerator
from src.data.pdf_parser import extract_text_from_pdf

def test_pipeline():
    print("Testing PDF Pipeline...")
    
    # Mock Candidate
    candidate = {
        "id": "test_candidate_001",
        "name": "Jane Doe",
        "location": "New York",
        "hourly_rate": 120.0,
        "email": "jane@example.com",
        "skills": [{"name": "Python", "proficiency": "Expert"}, {"name": "GraphRAG", "proficiency": "Beginner"}],
        "experience": [
            {"role": "Senior Engineer", "company": "TechCorp", "start_date": "2020-01-01", "end_date": "2023-01-01", "description": "Built cool stuff."}
        ]
    }
    
    # 1. Generate
    gen = PDFGenerator(output_dir="data/test_cvs")
    filepath = gen.generate_candidate_pdf(candidate)
    print(f"Generated PDF: {filepath}")
    
    if not os.path.exists(filepath):
        print("FAIL: PDF file not created.")
        return

    # 2. Parse
    text = extract_text_from_pdf(filepath)
    print("Extracted Text Preview:")
    print(text[:200])
    
    # 3. Verify
    if "Jane Doe" in text and "Python" in text and "TechCorp" in text:
        print("SUCCESS: Text content verification passed.")
    else:
        print("FAIL: Missing expected text content.")
        
    # Cleanup
    shutil.rmtree("data/test_cvs")

if __name__ == "__main__":
    test_pipeline()
