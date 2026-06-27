# Therapeutic Strategy Assistant

Evidence-grounded retrieval prototype for answering:

```text
What existing therapies can act on this target?
```

Current MVP target: `EGFR`.

This project is a research-support tool. It connects an existing biological target to known therapies, mechanisms, evidence sources, and confidence signals. It does not discover new targets and does not provide clinical treatment advice.

## Current Status

Week 1-3 work is complete for the EGFR MVP.

| Week | Goal | Status |
| --- | --- | --- |
| Week 1 | Define project scope | Complete |
| Week 2 | Select and explore datasets | Complete |
| Week 3 | Build knowledge base, chunks, evaluation questions, and retrieval prototype | Complete |

Current outputs:

```text
1 target: EGFR
76 therapy/drug rows
76 retrieval chunks
15 retrieval evaluation questions
15/15 retrieval hits with ChromaDB
```

## Scope

This assistant focuses on **Therapeutic Strategy / Drug Repurposing**:

```text
Target -> existing therapies -> mechanisms -> evidence -> confidence signals
```

In scope:

- EGFR drug-target relationships
- Existing therapies linked to EGFR
- Mechanisms of action
- Approval / investigational status from ChEMBL `max_phase`
- Label evidence from openFDA
- Literature evidence from PubMed
- Clinical trial evidence from ClinicalTrials.gov
- Target and disease context from UniProt and Open Targets
- DrugCentral indication/activity enrichment
- ChromaDB retrieval prototype

Out of scope for Week 1-3:

- Novel target discovery
- Patient-specific treatment recommendation
- FastAPI `/ask` endpoint
- Streamlit UI
- LLM-generated answer
- Docker deployment
- Production monitoring

## Data Sources

The project uses source-specific notebooks to explore, clean, and write processed outputs.

| Notebook | Source | Purpose |
| --- | --- | --- |
| `01_chembl_egfr_exploration.ipynb` | ChEMBL | EGFR target, activity, mechanism, approval phase |
| `02_pubmed_evidence_exploration.ipynb` | PubMed | Literature evidence for EGFR therapies |
| `03_clinical_trials_exploration.ipynb` | ClinicalTrials.gov | Clinical trial evidence |
| `04_openfda_drug_labels_exploration.ipynb` | openFDA | FDA label and indication evidence |
| `05_dgidb_opentargets_crosscheck.ipynb` | DGIdb + Open Targets | External drug-gene and disease-association cross-check |
| `06_uniprot_egfr_target_metadata.ipynb` | UniProt | EGFR protein metadata |
| `07_drugcentral_egfr_indications.ipynb` | DrugCentral | Drug activity and indication enrichment |
| `08_drugbank_egfr_enrichment.ipynb` | DrugBank | Access/status check only |

DrugBank note: full DrugBank data requires access/licensing, so it is not required for the Week 1-3 MVP. The project continues with public/API-backed sources.

## Pipeline

The project uses `uv`, not `requirements.txt`.

Install dependencies:

```bash
uv sync
```

The source notebooks write cleaned files into:

```text
data/processed/
```

The merged knowledge base is built with:

```bash
uv run python ingestion/index_to_vectordb.py
```

That script reads the processed notebook outputs and writes:

```text
data/processed/egfr_therapy_knowledge_base.csv
data/processed/egfr_therapy_knowledge_base_chunks.jsonl
```

The retrieval prototype is run with:

```bash
uv run python evaluation/retrieval_eval.py
```

That script:

1. Reads `egfr_therapy_knowledge_base_chunks.jsonl`
2. Builds a local ChromaDB collection
3. Runs 15 evaluation questions
4. Writes `evaluation/retrieval_results.json`

## Key Files

```text
notebooks/                         Source exploration and cleaning
ingestion/index_to_vectordb.py     Merged EGFR knowledge-base builder
evaluation/retrieval_questions.jsonl
evaluation/retrieval_eval.py
README.md
prd.md
pyproject.toml
uv.lock
```

Generated files:

```text
data/raw/                          Raw snapshots where available
data/processed/                    Cleaned and merged data
chroma_db/                         Local ChromaDB retrieval index
```

`data/`, `chroma_db/`, `prd.md`, and internal weekly team docs are ignored by git.

## Reproduce Week 3

From the project root:

```bash
uv sync
uv run python ingestion/index_to_vectordb.py
uv run python evaluation/retrieval_eval.py
```

Expected retrieval summary:

```text
Week 3 ChromaDB retrieval prototype
Questions: 15
Hits: 15
Hit rate: 1.0
```

## Data Quality Notes

The ChEMBL approval-status bug was fixed.

Before the fix, `max_phase = 4.0` was incorrectly labeled as `Research / Unknown`. The notebook now coerces `max_phase` to a numeric value before assigning approval labels.

Current approval-status counts:

```text
Approved                     20
Investigational (Phase 3)    19
Investigational (Phase 2)    25
Investigational (Phase 1)    12
```

## How To Explain This Project

Short version:

```text
I built the Week 1-3 foundation for a Therapeutic Strategy Assistant.
It currently supports one target, EGFR.
The system connects EGFR to known therapies using ChEMBL, DGIdb, Open Targets, openFDA, PubMed, ClinicalTrials.gov, UniProt, and DrugCentral.
I built a merged 76-row knowledge base, generated 76 retrieval chunks, created 15 evaluation questions, and verified a ChromaDB retrieval prototype with 15/15 hits.
```

More detailed version:

```text
The project does not discover new targets. It starts from an existing target, EGFR, and retrieves evidence for therapies that may act on it.

The data work is organized as separate notebooks, one per source or source group. Each notebook explores and cleans one dataset. The ingestion script then merges the processed outputs into a single application-ready knowledge base.

For Week 3, I added retrieval preparation by converting the merged knowledge base into JSONL evidence chunks and indexing them in ChromaDB. I also created 15 evaluation questions covering drug matching, approval status, FDA labels, PubMed evidence, clinical trials, Open Targets disease context, UniProt target metadata, DrugCentral indication evidence, ranking, and repurposing signals.
```

## Next Stage

Only after Week 3, the next stage is to build the application layer:

```text
query input -> retrieve relevant chunks -> show ranked evidence -> later add LLM summary
```

Do not build FastAPI, Streamlit, Docker, or LLM generation until the weekly plan moves beyond the current Week 1-3 scope.
