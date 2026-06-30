# Multi-Source Candidate Data Transformer
**Technical Design Document**

## 1. The Problem
Eightfold receives candidate data from multiple fragmented, messy, and conflicting sources (e.g., CSV exports, ATS JSON blobs, PDF resumes). Downstream systems require a single, trustworthy, canonical profile for every candidate. Bad or confident-but-wrong data pollutes hiring decisions. 

**The Goal**: Build a deterministic data pipeline that ingests heterogeneous sources, resolves candidate identities, normalizes disparate formats, merges conflicts intelligently, calculates confidence, records data provenance, and projects the final output into a customizable JSON schema.

---

## 2. Inputs & Outputs
- **Inputs**: 
  - *Structured*: Recruiter CSV exports.
  - *Semi-Structured*: ATS JSON payloads with arbitrary, non-standard field names.
  - *Unstructured*: Raw PDF Resumes.
  - *Runtime Config*: A JSON file defining how the final output should be shaped, allowing dynamic field subsetting, remapping, and missing-value policies.
- **Output**: A canonical JSON array of merged candidate profiles, guaranteeing schema validity, deduplication, and traceable provenance.

---

## 3. Pipeline Workflow (How I solved it)
The system is orchestrated by a linear pipeline (`TransformerPipeline`) consisting of 6 distinct phases:

1. **Detect & Validate**: Scans input paths, validates file extensions, and hashes file contents (MD5) to instantly discard duplicate files.
2. **Extract (Parsers)**: Dispatches files to specific parsers (`CSVParser`, `ATSParser`, `PDFParser`). Parsers apply heuristics/mappings to extract a `RawExtraction` dictionary without crashing on malformed inputs.
3. **Normalize**: Crucial data points are standardized *before* merging:
   - **Phones**: E.164 format (using `phonenumbers` library).
   - **Dates**: `YYYY-MM` format.
   - **Countries**: ISO-3166 alpha-2 format.
   - **Skills**: Aliases mapped to Canonical names (e.g., `"js"` -> `"JavaScript"`).
4. **Match (Identity Resolution)**: Uses a **Union-Find (Disjoint Set) graph**. Extractions are merged into a single candidate *only* if they share exact matches on highly specific anchors: Email, Phone, LinkedIn URL, or GitHub URL. (Name-only matching is avoided to prevent false positives).
5. **Merge & Score**: Resolves field-level conflicts based on strict **Source Priorities** (e.g., `linkedin` > `github` > `ats_json` > `csv`). Lists (like skills and experience) are deduplicated. **Confidence** is assigned per skill based on multi-source agreement, and an overall profile confidence is computed based on data density and source quality. Every field decision generates a `Provenance` tag.
6. **Project & Validate**: Takes the merged canonical record and reshapes it dynamically based on the user's `runtime_config.json`, applying field-remapping (fan-outs like `skills[].name`) and missing-value policies (`null`, `omit`, or `error`). Validates the final structure before JSON serialization.

---

## 4. Edge Cases & Known Failure Modes (Honest Assessment)

While the pipeline is highly robust and handles malformed inputs gracefully, there are specific edge cases where it intentionally makes tradeoffs or might fail:

> [!WARNING]
> **The "John Smith" Identity Problem (False Negatives)**
> If two source files contain a candidate named "John Smith" with identical work histories but absolutely no overlapping contact info (no emails, no phones), the engine will output **two separate candidates**. Because Name-only matching creates disastrous false-positives in hiring, the engine rigidly requires a hard anchor.

> [!WARNING]
> **Highly Creative Resumes (Heuristics Failure)**
> The `PDFParser` relies on textual heuristics (e.g., finding the word "Experience"). If a candidate uploads a wildly creative, multi-column resume without standard headers, the parser will fail to extract their timeline. It will not crash, but the data will be missing in the canonical profile.

> [!TIP]
> **Dynamic Config Normalization Traded for Canonical Purity**
> The assignment prompt suggested the runtime config could set per-field normalization. However, this engine eagerly normalizes everything (phones to E.164, skills to canonical) strictly within the internal pipeline. A projection config asking for `"normalize": "raw"` would be ignored because the raw data is intentionally discarded to maintain canonical purity.

> [!CAUTION]
> **Strict Projection Policies causing Data Loss**
> The projector honors a `"missing_value": "error"` policy. If a runtime config requires a specific indexed path (e.g., `"path": "emails[3]", "required": true, "missing_value": "error"`), and a candidate only has 1 email, the projector throws a hard error for that candidate and completely omits them from the final JSON payload.

---
*Note: To submit this as a PDF per the assignment deliverables, you can open this markdown file in VS Code or your browser and simply select "Print to PDF".*
