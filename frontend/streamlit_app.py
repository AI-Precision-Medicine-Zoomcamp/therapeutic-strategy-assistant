"""Streamlit UI for the multi-target Therapeutic Strategy Assistant."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.rag_pipeline import SUPPORTED_TARGETS, answer_question  # noqa: E402
from monitoring.telemetry import log_feedback, log_interaction  # noqa: E402


TARGET_DISPLAY_NAMES = {
    "EGFR": "EGFR",
    "ERBB2": "HER2 / ERBB2",
    "BRAF": "BRAF",
    "ALK": "ALK",
    "KRAS": "KRAS",
    "VEGFA": "VEGFA",
    "MET": "MET",
    "PIK3CA": "PIK3CA",
}

EXAMPLE_QUESTIONS = [
    "Which approved therapies are linked to EGFR?",
    "What evidence supports sotorasib as a KRAS therapy?",
    "Which BRAF drugs have strong clinical or FDA evidence?",
    "What evidence exists for ALK-targeted therapies?",
    "Which HER2 therapies appear in the knowledge base?",
]

TARGET_ALIASES = {
    "HER2": "ERBB2",
    "ERBB2": "ERBB2",
    "EGFR": "EGFR",
    "BRAF": "BRAF",
    "ALK": "ALK",
    "KRAS": "KRAS",
    "VEGFA": "VEGFA",
    "VEGF-A": "VEGFA",
    "MET": "MET",
    "PIK3CA": "PIK3CA",
}


def configure_page() -> None:
    st.set_page_config(
        page_title="Therapeutic Strategy Assistant",
        page_icon="",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 1180px;
        }
        [data-testid="stSidebar"] {
            background: #f8fafc;
            border-right: 1px solid #e5e7eb;
        }
        .metric-row {
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 0.8rem 0.9rem;
            background: #ffffff;
        }
        .small-muted {
            color: #64748b;
            font-size: 0.9rem;
        }
        .evidence-meta {
            color: #475569;
            font-size: 0.92rem;
            line-height: 1.45;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def display_target_options() -> dict[str, str | None]:
    options: dict[str, str | None] = {"All targets": None}
    for target in sorted(SUPPORTED_TARGETS):
        options[TARGET_DISPLAY_NAMES.get(target, target)] = target
    return options


def render_sidebar() -> tuple[str | None, int, bool]:
    st.sidebar.title("Controls")
    target_options = display_target_options()
    selected_target_label = st.sidebar.selectbox("Target", list(target_options.keys()))
    top_k = st.sidebar.slider("Evidence chunks", min_value=1, max_value=10, value=5, step=1)
    include_prompt = st.sidebar.toggle("Show generated prompt", value=False)

    st.sidebar.divider()
    st.sidebar.caption("Supported targets")
    st.sidebar.write(", ".join(TARGET_DISPLAY_NAMES.get(target, target) for target in sorted(SUPPORTED_TARGETS)))

    return target_options[selected_target_label], top_k, include_prompt


def infer_target_from_question(question: str) -> str | None:
    """Infer a target filter when the user asks about one supported target."""
    matches = []
    for alias, target in TARGET_ALIASES.items():
        pattern = rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])"
        if re.search(pattern, question, flags=re.IGNORECASE):
            matches.append(target)

    unique_matches = sorted(set(matches))
    if len(unique_matches) == 1:
        return unique_matches[0]
    return None


def resolve_target_filter(question: str, selected_target: str | None) -> tuple[str | None, str | None]:
    if selected_target:
        return selected_target, None

    inferred_target = infer_target_from_question(question)
    if inferred_target:
        return inferred_target, (
            f"Auto-applied target filter: {TARGET_DISPLAY_NAMES.get(inferred_target, inferred_target)}. "
            "Choose a specific target in the sidebar to override this."
        )

    return None, None


def render_llm_mode_notice() -> None:
    if os.getenv("OPENAI_API_KEY"):
        st.success("LLM answer generation is enabled.")
        return

    st.warning(
        "Evidence-only mode: `OPENAI_API_KEY` is not set, so the app retrieves evidence and builds the prompt, "
        "but it does not call the LLM to generate a final narrative answer."
    )


def render_header() -> None:
    st.title("Therapeutic Strategy Assistant")
    st.caption(
        "Evidence-grounded research support for matching biomedical targets to existing therapies."
    )

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Targets", len(SUPPORTED_TARGETS))
    with col_b:
        st.metric("Knowledge Base", "207 rows")
    with col_c:
        st.metric("Chunks Indexed", "207")

    st.info(
        "Research support only. This tool summarizes retrieved biomedical evidence and does not provide medical advice."
    )
    render_llm_mode_notice()


def render_question_input() -> str:
    default_question = EXAMPLE_QUESTIONS[0]
    selected_example = st.selectbox("Example question", EXAMPLE_QUESTIONS)
    question = st.text_area(
        "Question",
        value=selected_example or default_question,
        height=110,
        placeholder="Ask about a target, drug, mechanism, clinical evidence, or evidence gap.",
    )
    return question.strip()


def metadata_value(metadata: dict[str, Any], key: str, fallback: str = "Not available") -> str:
    value = metadata.get(key)
    if value is None or str(value).strip() == "":
        return fallback
    return str(value)


def render_evidence(response: Any) -> None:
    st.subheader("Retrieved Evidence")
    if not response.retrieved_chunks:
        st.warning("No evidence chunks were retrieved.")
        return

    for index, chunk in enumerate(response.retrieved_chunks, start=1):
        metadata = chunk.metadata
        target = metadata_value(metadata, "target_symbol")
        drug = metadata_value(metadata, "drug_name")
        evidence_strength = metadata_value(metadata, "evidence_strength")
        evidence_score = metadata_value(metadata, "evidence_score")
        approval_status = metadata_value(metadata, "approval_status")
        source = metadata_value(metadata, "source")
        distance = "Not available" if chunk.distance is None else f"{chunk.distance:.4f}"

        title = f"{index}. {target} - {drug}"
        with st.expander(title, expanded=index <= 3):
            st.markdown(
                f"""
                <div class="evidence-meta">
                <strong>Evidence strength:</strong> {evidence_strength}<br>
                <strong>Evidence score:</strong> {evidence_score}<br>
                <strong>Approval status:</strong> {approval_status}<br>
                <strong>Source:</strong> {source}<br>
                <strong>Vector distance:</strong> {distance}<br>
                <strong>Chunk ID:</strong> {chunk.id}
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.write(chunk.text)


def render_answer(response: Any) -> None:
    st.subheader("Answer")
    if response.used_llm:
        st.write(response.answer)
    else:
        st.warning(
            "The generated-answer step was skipped because `OPENAI_API_KEY` is not set. "
            "The evidence below is still retrieved from ChromaDB and can be used to inspect the result."
        )
        st.write(response.answer)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.caption(f"Model: {response.model}")
    with col_b:
        st.caption(f"LLM used: {'yes' if response.used_llm else 'no'}")
    with col_c:
        st.caption(f"Target filter: {response.target_filter or 'all'}")

    st.caption(f"Conversation ID: {response.conversation_id}")
    st.caption(f"Response time: {response.response_time:.2f}s")
    st.caption(
        f"Tokens: {response.total_tokens} total "
        f"({response.prompt_tokens} prompt, {response.completion_tokens} completion)"
    )
    st.caption(f"Estimated cost: ${response.estimated_cost_usd:.6f}")
    st.caption(f"Evaluation: {response.evaluation.relevance} - {response.evaluation.explanation}")


def render_prompt(response: Any) -> None:
    st.subheader("Generated Prompt")
    system_prompt = response.prompt.get("system", "")
    user_prompt = response.prompt.get("user", "")

    with st.expander("System prompt"):
        st.code(system_prompt, language="text")
    with st.expander("User prompt"):
        st.code(user_prompt, language="text")


def render_feedback(conversation_id: str) -> None:
    st.subheader("Feedback")
    col_up, col_down = st.columns(2)

    with col_up:
        if st.button("Helpful (+1)", key=f"feedback-up-{conversation_id}"):
            try:
                log_feedback(conversation_id=conversation_id, rating=1, source="streamlit")
                st.success("Feedback saved.")
            except Exception as exc:
                st.error(f"Unable to save feedback: {exc}")

    with col_down:
        if st.button("Not helpful (-1)", key=f"feedback-down-{conversation_id}"):
            try:
                log_feedback(conversation_id=conversation_id, rating=-1, source="streamlit")
                st.success("Feedback saved.")
            except Exception as exc:
                st.error(f"Unable to save feedback: {exc}")


def main() -> None:
    configure_page()
    target_symbol, top_k, include_prompt = render_sidebar()
    render_header()

    question = render_question_input()
    submitted = st.button("Ask", type="primary", use_container_width=False)

    if not submitted:
        return

    if len(question) < 3:
        st.error("Enter a question with at least 3 characters.")
        return

    effective_target_symbol, target_notice = resolve_target_filter(question, target_symbol)
    if target_notice:
        st.info(target_notice)

    with st.spinner("Retrieving evidence and building answer..."):
        try:
            response = answer_question(
                question=question,
                target_symbol=effective_target_symbol,
                top_k=top_k,
            )
        except Exception as exc:
            st.error(f"Unable to answer the question: {exc}")
            return

    try:
        log_interaction(response, source="streamlit")
    except Exception as exc:
        st.warning(f"Answer generated, but the database record could not be saved: {exc}")

    answer_tab, evidence_tab, prompt_tab, feedback_tab = st.tabs(["Answer", "Evidence", "Prompt", "Feedback"])
    with answer_tab:
        render_answer(response)
    with evidence_tab:
        render_evidence(response)
    with prompt_tab:
        if include_prompt:
            render_prompt(response)
        else:
            st.caption("Enable 'Show generated prompt' in the sidebar to inspect the prompt.")
    with feedback_tab:
        render_feedback(response.conversation_id)


if __name__ == "__main__":
    main()
