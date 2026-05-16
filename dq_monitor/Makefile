.PHONY: install test run docker-build docker-run clean

install:
	pip install -r requirements.txt

test:
	pytest tests/

run:
	streamlit run app/streamlit_app.py

docker-build:
	docker build -t dq-monitor .

docker-run:
	docker run --rm -p 8501:8501 -v $(PWD)/data:/app/data dq-monitor

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache htmlcov .coverage
