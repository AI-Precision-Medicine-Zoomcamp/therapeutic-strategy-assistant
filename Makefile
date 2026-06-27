.PHONY: setup test run up down

setup:
	uv sync

test:
	uv run pytest tests/

up:
	docker-compose up --build

down:
	docker-compose down
