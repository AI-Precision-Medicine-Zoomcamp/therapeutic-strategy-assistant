"""Build the EGFR therapeutic strategy knowledge base.

This script is the bridge between the exploration notebooks and the app.
It reads the cleaned CSVs in data/processed, merges evidence by drug, computes
a simple evidence score, and writes:

- data/processed/egfr_therapy_knowledge_base.csv
- data/processed/egfr_therapy_knowledge_base_chunks.jsonl
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

TARGET_NAME = "EGFR"
KNOWLEDGE_BASE_FILE = PROCESSED_DIR / "egfr_therapy_knowledge_base.csv"
CHUNKS_FILE = PROCESSED_DIR / "egfr_therapy_knowledge_base_chunks.jsonl"


def normalize_name(value: object) -> str:
    """Normalize drug names for joins across biomedical sources."""
    if pd.isna(value):
        return ""
    return re.sub(r"[^A-Z0-9]+", "", str(value).upper())


def read_csv(name: str) -> pd.DataFrame:
    path = PROCESSED_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing required processed dataset: {path}")
    return pd.read_csv(path)


def safe_join(values: pd.Series, limit: int = 5) -> str:
    cleaned = [str(value) for value in values if pd.notna(value) and str(value).strip()]
    return " | ".join(list(dict.fromkeys(cleaned))[:limit])


def phase_score(value: object) -> float:
    try:
        phase = float(value)
    except (TypeError, ValueError):
        return 0.10
    if phase >= 4:
        return 1.00
    if phase >= 3:
        return 0.75
    if phase >= 2:
        return 0.50
    if phase >= 1:
        return 0.25
    return 0.10


def clinical_score(row: pd.Series) -> float:
    if row.get("late_phase_trial_count", 0) > 0:
        return 1.00
    if row.get("active_trial_count", 0) > 0:
        return 0.70
    if row.get("clinical_trial_count", 0) > 0:
        return 0.40
    return 0.00


def literature_score(value: object) -> float:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 0.00
    if count >= 5:
        return 1.00
    if count >= 1:
        return 0.50
    return 0.00


def evidence_summary(row: pd.Series) -> str:
    parts = [
        f"Target: {row['target_name']}",
        f"Target protein: {row.get('protein_name', '') or 'not available'}",
        f"Target metadata source: UniProt {row.get('uniprot_accession', '')}",
        f"Drug: {row['drug_name']}",
        f"Mechanism: {row.get('mechanism_of_action', '') or 'not available'}",
        f"Action type: {row.get('action_type', '') or 'not available'}",
        f"Approval/phase: {row.get('approval_status', '')} (max_phase={row.get('max_phase', '')})",
        f"ChEMBL evidence: molecule {row.get('molecule_chembl_id', '')}; max_phase {row.get('max_phase', '')}",
        f"DGIdb evidence: score={row.get('dgidb_interaction_score', 0)}; sources: {row.get('dgidb_sources', '')}",
        f"openFDA: {row.get('openfda_label_count', 0)} labels; indications: {row.get('openfda_indications', '')}",
        f"PubMed: {row.get('pubmed_count', 0)} articles; top titles: {row.get('top_pubmed_titles', '')}",
        (
            "ClinicalTrials.gov: "
            f"{row.get('clinical_trial_count', 0)} trials, "
            f"{row.get('active_trial_count', 0)} active, "
            f"{row.get('late_phase_trial_count', 0)} late-phase"
        ),
        f"DrugCentral: score={row.get('drugcentral_evidence_score', 0)}; indications: {row.get('drugcentral_top_indications', '')}",
        f"Open Targets context: {row.get('opentargets_top_diseases', '')}",
        f"Final evidence score: {row.get('final_ranking_score', 0):.3f}",
        f"Source references: {row.get('source_references', '')}",
    ]
    return "\n".join(str(part) for part in parts)


def build_knowledge_base() -> pd.DataFrame:
    base = read_csv("egfr_drug_recommendations.csv").copy()
    base["target_name"] = TARGET_NAME
    base["normalised_drug_name"] = base["drug_name"].apply(normalize_name)

    dgidb = read_csv("egfr_dgidb_interactions.csv").copy()
    dgidb_grouped = (
        dgidb.groupby("normalised_drug_name", dropna=False)
        .agg(
            dgidb_interaction_score=("interaction_score", "max"),
            dgidb_sources=("sources", safe_join),
            dgidb_interaction_types=("interaction_types", safe_join),
            dgidb_matches_project_drug=("matches_project_drug", "max"),
        )
        .reset_index()
    )

    openfda = read_csv("egfr_openfda_summary.csv").copy()
    openfda["normalised_drug_name"] = openfda["drug_name"].apply(normalize_name)
    openfda = openfda.rename(columns={"top_indications": "openfda_indications"})

    pubmed = read_csv("egfr_pubmed_summary.csv").copy()
    pubmed["normalised_drug_name"] = pubmed["drug_name"].apply(normalize_name)

    trials = read_csv("egfr_clinical_trials_summary.csv").copy()
    trials["normalised_drug_name"] = trials["drug_name"].apply(normalize_name)

    drugcentral = read_csv("egfr_drugcentral_summary.csv").copy()
    drugcentral["normalised_drug_name"] = drugcentral["drugcentral_name"].apply(normalize_name)
    drugcentral = drugcentral.rename(columns={"top_indications": "drugcentral_top_indications"})

    uniprot = read_csv("egfr_uniprot_target_metadata.csv").iloc[0].to_dict()
    external = read_csv("egfr_external_crosscheck_summary.csv").iloc[0].to_dict()

    kb = base.merge(dgidb_grouped, on="normalised_drug_name", how="left")
    kb = kb.merge(
        openfda[
            [
                "normalised_drug_name",
                "openfda_label_count",
                "mentions_target_in_label",
                "brand_names",
                "generic_names",
                "openfda_indications",
                "has_openfda_label",
                "openfda_evidence_score",
            ]
        ],
        on="normalised_drug_name",
        how="left",
    )
    kb = kb.merge(
        pubmed[["normalised_drug_name", "pubmed_count", "top_pubmed_titles"]],
        on="normalised_drug_name",
        how="left",
    )
    kb = kb.merge(
        trials[
            [
                "normalised_drug_name",
                "clinical_trial_count",
                "active_trial_count",
                "late_phase_trial_count",
                "top_trial_titles",
                "clinical_evidence_score",
            ]
        ],
        on="normalised_drug_name",
        how="left",
    )
    kb = kb.merge(
        drugcentral[
            [
                "normalised_drug_name",
                "struct_id",
                "drugcentral_name",
                "activity_count",
                "indication_count",
                "drugcentral_top_indications",
                "has_drugcentral_indication",
                "drugcentral_evidence_score",
            ]
        ],
        on="normalised_drug_name",
        how="left",
    )

    fill_zero_columns = [
        "dgidb_interaction_score",
        "openfda_label_count",
        "openfda_evidence_score",
        "pubmed_count",
        "clinical_trial_count",
        "active_trial_count",
        "late_phase_trial_count",
        "clinical_evidence_score",
        "activity_count",
        "indication_count",
        "drugcentral_evidence_score",
    ]
    for column in fill_zero_columns:
        if column in kb.columns:
            kb[column] = kb[column].fillna(0)

    for column in kb.columns:
        if kb[column].dtype == object:
            kb[column] = kb[column].fillna("")

    kb["drug_target_score"] = kb.apply(
        lambda row: max(
            1.0 if str(row.get("mechanism_of_action", "")).strip() else 0.0,
            min(float(row.get("dgidb_interaction_score", 0) or 0), 1.0),
            1.0 if row.get("activity_count", 0) > 0 else 0.0,
        ),
        axis=1,
    )
    kb["approval_or_phase_score"] = kb["max_phase"].apply(phase_score)
    kb["clinical_score"] = kb.apply(clinical_score, axis=1)
    kb["literature_score"] = kb["pubmed_count"].apply(literature_score)
    kb["external_crosscheck_score"] = float(external.get("external_crosscheck_score", 0) or 0)
    kb["opentargets_top_diseases"] = external.get("top_opentargets_diseases", "")
    kb["uniprot_accession"] = uniprot.get("uniprot_accession", "")
    kb["protein_name"] = uniprot.get("protein_name", "")

    kb["final_ranking_score"] = (
        0.25 * kb["drug_target_score"]
        + 0.15 * kb["approval_or_phase_score"]
        + 0.15 * kb["openfda_evidence_score"]
        + 0.15 * kb["clinical_score"]
        + 0.10 * kb["literature_score"]
        + 0.10 * kb["drugcentral_evidence_score"]
        + 0.10 * kb["external_crosscheck_score"]
    ).round(4)

    kb["source_references"] = kb.apply(
        lambda row: " | ".join(
            source
            for source, present in [
                ("ChEMBL", bool(str(row.get("molecule_chembl_id", "")).strip())),
                ("DGIdb", row.get("dgidb_interaction_score", 0) > 0),
                ("openFDA", row.get("openfda_label_count", 0) > 0),
                ("PubMed", row.get("pubmed_count", 0) > 0),
                ("ClinicalTrials.gov", row.get("clinical_trial_count", 0) > 0),
                ("DrugCentral", row.get("activity_count", 0) > 0),
                ("Open Targets", bool(row.get("opentargets_top_diseases", ""))),
                ("UniProt", bool(row.get("uniprot_accession", ""))),
            ]
            if present
        ),
        axis=1,
    )
    kb["evidence_summary_text"] = kb.apply(evidence_summary, axis=1)

    output_columns = [
        "target_name",
        "drug_name",
        "molecule_chembl_id",
        "action_type",
        "mechanism_of_action",
        "approval_status",
        "max_phase",
        "drug_target_score",
        "approval_or_phase_score",
        "openfda_evidence_score",
        "clinical_score",
        "literature_score",
        "drugcentral_evidence_score",
        "external_crosscheck_score",
        "final_ranking_score",
        "dgidb_interaction_score",
        "dgidb_sources",
        "openfda_label_count",
        "openfda_indications",
        "pubmed_count",
        "top_pubmed_titles",
        "clinical_trial_count",
        "active_trial_count",
        "late_phase_trial_count",
        "top_trial_titles",
        "struct_id",
        "drugcentral_name",
        "drugcentral_top_indications",
        "uniprot_accession",
        "protein_name",
        "opentargets_top_diseases",
        "source_references",
        "evidence_summary_text",
    ]
    output_columns = [column for column in output_columns if column in kb.columns]
    return kb[output_columns].sort_values("final_ranking_score", ascending=False).reset_index(drop=True)


def write_chunks(kb: pd.DataFrame) -> None:
    with CHUNKS_FILE.open("w") as f:
        for index, row in kb.iterrows():
            chunk = {
                "id": f"{TARGET_NAME.lower()}-{index + 1:03d}-{normalize_name(row['drug_name']).lower()}",
                "text": row["evidence_summary_text"],
                "metadata": {
                    "target_name": row["target_name"],
                    "drug_name": row["drug_name"],
                    "final_ranking_score": float(row["final_ranking_score"]),
                    "sources": row["source_references"],
                },
            }
            f.write(json.dumps(chunk) + "\n")


def main() -> None:
    kb = build_knowledge_base()
    kb.to_csv(KNOWLEDGE_BASE_FILE, index=False)
    write_chunks(kb)

    print("EGFR therapeutic strategy knowledge base built")
    print("=" * 70)
    print("Rows:", len(kb))
    print("Knowledge base:", KNOWLEDGE_BASE_FILE)
    print("Chunks:", CHUNKS_FILE)
    print(kb[["drug_name", "final_ranking_score", "source_references"]].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
