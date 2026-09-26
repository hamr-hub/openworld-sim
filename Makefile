.PHONY: help install backend frontend build test headless clean

help:
	@echo "OpenWorld Sim — make targets"
	@echo "  make install    - install backend (editable) + frontend deps"
	@echo "  make backend    - run FastAPI server (port 8000)"
	@echo "  make frontend   - run Vite dev server (port 5173)"
	@echo "  make build      - build frontend (npm run build)"
	@echo "  make test       - run pytest"
	@echo "  make headless   - run 200-tick headless simulation"
	@echo "  make clean      - remove __pycache__, .pytest_cache, frontend/dist"

install:
	pip install -e ./backend[test]
	cd frontend && npm install

backend:
	cd backend && uvicorn openworld.server:app --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

test:
	cd backend && PYTHONPATH=. python -m pytest -q

headless:
	cd backend && PYTHONPATH=. python -m openworld.headless --ticks 200

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf backend/.pytest_cache frontend/dist frontend/node_modules/.vite
	@echo "cleaned"