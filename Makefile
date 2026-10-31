.PHONY: install download discover run test dashboard clean docker-up docker-down

install:
	pip install --upgrade pip
	pip install -r requirements.txt

download:
	python -m src.pipeline.orchestrator download

discover:
	python -m src.pipeline.orchestrator discover

run:
	python -m src.pipeline.orchestrator run --coins BTC,ETH,SOL

test:
	pytest tests/ -v

dashboard:
	streamlit run src/dashboard/app.py

docker-up:
	docker compose up --build

docker-down:
	docker compose down

clean:
	rm -rf data/bronze/* data/silver/* data/gold/* data/observability/reports/*
