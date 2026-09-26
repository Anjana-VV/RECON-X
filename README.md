# RECON-X

### AI-Assisted Intelligent Data Recovery and Digital Evidence Reconstruction

> **Recovering a file does not necessarily mean recovering reliable evidence.**

> **RECON-X does not tell investigators what they want to hear. It tells them what the available evidence supports.**

---

## 1. Overview

RECON-X is an AI-assisted digital evidence recovery and reconstruction prototype designed to bridge the gap between **file carving** and **evidence reliability**.

Traditional recovery tools can identify byte patterns that resemble files, but identifying a file is not the same as establishing that the recovered artifact is structurally usable, sufficiently complete, or correctly reconstructed.

RECON-X therefore treats recovery as an **evidence-confidence and reconstruction problem**.

The system combines:

- Evidence acquisition and SHA-256 provenance
- JPEG signature scanning and carving
- Fragment-level deterministic feature extraction
- AI-assisted fragment compatibility analysis
- Reconstruction hypothesis generation
- Evidence contradiction detection
- Controlled ordered JPEG reconstruction
- Structural and decodability validation
- Recovery completeness assessment
- Explainable Reconstruction Confidence Scoring
- Evidence prioritization
- Explicit forensic evidence-state categorization
- Offline ground-truth evaluation
- A provenance-focused forensic investigator UI

The AI component proposes possible fragment relationships. **Deterministic validation remains responsible for testing whether a proposed reconstruction is supported by the recovered bytes.**

---

## 2. The Core Idea

RECON-X separates six stages:

```text
DETECT
   ↓
RELATE
   ↓
RECONSTRUCT
   ↓
VALIDATE
   ↓
ASSESS
   ↓
PRIORITIZE
```

The central principle is:

> **Detection is not recovery. Recovery is not reconstruction. Reconstruction is not validation. And validation is not certainty.**

---

## 3. Problem

Digital evidence can be damaged or partially lost through:

- Accidental deletion
- Filesystem corruption
- Storage damage
- Ransomware or malicious destruction
- Fragmentation
- Duplicate evidence
- Partial overwriting

Traditional file carving can recover byte regions that look like files, but several questions remain:

- Do the fragments actually belong together?
- Is the reconstructed artifact structurally valid?
- Is a decodable file necessarily complete?
- Did corruption alter the recovered bytes?
- Are duplicated fragments inflating recovery results?
- Which conclusions are directly observed versus inferred?
- What should remain explicitly unknown?

RECON-X addresses these questions by combining ML-assisted hypothesis generation with deterministic validation and an explicit evidence-state model.

---

## 4. What Makes RECON-X Different

### 4.1 Fragment Intelligence

RECON-X extracts deterministic byte-level features from candidate fragments, including:

- Size
- Byte entropy
- Zero-byte ratio
- Unique-byte ratio
- Byte mean
- Byte standard deviation
- JPEG header/footer presence
- JPEG marker information
- Pairwise statistical differences
- Fixed boundary statistics

A lightweight Random Forest model uses these features to calculate a:

> **Fragment Compatibility Score**

The score is a **model-derived compatibility signal**.

It is **not** a probability, authenticity score, or forensic certainty.

---

### 4.2 Reconstruction Hypotheses

Instead of blindly joining fragments, RECON-X generates a bounded set of candidate ordered reconstruction hypotheses.

Example:

```text
FRAG-001 → FRAG-002 → FRAG-003
```

Alternative arrangements can also be tested.

Each hypothesis is independently passed through the deterministic reconstruction and integrity pipeline.

Possible outcomes:

```text
SUPPORTED
REJECTED
PARTIAL
```

---

### 4.3 AI Does Not Make the Final Forensic Decision

A core safety mechanism is the separation between ML inference and deterministic evidence validation.

```text
AI Compatibility: HIGH
        ↓
Candidate Reconstruction
        ↓
Deterministic Validation
        ↓
       PASS
        ↓
    SUPPORTED
```

or:

```text
AI Compatibility: HIGH
        ↓
Candidate Reconstruction
        ↓
Deterministic Validation
        ↓
       FAIL
        ↓
    REJECTED
```

A high compatibility score does **not** override failed deterministic validation.

---

## 5. Evidence States

RECON-X explicitly separates information into four states.

### OBSERVED

Directly measured from the available evidence.

Examples:

- Evidence offsets
- SHA-256
- File size
- JPEG markers
- Decodability
- Structural validation results

### RECONSTRUCTED

An artifact produced by combining observed evidence fragments.

### INFERRED

Analytical conclusions derived from measured evidence.

Examples:

- Fragment compatibility
- Fragment relationship ranking
- Reconstruction hypotheses
- Evidence prioritization

### UNKNOWN

Information that cannot be established from the available evidence.

Examples:

- Missing fragments
- Unknown original size
- Unavailable filename
- Unestablished recovery completeness
- Unestablished fragment consistency

RECON-X deliberately preserves uncertainty rather than replacing unavailable information with fabricated values.

---

## 6. Architecture

```text
                 DAMAGED STORAGE / DISK IMAGE
                              │
                              ▼
                    ┌──────────────────┐
                    │ Evidence         │
                    │ Acquisition      │
                    └────────┬─────────┘
                             ▼
                       SHA-256 Hash
                             │
                             ▼
                      JPEG Scanner
                             │
                             ▼
                       JPEG Carver
                             │
                             ▼
                    Candidate Regions
                             │
                             ▼
                  Fragment Intelligence
                             │
                             ▼
                Fragment Compatibility
                       Random Forest
                             │
                             ▼
                 Reconstruction Hypotheses
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
               Hypothesis A      Hypothesis B
                    │                 │
                    └────────┬────────┘
                             ▼
                  Deterministic Ordered
                     Reconstruction
                             │
                             ▼
                      Integrity Engine
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
                SUPPORTED          REJECTED
                    │                 │
                    └────────┬────────┘
                             ▼
                Completeness / Confidence
                             │
                             ▼
                    Evidence Priority
                             │
                             ▼
                       FastAPI API
                             │
                             ▼
                 Forensic Investigator UI
```

---

## 7. Technology Stack

### Backend

- Python 3
- FastAPI
- Uvicorn

### Core Forensic Engine

- Python Standard Library
- `hashlib`
- Pillow

### Machine Learning

- scikit-learn
- Random Forest Classifier
- Deterministic engineered fragment features

### Frontend

- HTML5
- CSS3
- Vanilla JavaScript
- Fetch API

### Validation / Data

- JSON
- JSON schemas
- Offline ground-truth evaluation

### Intentionally Not Used

- React
- Vite
- Tailwind
- Node.js
- Next.js
- Vue
- Angular
- RAG
- LangChain
- Knowledge Graph
- Neo4j
- MongoDB
- PostgreSQL
- SQLite
- Docker/Kubernetes
- Cloud services
- LLM-dependent recovery

The prototype deliberately keeps the recovery pipeline deterministic and lightweight.

---

## 8. Current File-Type Scope

### Currently supported end-to-end

**JPEG / JPG**

The current prototype is intentionally JPEG-focused.

The complete demonstrated pipeline currently supports JPEG:

```text
JPEG Detection
    ↓
JPEG Carving
    ↓
Fragment Features
    ↓
Compatibility Model
    ↓
Reconstruction Hypotheses
    ↓
Ordered Reconstruction
    ↓
JPEG Integrity Validation
    ↓
Confidence / Priority
    ↓
Forensic UI
    ↓
Offline Evaluation
```

### Not currently claimed

The current prototype does **not** claim end-to-end recovery for:

- PNG
- PDF
- DOC/DOCX
- ZIP/RAR
- MP4/video
- Arbitrary binary formats
- Arbitrary out-of-order fragmented files
- General filesystem-level recovery across FAT/NTFS/ext4/etc.

Additional format-specific carvers and validators are future work.

---

## 9. Recovery Pipeline

### 9.1 Evidence Acquisition

The system calculates SHA-256 for the uploaded evidence source and records the evidence provenance.

### 9.2 JPEG Scan and Carving

JPEG signatures are detected using:

```text
FF D8 = Start Of Image
FF D9 = End Of Image
```

Candidate byte ranges and absolute offsets are recorded.

### 9.3 Fragment Feature Extraction

Candidate fragments are represented using deterministic byte-level characteristics such as entropy, size, byte distribution, JPEG markers, and boundary statistics.

### 9.4 Fragment Compatibility

A Random Forest classifier evaluates relationships between candidate fragments and produces a Fragment Compatibility Score in `[0, 1]`.

This score is not a probability.

### 9.5 Hypothesis Generation

The hypothesis engine creates a small, bounded set of candidate ordered fragment chains.

The prototype does not claim arbitrary out-of-order recovery.

### 9.6 Reconstruction

Validated ordered chunks are concatenated exactly as observed.

The system does not fabricate missing bytes.

If required fragments are unavailable, the result remains partial or otherwise conservative.

### 9.7 Integrity Validation

JPEG artifacts are checked for:

- Valid JPEG header
- Valid JPEG footer
- Decodability
- Structural validity
- Conservative corruption indication

Pillow verification and reopening/loading are used as part of the validation process.

---

## 10. Reconstruction Confidence Score

The Reconstruction Confidence Score is an explainable engineering score.

It is **not a probability**.

```text
Confidence =
    0.30 × Classification
  + 0.30 × Structural Integrity
  + 0.25 × Recovery Completeness
  + 0.15 × Fragment Consistency
```

### Labels

| Score | Label |
|---|---|
| 0.85–1.00 | HIGH |
| 0.65–<0.85 | MEDIUM |
| 0.40–<0.65 | LOW |
| <0.40 | UNRELIABLE |

When required measurements are unavailable, the system preserves `Not established` rather than fabricating a value.

---

## 11. Evidence Prioritization

Evidence Priority is a deterministic triage score used to order artifacts for investigator attention.

```text
Priority =
    0.40 × Confidence
  + 0.30 × Recovery Completeness
  + 0.20 × Structural Integrity
  + 0.10 × Relevance
```

Priority is:

- Not a probability
- Not proof of authenticity
- Not proof of guilt or innocence
- Not forensic certainty

It is a prioritization mechanism.

---

## 12. Dataset and Controlled Scenarios

RECON-X includes a deterministic synthetic evidence generator.

Generated evidence:

```text
dataset/generated/incident_disk.img
```

Offline evaluation metadata:

```text
dataset/ground_truth.json
```

### Ground Truth Isolation

`ground_truth.json` is **offline evaluation data only**.

The live forensic runtime does **not** read it.

Runtime decisions are made from the evidence bytes and the existing analysis pipeline.

### Controlled Scenarios

The dataset includes:

- `intact`
- `split`
- `corrupted`
- `duplicated`
- `deleted_unavailable`

Controlled split scenarios physically separate JPEG chunks using observable zero-padding gaps. The runtime can detect these controlled evidence segments without consulting ground truth.

---

## 13. Offline Ground-Truth Evaluation

RECON-X includes a separate offline evaluator:

```text
dataset/evaluate.py
```

Run it with:

```bash
python -m dataset.evaluate
```

It compares actual analysis behavior against the controlled ground truth **without feeding ground truth into runtime forensic decisions**.

The evaluator produces:

```text
dataset/evaluation_report.json
```

### Measured Metrics

The current controlled evaluation reports:

| Metric | Result |
|---|---:|
| Classification accuracy | **100%** |
| Recovery success rate | **100%** |
| Correct corruption handling | **50%** |
| Deleted evidence correctly flagged | **100%** |
| Exact byte matches among successful-status artifacts | **1 / 5 (20%)** |
| Exact byte mismatches among successful-status artifacts | **4 / 5 (80%)** |

Supporting statistics from the current 7-case controlled dataset:

- Ground-truth cases: **7**
- Runtime candidates: **6**
- Successful runtime recoveries: **5**
- Supported hypotheses: **2**
- Rejected hypotheses: **4**
- Partial hypotheses: **0**
- Exact byte matches: **1**
- Exact byte mismatches across matched candidates: **5**

### Important Interpretation

The `80%` figure above is **not** a claim that RECON-X has an 80% real-world failure rate.

It means:

> In this controlled 7-case evaluation, **4 of the 5 runtime artifacts that claimed `RECOVERED` or `RECONSTRUCTED` and had an available byte comparison did not exactly match the corresponding original bytes.**

This distinction is important because a file can:

- have valid JPEG structure,
- successfully decode,
- receive a successful recovery status,

while still not being byte-for-byte identical to the original.

That is precisely the evidence-honesty problem RECON-X is designed to expose.

The evaluation dataset is small and controlled. The results should not be interpreted as production forensic performance.

---

## 14. Forensic Reconstruction Trail

The frontend provides a provenance-focused reconstruction trail.

For each artifact, the interface separates:

```text
OBSERVED
    ↓
RECONSTRUCTED
    ↓
INFERRED
    ↓
UNKNOWN
```

The interface exposes:

- Artifact status
- Evidence quality
- Reconstruction assessment
- Compatibility information
- Hypothesis status
- Contradiction status
- SHA-256 provenance
- Evidence offsets
- Evidence map
- Artifact preview where appropriate
- "Why this assessment?" explanation

The UI deliberately distinguishes:

```text
DETECTED
    ≠
DECODED
    ≠
STRUCTURALLY VALID
    ≠
RECOVERED
    ≠
RECONSTRUCTED
    ≠
VERIFIED
```

A decoded file is not automatically treated as an exact or complete recovery.

---

## 15. API Capabilities

The FastAPI backend provides controlled endpoints for:

- `GET /health`
- `GET /api/health`
- `POST /api/cases`
- `POST /api/cases/{case_id}/analyze`
- `GET /api/cases/{case_id}`
- `GET /api/cases/{case_id}/artifacts`
- `GET /api/artifacts/{artifact_id}`
- `GET /api/artifacts/{artifact_id}/preview`

The API deliberately avoids exposing:

- Absolute filesystem paths
- Offline ground truth
- Internal training data
- Unverified forensic claims

The backend uses an in-memory registry and controlled working directories rather than a database.

---

## 16. Frontend

The frontend is a premium, light forensic workstation designed for investigator readability rather than cyberpunk styling.

Main views include:

- Overview
- Evidence
- Artifacts
- Artifact Detail
- Analysis
- Case Information

The artifact detail experience emphasizes:

1. What was found
2. What is known
3. What cannot be established
4. Why the assessment was made
5. Whether a reconstruction hypothesis was supported or rejected

Technical forensic details remain available beneath the high-level assessment.

---

## 17. Limitations

> **IMPORTANT FORENSIC CONSTRAINT**

The current prototype supports **controlled ordered fragmentation for JPEG artifacts**.

It does not claim:

- Arbitrary out-of-order fragment reconstruction
- General filesystem recovery
- Production-grade forensic probability estimation
- Universal file-format recovery
- Authenticity determination from a single confidence score
- Fabrication or recovery of bytes that are not present in evidence

When required fragments are unavailable, RECON-X remains conservative rather than inventing missing content.

The Fragment Compatibility Model is a controlled prototype model and should not be interpreted as a production-grade forensic probability estimator.

---

## 18. Testing and Validation

Run the complete test suite:

```bash
python -m pytest tests/ -v
```

Latest validation:

```text
141 passed
0 failed
```

The tests cover:

- Hashing
- Scanner behavior
- JPEG carving
- Reconstruction
- Integrity validation
- Confidence
- Prioritization
- Feature extraction
- Fragment classifier
- Reconstruction hypotheses
- Dataset generation
- Damage scenarios
- API behavior
- Offline evaluation

The project also includes focused tests for the offline evaluation logic.

---

## 19. Running RECON-X

### Install dependencies

```bash
pip install -r requirements.txt
```

### Start FastAPI

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend:

```text
http://127.0.0.1:8000
```

### Serve the frontend

Using Python's standard library:

```bash
python -m http.server 5500 --directory frontend
```

Frontend:

```text
http://127.0.0.1:5500
```

### Generate the controlled dataset

```bash
python -m dataset.generator
```

### Run offline evaluation

```bash
python -m dataset.evaluate
```

---

## 20. Project Structure

```text
recon-x/
├── README.md
├── DEMO_CHECKLIST.md
├── requirements.txt
├── .gitignore
│
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── cases.py
│   │   └── artifacts.py
│   └── services/
│       ├── __init__.py
│       └── analysis_service.py
│
├── core/
│   ├── __init__.py
│   ├── hashing.py
│   ├── scanner.py
│   ├── carving.py
│   ├── reconstruction.py
│   ├── integrity.py
│   ├── confidence.py
│   └── prioritization.py
│
├── ml/
│   ├── __init__.py
│   ├── features.py
│   ├── classifier.py
│   ├── train.py
│   └── hypotheses.py
│
├── dataset/
│   ├── originals/
│   ├── generated/
│   ├── generator.py
│   ├── damage_engine.py
│   ├── evaluate.py
│   ├── evaluation_report.json
│   └── ground_truth.json
│
├── schemas/
│   ├── fragment_schema.json
│   ├── artifact_schema.json
│   └── case_schema.json
│
├── samples/
│   └── demo_case/
│
├── tests/
│   ├── test_hashing.py
│   ├── test_scanner.py
│   ├── test_carving.py
│   ├── test_reconstruction.py
│   ├── test_integrity.py
│   ├── test_confidence.py
│   ├── test_prioritization.py
│   ├── test_features.py
│   ├── test_classifier.py
│   ├── test_hypotheses.py
│   ├── test_damage_engine.py
│   ├── test_generator.py
│   ├── test_evaluate.py
│   └── test_api.py
│
└── frontend/
    ├── index.html
    ├── style.css
    ├── app.js
    └── assets/
```

Runtime-generated upload evidence under `samples/uploads/` is intentionally excluded from version control.

---

## 21. Judge Talking Points

### The core problem

> **"The difficult part of digital recovery isn't finding bytes that look like a file. It's determining which fragments actually belong together and whether the resulting reconstruction is supported by the evidence."**

### The AI differentiator

> **"RECON-X uses a lightweight ML model to evaluate compatibility between evidence fragments and generate candidate reconstruction hypotheses."**

### The safety mechanism

> **"The AI does not make the final forensic decision. Every candidate reconstruction is independently tested using deterministic structural validation."**

### The contradiction story

> **"If the AI considers fragments compatible but the reconstruction fails deterministic validation, RECON-X rejects the hypothesis instead of blindly trusting the model."**

### The evidence-honesty story

> **"A file opening successfully does not prove that it is the original evidence."**

### The provenance story

> **"RECON-X separates what was observed, what was reconstructed, what was inferred, and what remains unknown."**

### The non-hallucination principle

> **"When evidence is missing, RECON-X does not invent missing bytes or pretend the artifact is complete."**

### The evaluation story

> **"We don't only report what our system claims. We compare those claims against a separate ground-truth dataset offline and measure exact byte agreement."**

### The scope

> **"The current prototype focuses on JPEG artifacts and controlled ordered fragmentation. It deliberately does not claim arbitrary out-of-order recovery."**

---

## 22. Demo Flow

A concise demonstration should follow:

```text
1. Upload evidence
        ↓
2. Scan and carve candidates
        ↓
3. Show recovered artifact
        ↓
4. Show fragment compatibility
        ↓
5. Generate reconstruction hypothesis
        ↓
6. Run deterministic validation
        ↓
7. Show SUPPORTED or REJECTED
        ↓
8. Open "Why this assessment?"
        ↓
9. Show Observed / Reconstructed / Inferred / Unknown
        ↓
10. Show offline evaluation results
```

The strongest technical moment is the separation:

```text
AI PROPOSES
     ↓
EVIDENCE VALIDATES
     ↓
RECON-X REPORTS WHAT IS SUPPORTED
```

---

## 23. Future Work

Potential extensions include:

- PNG chunk-based reconstruction
- PDF object and stream recovery
- Additional archive/container formats
- More advanced JPEG structural analysis
- Advanced fragment alignment using JPEG-specific structures
- Larger and more diverse compatibility-model datasets
- Evaluation across larger evidence sources
- Filesystem-aware recovery
- Production-grade forensic audit workflows

These are future directions and are **not claimed as current prototype capabilities**.

---

## 24. Core Principle

RECON-X is built around one principle:

> **Detection is not recovery. Recovery is not reconstruction. Reconstruction is not validation. And validation is not certainty.**

The system therefore keeps the stages separate:

```text
DETECT
  ↓
RELATE
  ↓
RECONSTRUCT
  ↓
VALIDATE
  ↓
ASSESS
  ↓
PRIORITIZE
```

This allows RECON-X to use AI where it is useful — **generating and ranking reconstruction hypotheses** — while retaining deterministic evidence validation as the final technical check.

> **AI proposes. Evidence validates. RECON-X reports what is actually supported.**
