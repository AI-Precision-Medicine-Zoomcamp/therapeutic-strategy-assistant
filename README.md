# Therapeutic Strategy Assistant

Therapeutic Strategy Assistant is a biomedical retrieval project for connecting a known therapeutic target to existing drugs, mechanisms, clinical evidence, and supporting biomedical sources.

The current minimum viable product focuses on one target:

```text
EGFR - Epidermal growth factor receptor
```

The project answers research questions such as:

```text
Which existing therapies target EGFR, and what evidence supports them?
```

This is a research-support prototype. It is not a clinical decision system, does not recommend treatment for individual patients, and does not perform novel target discovery.

## Project Scope

The current implementation covers the Week 1 to Week 3 milestone:

| Milestone | Status | Output |
| --- | --- | --- |
| Week 1: Project planning | Complete | EGFR therapeutic strategy scope |
| Week 2: Data source setup | Complete | Public biomedical datasets selected and explored |
| Week 3: Knowledge base and retrieval prototype | Complete | Merged EGFR knowledge base, retrieval chunks, and ChromaDB evaluation |

Later product features such as a public API, user interface, LLM answer generation, and deployment are intentionally outside the current milestone.

## What The Project Builds

The pipeline collects EGFR therapy evidence from public biomedical data sources, cleans the data in source-specific notebooks, merges the processed outputs into a single knowledge base, and tests retrieval with ChromaDB.

```text
Public biomedical data sources
        |
        v
Exploration and cleaning notebooks
        |
        v
Processed source datasets
        |
        v
Merged EGFR therapy knowledge base
        |
        v
Retrieval-ready evidence chunks
        |
        v
ChromaDB retrieval evaluation
```

## Current MVP Summary

| Item | Current value |
| --- | --- |
| Target count | 1 |
| Target | EGFR |
| Processed therapy rows | 76 |
| Retrieval chunks | 76 |
| Evaluation questions | 15 |
| Retrieval backend | ChromaDB |
| Current retrieval result | 15 / 15 hits |

## Data Sources

The knowledge base combines evidence from the following sources:

| Source | Role in the project |
| --- | --- |
| ChEMBL | EGFR drug-target mechanisms, molecule identifiers, and development phase |
| DGIdb | Drug-gene interaction cross-checks |
| Open Targets | EGFR disease-association context |
| openFDA | FDA label and indication evidence |
| PubMed | Literature evidence for selected EGFR therapies |
| ClinicalTrials.gov | Clinical trial evidence and trial phase context |
| UniProt | EGFR protein metadata |
| DrugCentral | Drug activity and indication enrichment |
| DrugBank | Access/status check only; full data is not included because it requires appropriate access and licensing |

## Repository Structure

Only the directories needed for the current milestone are listed here.

```text
notebooks/
  Source-specific exploration and cleaning notebooks.

ingestion/
  Builds the merged EGFR knowledge base and retrieval chunks.

evaluation/
  Stores retrieval questions and the ChromaDB retrieval evaluation script.

pyproject.toml
  Python project metadata and dependencies managed with uv.

uv.lock
  Locked dependency versions for reproducible setup.
```

Generated local files are not committed to git:

```text
data/raw/
  Raw downloaded or captured source files.

data/processed/
  Cleaned datasets, merged knowledge base, and retrieval chunks.

chroma_db/
  Local ChromaDB index created during retrieval evaluation.
```

## Setup

This project uses `uv` for Python dependency management.

Install `uv` if it is not already installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Clone the repository:

```bash
git clone https://github.com/AI-Precision-Medicine-Zoomcamp/therapeutic-strategy-assistant.git
cd therapeutic-strategy-assistant
```

Install dependencies:

```bash
uv sync
```

Start Jupyter if you need to regenerate the processed datasets from the notebooks:

```bash
uv run jupyter lab
```

## Reproducing The Current Pipeline

The processed data is generated locally and ignored by git. On a fresh clone, run the notebooks first, then run the ingestion and evaluation scripts.

### Step 1: Run the source notebooks

Run the notebooks in this order:

| Order | Notebook | Purpose |
| --- | --- | --- |
| 1 | `01_chembl_egfr_exploration.ipynb` | Builds the base EGFR therapy list from ChEMBL |
| 2 | `02_pubmed_evidence_exploration.ipynb` | Collects PubMed evidence |
| 3 | `03_clinical_trials_exploration.ipynb` | Collects ClinicalTrials.gov evidence |
| 4 | `04_openfda_drug_labels_exploration.ipynb` | Collects openFDA label evidence |
| 5 | `05_dgidb_opentargets_crosscheck.ipynb` | Adds DGIdb and Open Targets cross-checks |
| 6 | `06_uniprot_egfr_target_metadata.ipynb` | Adds EGFR protein metadata |
| 7 | `07_drugcentral_egfr_indications.ipynb` | Adds DrugCentral activity and indication evidence |
| 8 | `08_drugbank_egfr_enrichment.ipynb` | Records DrugBank access/status information |

The notebooks write cleaned outputs into:

```text
data/processed/
```

### Step 2: Build the knowledge base

After the processed notebook outputs exist, run:

```bash
uv run python ingestion/index_to_vectordb.py
```

This creates:

```text
data/processed/egfr_therapy_knowledge_base.csv
data/processed/egfr_therapy_knowledge_base_chunks.jsonl
```

Expected current output:

```text
Rows: 76
Chunks: 76
```

### Step 3: Run retrieval evaluation

Run:

```bash
uv run python evaluation/retrieval_eval.py
```

This script:

1. Reads the retrieval chunks from `data/processed/egfr_therapy_knowledge_base_chunks.jsonl`.
2. Builds a local ChromaDB collection in `chroma_db/`.
3. Runs the evaluation questions in `evaluation/retrieval_questions.jsonl`.
4. Writes the result summary to `evaluation/retrieval_results.json`.

Expected current result:

```text
Questions: 15
Hits: 15
Hit rate: 1.0
```

## Knowledge Base

The final knowledge base stores one row per EGFR therapy candidate.

Important columns include:

| Column | Description |
| --- | --- |
| `target_name` | Target name, currently `EGFR` |
| `drug_name` | Candidate therapy or drug |
| `mechanism_of_action` | Mechanism evidence from ChEMBL |
| `action_type` | Type of interaction where available |
| `approval_status` | Approved or investigational status derived from ChEMBL `max_phase` |
| `openfda_label_count` | Number of matching openFDA labels |
| `pubmed_count` | Number of PubMed evidence records |
| `clinical_trial_count` | Number of matching clinical trial records |
| `drugcentral_evidence_score` | DrugCentral activity and indication evidence score |
| `final_ranking_score` | Combined evidence score used for ordering candidates |
| `source_references` | Sources supporting the row |
| `evidence_summary_text` | Text used to create retrieval chunks |

Approval status is normalized from ChEMBL `max_phase`, so values such as `4`, `4.0`, and `"4.0"` are handled consistently.

Current approval-status distribution:

```text
Approved                     20
Investigational (Phase 3)    19
Investigational (Phase 2)    25
Investigational (Phase 1)    12
```

## Retrieval Evaluation

The evaluation dataset is stored in:

```text
evaluation/retrieval_questions.jsonl
```

Each evaluation record contains:

| Field | Description |
| --- | --- |
| `question` | The retrieval question |
| `expected_source` | The source expected to support the answer |
| `category` | The evidence category being tested |

Example categories include:

```text
Drug Matching
Approval Status
Drug Label Evidence
Clinical Trials
Literature Evidence
Mechanism of Action
Evidence Summary
Target Metadata
Ranking
Evidence Gap
```

The current retrieval score is a functional smoke test for the Week 3 prototype. It confirms that relevant evidence chunks can be retrieved, but it is not a clinical validation metric.

## Current Limitations

- The current knowledge base covers only EGFR.
- The retrieval prototype runs locally.
- Generated datasets and vector indexes are not committed to git.
- DrugBank full data is not included because it requires appropriate access and licensing.
- The current system retrieves evidence but does not generate final natural-language medical recommendations.
- This project is not suitable for clinical decision-making.

## Next Development Stage

Recommended next steps after the Week 1 to Week 3 milestone:

1. Add a simple query interface over the ChromaDB retriever.
2. Add an API endpoint for retrieval requests.
3. Add grounded answer generation using only retrieved evidence.
4. Add a lightweight user interface for exploring therapies and evidence.
5. Add tests around ingestion, retrieval, and ranking behavior.
6. Extend the pipeline to additional therapeutic targets beyond EGFR.
