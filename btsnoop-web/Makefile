.PHONY: dev backend frontend test docker clean

# 开发模式：同时启动前后端
dev:
	@echo "Starting backend on :8000 and frontend on :5173..."
	@make backend & make frontend

backend:
	cd backend && python3 server.py

frontend:
	cd frontend && npm run dev

# 测试
test: test-backend test-frontend

test-backend:
	cd backend && python3 -m pytest tests/ -v

test-frontend:
	cd frontend && npm test

# Docker
docker:
	docker-compose up --build

docker-stop:
	docker-compose down

# 清理
clean:
	rm -rf frontend/dist frontend/node_modules backend/__pycache__ backend/parser/__pycache__
