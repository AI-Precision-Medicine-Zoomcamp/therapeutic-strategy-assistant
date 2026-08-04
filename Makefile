.PHONY: setup test index eval db-init db-summary run-api run-ui up down telemetry

setup:
	uv sync

test:
	uv run pytest tests/

index:
	uv run python ingestion/index_to_vectordb.py

eval:
	uv run python evaluation/retrieval_eval.py

db-init:
	uv run python -m monitoring.telemetry

db-summary:
	uv run python -c "from monitoring.telemetry import monitoring_summary; print(monitoring_summary())"

run-api:
	uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

run-ui:
	uv run streamlit run frontend/streamlit_app.py --server.address 127.0.0.1 --server.port 8501

up:
	docker compose up --build

down:
	docker compose down

telemetry:
	uv run python -c "from monitoring.telemetry import monitoring_summary; print(monitoring_summary())"
