# ClauseLens — the <5 command developer interface.
.DEFAULT_GOAL := help
.PHONY: help install dev test lint typecheck eval fetch-samples docker-build deploy

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install:  ## Install backend with all extras + dev tools
	pip install -e ".[rag,ocr,pg,dev]"

dev:  ## Run the API locally with hot reload (http://localhost:8000)
	uvicorn app.main:app --reload --app-dir backend --port 8000

test:  ## Run the pytest suite
	pytest -q

lint:  ## Lint with ruff
	ruff check backend evals

typecheck:  ## Static type check with mypy
	mypy backend/app

eval:  ## Run the LLM-as-Judge eval harness and print the scorecard
	python evals/run_evals.py

fetch-samples:  ## Download PUBLIC sample contracts (CUAD / SEC EDGAR)
	python scripts/fetch_samples.py

docker-build:  ## Build the deployment container
	docker build -t clauselens:latest .

deploy:  ## Print HF Space deploy instructions
	@echo "See README 'How to deploy' — push to a Hugging Face Space (Docker SDK)."
