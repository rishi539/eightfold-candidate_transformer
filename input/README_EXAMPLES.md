# Example Data Files for Testing

## Files Created

### 1. `input/students_example.json`
**Structured ATS export** with 2 students including edge cases:

**Student 1: José María García Álvarez**
- ✅ Complete profile
- Unicode name (accented characters)
- Full contact info
- Multiple experiences
- All fields populated
- Linked profiles (LinkedIn, GitHub)

**Student 2: 李华 (Li Hua)**
- ⚠️ Edge cases:
  - Unicode name (Chinese characters)
  - Email: empty string `"   "` (whitespace)
  - Phone: `null`
  - Company: empty string `""`
  - Location: `"\t"` (tab character)
  - LinkedIn: empty string `""`
  - Experience: empty array `[]`
  - Total years: `null`

### 2. `input/student1_resume.txt`
Resume text for José García (simulates PDF extraction)

### 3. `input/student2_resume.txt`
Resume text for Li Hua (simulates PDF extraction)

---

## Edge Cases Covered

### ✅ Empty Strings
```json
"email": "   ",     // Whitespace
"company": "",      // Empty
"location": "\t"    // Tab character
```
→ Pipeline will strip and convert to `None`

### ✅ Unicode Names
```json
"name": "José María García Álvarez"  // Spanish
"name": "李华"                        // Mandarin Chinese
```
→ Pipeline preserves UTF-8 encoding

### ✅ Null Values
```json
"phone": null,
"total_years_experience": null
```
→ Treated as missing data (no invention)

### ✅ Empty Arrays
```json
"experience": [],
"education": []
```
→ Handled gracefully (shows no prior work/education)

### ✅ Multiple Formats in Text
Resume text includes:
- Phone formats: `+34-91-555-0123`
- URLs: `linkedin.com/in/...`, `github.com/...`
- Dates: `January 2020 – June 2024`, `2023`
- Skills: Comma-separated list
- Location details embedded in header

---

## Convert to PDF (Optional)

If you want to generate actual PDF files from the text resumes:

### Option 1: Using Python `reportlab`
```bash
pip install reportlab
python -c "
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def txt_to_pdf(txt_file, pdf_file):
    c = canvas.Canvas(pdf_file, pagesize=letter)
    c.setFont('Helvetica', 10)
    y = 750
    with open(txt_file, 'r') as f:
        for line in f:
            c.drawString(50, y, line.strip())
            y -= 15
    c.save()

txt_to_pdf('input/student1_resume.txt', 'input/student1_resume.pdf')
txt_to_pdf('input/student2_resume.txt', 'input/student2_resume.pdf')
"
```

### Option 2: Using `pypdf` + word wrapping
```bash
pip install pypdf reportlab
```

### Option 3: Manual (macOS/Linux)
```bash
# Convert text to PDF using enscript
enscript -p student1_resume.pdf input/student1_resume.txt
enscript -p student2_resume.pdf input/student2_resume.txt
```

### Option 4: Online
- Use https://www.text2pdf.com/
- Upload text files, download PDFs

---

## Test the Pipeline

### Option A: CLI (Python)
```bash
cd c:\Users\rishi\Downloads\eightfold

# Test with JSON + text (simulating PDF)
python main.py --sources input/students_example.json --output output/result_json.json

# Test with all sources (if PDFs are available)
python main.py --sources input/students_example.json input/student1_resume.txt input/student2_resume.txt --output output/result_all.json
```

### Option B: REST API
```bash
# Terminal 1: Start Flask API
cd c:\Users\rishi\Downloads\eightfold
python api/app.py

# Terminal 2: Upload files
curl -X POST http://localhost:5000/api/transform \
  -F "files=@input/students_example.json" \
  -F "files=@input/student1_resume.txt" \
  -F "files=@input/student2_resume.txt" \
  -o result.json

# Or using Python
python -c "
import requests

files = [
    ('files', open('input/students_example.json', 'rb')),
    ('files', open('input/student1_resume.txt', 'rb')),
    ('files', open('input/student2_resume.txt', 'rb')),
]

response = requests.post('http://localhost:5000/api/transform', files=files)
print(response.json())
"
```

### Option C: React UI (When ready)
```bash
# Terminal 1: Flask API
python api/app.py

# Terminal 2: React Dev Server
cd frontend
npm install
npm run dev

# Terminal 3: Open browser
http://localhost:5173
# Upload files through UI
```

---

## Expected Output

### For José García (Complete Profile):
```json
{
  "candidate_id": "uuid-...",
  "full_name": "José María García Álvarez",
  "emails": ["jose.garcia@example.com"],
  "phones": ["+34915550123"],  // Normalized to E.164
  "location": {
    "city": "Madrid",
    "country": "ES"  // Normalized to ISO-3166
  },
  "headline": "Senior Software Engineer",
  "total_years_experience": 6,
  "skills": [
    {"name": "Python", "confidence": 0.95, "sources": ["ats_json", "resume_pdf", "resume_pdf"]},
    {"name": "Docker", "confidence": 0.95, "sources": ["ats_json", "resume_pdf"]},
    // ... more skills
  ],
  "experience": [
    {
      "company": "Tech Solutions S.L.",
      "title": "Senior Software Engineer",
      "start": "2020-01",
      "end": "2024-06"
    },
    // ... more experiences
  ],
  "overall_confidence": 0.92,  // High: multiple sources, complete data
  "provenance": {
    "full_name": ["ats_json", "resume_pdf"],
    "emails": ["ats_json"],
    "phones": ["ats_json"],
    "skills": ["ats_json", "resume_pdf"],
    "experience": ["ats_json", "resume_pdf"]
  }
}
```

### For Li Hua (Edge Cases):
```json
{
  "candidate_id": "uuid-...",
  "full_name": "李华",
  "emails": [],  // Empty (whitespace stripped)
  "phones": [],  // Empty (null value)
  "location": null,  // Tab character stripped to None
  "headline": "Data Scientist and Machine Learning Engineer",
  "total_years_experience": null,  // null value preserved
  "skills": [
    {"name": "TensorFlow", "confidence": 0.80, "sources": ["resume_pdf"]},
    {"name": "Python", "confidence": 0.80, "sources": ["resume_pdf"]},
    // ... more skills
  ],
  "experience": [],  // Empty array preserved
  "education": [
    {
      "institution": "Tsinghua University",
      "degree": "Master of Science",
      "field": "Artificial Intelligence",
      "end_year": 2023
    }
  ],
  "overall_confidence": 0.45,  // Lower: missing critical fields (emails, phones)
  "provenance": {
    "full_name": ["ats_json"],
    "skills": ["resume_pdf"],
    "education": ["ats_json"]
  }
}
```

---

## Key Observations

1. **José García**: 0.92 confidence (complete, multiple sources agree)
2. **Li Hua**: 0.45 confidence (incomplete, missing critical contact fields)
3. Both profiles preserve data integrity (no invented values)
4. Unicode names handled correctly
5. Empty strings/whitespace stripped appropriately
6. Null values preserved (not invented)
7. Phone numbers normalized (E.164 format)
8. Locations normalized (ISO-3166 country codes)

