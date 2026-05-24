SHELL := /bin/bash

PORT ?= 5000
PID_FILE ?= .auto-cv.pid
LOG_FILE ?= /tmp/auto-cv-app-$(PORT).log

.PHONY: help install run start stop restart status logs check py-check js-check clean

help:
	@echo "Auto-CV Make targets"
	@echo ""
	@echo "  make run      Run the app in the foreground on port $(PORT)"
	@echo "  make start    Start the app in the background on port $(PORT)"
	@echo "  make stop     Stop the background app and anything listening on port $(PORT)"
	@echo "  make restart  Stop then start the app"
	@echo "  make status   Show processes listening on port $(PORT)"
	@echo "  make logs     Follow the app log"
	@echo "  make check    Run Python compile check and JS syntax check"
	@echo "  make install  Install Python dependencies"
	@echo "  make clean    Remove local runtime files"

install:
	pip install -r requirements.txt

run:
	python main.py

start:
	@if ss -ltnp | rg -q ':$(PORT)\b'; then \
		echo "Port $(PORT) is already in use:"; \
		ss -ltnp | rg ':$(PORT)\b'; \
		echo "Use 'make stop' first, or run 'make status'."; \
		exit 1; \
	fi
	@echo "Starting Auto-CV on http://127.0.0.1:$(PORT) ..."
	@nohup python main.py > "$(LOG_FILE)" 2>&1 & echo $$! > "$(PID_FILE)"
	@sleep 1
	@$(MAKE) --no-print-directory status
	@echo "Logs: $(LOG_FILE)"

stop:
	@if [ -f "$(PID_FILE)" ]; then \
		pid=$$(cat "$(PID_FILE)"); \
		if kill -0 "$$pid" 2>/dev/null; then \
			echo "Stopping PID $$pid from $(PID_FILE)"; \
			kill "$$pid" || true; \
		fi; \
		rm -f "$(PID_FILE)"; \
	fi
	@pids=$$(ss -ltnp | rg ':$(PORT)\b' | rg -o 'pid=[0-9]+' | cut -d= -f2 | sort -u); \
	if [ -n "$$pids" ]; then \
		echo "Stopping process(es) on port $(PORT): $$pids"; \
		kill $$pids || true; \
	else \
		echo "No process is listening on port $(PORT)."; \
	fi

restart: stop start

status:
	@ss -ltnp | rg ':$(PORT)\b' || echo "No process is listening on port $(PORT)."

logs:
	@touch "$(LOG_FILE)"
	tail -f "$(LOG_FILE)"

check: py-check js-check

py-check:
	python -m compileall main.py src

js-check:
	node --check static/interview.js

clean:
	rm -f "$(PID_FILE)"
	rm -f /tmp/auto-cv-app-*.log
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
