# Therapeutic Strategy Assistant

Therapeutic Strategy Assistant is a biomedical retrieval project that connects known therapeutic targets to existing drugs, mechanisms, clinical evidence, literature evidence, and supporting public biomedical sources.

The project is designed for research support and learning. It is not a clinical decision system, does not recommend treatment for individual patients, and does not perform novel drug or target discovery.

## What This Project Does

The project follows this evidence flow:

```text
Target -> existing drugs/therapies -> mechanisms -> evidence -> retrieval -> grounded answer
```

Example research questions:

```text
Which approved therapies target EGFR?
What evidence supports sotorasib as a KRAS therapy?
Which ALK therapies have clinical trial evidence?
Which BRAF drugs have FDA label evidence?
What diseases are associated with EGFR in Open Targets?
```

## Current Status

The current implementation has moved beyond the original EGFR-only proof of concept into a multi-target retrieval dataset.

| Area | Status |
| --- | --- |
| Data preparation | Complete for the current 8-target scope |
| Multi-target knowledge base | Complete |
| Chunk generation | Complete |
| ChromaDB vector indexing | Complete |
| Multi-target retrieval evaluation | Complete |
| Prompted LLM answer generation | Complete locally |
| FastAPI API | Complete locally |
| Streamlit UI | Complete locally |
| Monitoring / deployment | Not yet implemented |

Current retrieval result:

```text
Targets: 8
Knowledge-base rows: 207
RAG-ready chunks: 207
Evaluation questions: 24
Retrieval hits: 24 / 24
Hit rate: 1.0
```

## Targets

| Display name | Canonical symbol |
| --- | --- |
| EGFR | EGFR |
| HER2 | ERBB2 |
| BRAF | BRAF |
| ALK | ALK |
| KRAS | KRAS |
| VEGFA | VEGFA |
| MET | MET |
| PIK3CA | PIK3CA |

HER2 is stored as `ERBB2` because that is the canonical symbol used by many biomedical databases.

## Data Sources

| Source | Role |
| --- | --- |
| ChEMBL | Drug-target mechanisms, molecule identifiers, action types, and development phase |
| PubMed | Literature evidence |
| ClinicalTrials.gov | Clinical trial evidence |
| openFDA | FDA label and indication evidence |
| DGIdb | Drug-gene interaction cross-checks |
| Open Targets | Target-disease association context |
| UniProt | Target/protein metadata and external identifiers |
| DrugCentral | Drug activity, indications, off-label use, and contraindication context |

DrugBank is not used as a core data source because full data access requires appropriate licensing.

## Repository Structure

```text
notebooks/
  Source-specific exploration, cleaning, and knowledge-base notebooks.

ingestion/
  ChromaDB indexing for retrieval-ready chunks.

evaluation/
  Retrieval questions, retrieval evaluation script, and saved retrieval results.

app/
  Local RAG pipeline, LLM answer service, and FastAPI application.

frontend/
  Streamlit interface for asking questions and inspecting retrieved evidence.

monitoring/
  Placeholder telemetry layer for the upcoming monitoring stage.

pyproject.toml
  Python project metadata and dependencies managed with uv.

uv.lock
  Locked dependency versions for reproducible setup.
```

Generated local files are intentionally ignored by git:

```text
data/raw/
data/processed/
chroma_db/
```

## Setup

This project uses `uv` for Python dependency management.

Install `uv` if needed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Clone and install:

```bash
git clone https://github.com/AI-Precision-Medicine-Zoomcamp/therapeutic-strategy-assistant.git
cd therapeutic-strategy-assistant
uv sync
```

Start Jupyter for notebook execution:

```bash
uv run jupyter lab
```

## Environment Variables

Generated LLM answers require an OpenAI API key. Retrieval and evidence inspection still work without a key.

Create a local `.env` file in this project, or place one in a parent folder such as `datatalks/llm/.env` if you want to reuse the same key across related projects.

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

The app automatically loads the nearest `.env` file from the project folder or its parent folders. Do not commit `.env`; it is ignored by git.

## Reproduce The Data Pipeline

Run the notebooks in order.

| Order | Notebook | Purpose |
| --- | --- | --- |
| 1 | `01_chembl_egfr_exploration.ipynb` | Original EGFR ChEMBL exploration |
| 2 | `02_pubmed_evidence_exploration.ipynb` | Original EGFR PubMed exploration |
| 3 | `03_clinical_trials_exploration.ipynb` | Original EGFR ClinicalTrials.gov exploration |
| 4 | `04_openfda_drug_labels_exploration.ipynb` | Original EGFR openFDA exploration |
| 5 | `05_dgidb_opentargets_crosscheck.ipynb` | Original EGFR DGIdb and Open Targets cross-check |
| 6 | `06_uniprot_egfr_target_metadata.ipynb` | Original EGFR UniProt metadata |
| 7 | `07_drugcentral_egfr_indications.ipynb` | Original EGFR DrugCentral enrichment |
| 8 | `08_drugbank_egfr_enrichment.ipynb` | DrugBank access/status check |
| 9 | `09_multi_target_chembl_exploration.ipynb` | Multi-target ChEMBL mechanisms and recommendations |
| 10 | `10_multi_target_pubmed_exploration.ipynb` | Multi-target PubMed evidence |
| 11 | `11_multi_target_clinical_trials_exploration.ipynb` | Multi-target ClinicalTrials.gov evidence |
| 12 | `12_multi_target_openfda_exploration.ipynb` | Multi-target openFDA label evidence |
| 13 | `13_multi_target_dgidb_opentargets_exploration.ipynb` | Multi-target DGIdb and Open Targets cross-check |
| 14 | `14_multi_target_uniprot_metadata.ipynb` | Multi-target UniProt metadata |
| 15 | `15_multi_target_drugcentral_exploration.ipynb` | Multi-target DrugCentral evidence |
| 16 | `16_multi_target_knowledge_base_build.ipynb` | Final multi-target knowledge base and chunk generation |

Notebook 16 creates:

```text
data/processed/multi_target_therapy_knowledge_base.csv
data/processed/multi_target_therapy_knowledge_base_chunks.jsonl
data/processed/multi_target_therapy_knowledge_base_summary.csv
```

## Build The Vector Index

After running notebook 16, index the chunks into ChromaDB:

```bash
uv run python ingestion/index_to_vectordb.py
```

Expected output:

```text
Chunks indexed: 207
Targets: ALK, BRAF, EGFR, ERBB2, KRAS, MET, PIK3CA, VEGFA
```

## Run Retrieval Evaluation

Run the multi-target retrieval evaluation:

```bash
uv run python evaluation/retrieval_eval.py
```

The evaluation reads:

```text
evaluation/retrieval_questions_multi_target.jsonl
```

It writes:

```text
evaluation/retrieval_results_multi_target.json
```

Current result:

```text
Questions: 24
Hits: 24
Hit rate: 1.0
```

## Run Local RAG

Ask a question from the command line:

```bash
UV_CACHE_DIR=.uv-cache uv run python -m app.rag_pipeline \
  --question "What evidence supports sotorasib as a KRAS therapy?" \
  --target KRAS \
  --top-k 3
```

If `OPENAI_API_KEY` is set, the pipeline returns a generated answer grounded in retrieved evidence. If the key is missing, it returns an evidence-only fallback so retrieval can still be tested.

## Run The API

Start the FastAPI app:

```bash
UV_CACHE_DIR=.uv-cache uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Available endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Service health and supported targets |
| `POST /retrieve` | Retrieve relevant evidence chunks |
| `POST /ask` | Retrieve evidence and generate a grounded answer |

Example health check:

```bash
curl http://127.0.0.1:8000/health
```

## Run The Streamlit UI

Start the UI:

```bash
UV_CACHE_DIR=.uv-cache uv run streamlit run frontend/streamlit_app.py --server.address 127.0.0.1 --server.port 8501
```

Open:

```text
http://127.0.0.1:8501
```

The UI supports:

```text
question input
target filter
automatic target detection for clear single-target questions
top-k evidence control
grounded answer display
retrieved evidence and metadata display
optional prompt inspection
research-only safety notice
```

## Current Knowledge Base

The final knowledge base stores one row per target-drug candidate.

Important fields include:

| Field | Meaning |
| --- | --- |
| `target_symbol` | Canonical target symbol |
| `drug_name` | Candidate therapy or drug |
| `molecule_chembl_id` | ChEMBL molecule identifier |
| `mechanism_of_action` | Mechanism text where available |
| `approval_status` | Development or approval status derived from ChEMBL phase |
| `pubmed_count` | Literature evidence count |
| `clinical_trial_count` | Clinical trial evidence count |
| `label_count` | openFDA label count |
| `dgidb_interaction_count` | DGIdb interaction evidence count |
| `drugcentral_activity_count` | DrugCentral activity evidence count |
| `evidence_score` | Project-level evidence coverage score |
| `evidence_text` | Text used for retrieval chunks |

The evidence score is a project-level retrieval ranking signal, not a medical recommendation score.

## Safety Notes

- This is a research-support prototype.
- It does not provide medical advice.
- It does not recommend treatment for individual patients.
- It does not claim that a drug cures a disease.
- LLM-generated answers are designed to use retrieved evidence and show source context.

## Next Stage

The next development stage is:

```text
Answer evaluation and monitoring
```

The next implementation should:

```text
1. Add answer-level evaluation for groundedness and source use.
2. Add basic telemetry for questions, retrieved chunks, latency, model, and errors.
3. Validate Docker and deployment workflow after the local app is stable.
4. Keep README updated as serving and monitoring mature.
```
