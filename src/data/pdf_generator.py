from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
from typing import Dict

class PDFGenerator:
    def __init__(self, output_dir: str = "data/raw/cvs"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_candidate_pdf(self, candidate: Dict) -> str:
        """Generates a simple PDF CV for a candidate."""
        filename = f"{candidate['id']}.pdf"
        filepath = os.path.join(self.output_dir, filename)
        
        c = canvas.Canvas(filepath, pagesize=letter)
        width, height = letter
        
        # Header
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, candidate['name'])
        
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 70, f"Location: {candidate.get('location', 'Unknown')}")
        c.drawString(50, height - 85, f"Rate: ${candidate.get('hourly_rate', 0)}/hr")
        c.drawString(50, height - 100, f"Email: {candidate.get('email', 'N/A')}")
        
        y = height - 130
        
        # Skills
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "Skills")
        y -= 20
        c.setFont("Helvetica", 10)
        
        for s in candidate.get('skills', []):
            if y < 50:
                 c.showPage()
                 y = height - 50
            
            # Clean proficiency string (remove "SkillProficiency.")
            prof = str(s.get('proficiency', '')).replace('SkillProficiency.', '')
            c.drawString(60, y, f"• {s['name']} ({prof})")
            y -= 15
            
        y -= 20
        
        # Experience
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "Experience")
        y -= 25
        
        for exp in candidate.get('experience', []):
            if y < 50:
                c.showPage()
                y = height - 50
                
            c.setFont("Helvetica-Bold", 10)
            c.drawString(50, y, f"{exp['role']} at {exp['company']}")
            y -= 15
            c.setFont("Helvetica", 10)
            c.drawString(50, y, f"{exp.get('start_date', '')} - {exp.get('end_date', '')}")
            y -= 25

        c.save()
        return filepath
