.PHONY: install test run docker-build docker-run clean help

help:
	@echo "Доступные команды:"
	@echo "  make install      — установить Python-зависимости"
	@echo "  make test         — прогнать pytest"
	@echo "  make run          — запустить Streamlit локально (http://localhost:8501)"
	@echo "  make docker-build — собрать Docker-образ"
	@echo "  make docker-run   — запустить контейнер (http://localhost:8501)"
	@echo "  make clean        — почистить кеш Python и pytest"

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
