.PHONY: setup test run up down

setup:
	pip install -r requirements.txt

test:
	pytest tests/

up:
	docker-compose up --build

down:
	docker-compose down
