# Multi-Source Candidate Data Transformer
**Eightfold Engineering Intern (Jul-Dec 2026) - Assignment**

This repository contains a deterministic data pipeline designed to ingest candidate information from heterogeneous, messy sources (ATS JSON, PDFs/DOCX), resolve identities, handle conflicts safely, calculate confidence scores, track provenance, and dynamically project the output into a canonical schema.


## 1. Assumptions & Scope
- **Identity Resolution**: Candidates are matched primarily via deterministic exact matches on normalized Email, Phone, and LinkedIn/GitHub URLs.
- **Heuristic Identity Fallback**: If contact info is entirely missing, candidates are successfully merged if they share identical normalized names **AND** have overlapping company names or job titles in their work history.
- **Descoped CSVs**: Processing flat CSV files was intentionally descoped to prioritize robust, deeply-nested JSON ATS schema traversal and complex unstructured PDF heuristic parsing.
- **Time/Location Validation**: Validation rules assume strict formatting (e.g., ISO-8601 for dates, ISO-3166 alpha-2 for country codes) and gently rejects/flags invalid fields via the validation projection layer while merging the remaining valid data.

## 2. Exact Run Steps
### Requirements
- **Python 3.10+**
- **Node.js** (Only required if running the Bonus React UI)

### Running the CLI Engine
The core backend pipeline reads the messy inputs and outputs the single trusted canonical JSON.

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Run the engine against the input files:**
   ```bash
   python main.py --sources input/*.json input/*.pdf --output output/result.json
   ```
3. **Run with detailed logging (Recommended for tracking internal heuristics):**
   ```bash
   python main.py --sources input/*.json input/*.pdf --verbose
   ```

## 3. Produced Output
Running the engine generates a unified `result.json` payload containing the normalized candidate array.
- Look in the `output/` directory after running the command above to see the canonical output.
- **Provenance tracking**: Every merged field in the output explicitly tracks its source origin (e.g., `resume_pdf` vs `ats_json`) and the method of extraction.
- **Confidence scoring**: Each candidate receives an overall confidence score and field-level skill confidence scores based on validation density and source overlap.

## 4. Running the Tests
A comprehensive `pytest` suite is included that strictly validates the PDF parsers, JSON ATS schema handling, confidence algorithms, and Identity Union-Find resolver logic.

1. **Execute the test suite:**
   ```bash
   python -m pytest tests/ -v
   ```

## 5. Bonus: React Dashboard
A full-stack React application is included to beautifully visualize the data merge and heuristic identity resolution in real-time.

1. **Start the Python Backend API:**
   ```bash
   python api/app.py
   ```
2. **Start the React Frontend:**
   *Open a new terminal window*
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
3. **Launch the Application:**
   Open your browser to `http://localhost:5173`. Drag and drop any combination of `.json` and `.pdf` files from the `input/` folder to instantly watch the engine perform its identity resolution and normalizations!
