#!/usr/bin/env python3
"""Convert text resumes to PDF."""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

def txt_to_pdf_simple(txt_file, pdf_file):
    """Convert text file to PDF with proper formatting."""
    c = canvas.Canvas(pdf_file, pagesize=letter)
    c.setFont('Courier', 9)
    y = 750
    margin = 50
    page_height = 750
    line_height = 11
    
    with open(txt_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if y < 50:  # New page needed
                c.showPage()
                c.setFont('Courier', 9)
                y = page_height
            c.drawString(margin, y, line)
            y -= line_height
    
    c.save()
    print(f'✅ Created: {pdf_file}')

if __name__ == '__main__':
    import sys
    if len(sys.argv) == 3:
        txt_to_pdf_simple(sys.argv[1], sys.argv[2])
    else:
        txt_to_pdf_simple('input/student1_resume.txt', 'input/student1_resume.pdf')
        txt_to_pdf_simple('input/student2_resume.txt', 'input/student2_resume.pdf')
        txt_to_pdf_simple('input/rahul_sharma_resume.txt', 'input/rahul_sharma_resume.pdf')
    print('📄 PDF files created successfully!')
