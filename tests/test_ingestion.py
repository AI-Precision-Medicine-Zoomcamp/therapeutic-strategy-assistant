import pytest

from ingestion.index_to_vectordb import normalize_metadata_value, validate_chunks


def test_normalize_metadata_value_handles_none_and_lists():
    assert normalize_metadata_value(None) == ""
    assert normalize_metadata_value(["a", "b"]) == "['a', 'b']"
    assert normalize_metadata_value(3) == 3


def test_validate_chunks_rejects_empty_input():
    with pytest.raises(ValueError, match="No chunks found"):
        validate_chunks([])


def test_validate_chunks_requires_id_text_and_metadata():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_chunks([{"id": "chunk-1", "text": "missing metadata"}])
