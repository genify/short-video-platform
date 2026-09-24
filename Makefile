.PHONY: help test test-recommend test-media test-api test-auth test-exploration test-evaluate \
        evaluate smoke run demo clean

PY ?= python3
PORT ?= 8080

help:
	@echo "短视频平台 MVP —— 可用目标"
	@echo "  make test            跑全部回归测试"
	@echo "  make test-recommend  只跑推荐引擎单测"
	@echo "  make test-media      只跑上传链路单测"
	@echo "  make test-api        只跑端到端 HTTP 测试"
	@echo "  make test-auth       只跑鉴权与限流测试（严格限流档）"
	@echo "  make test-exploration 只跑探索位行为测试（AC-F-08/08b/08c）"
	@echo "  make test-evaluate   只跑离线评测器一致性测试"
	@echo "  make evaluate        推荐权重离线校准（NDCG@K）并写报告"
	@echo "  make smoke           端到端冒烟测试（真实 HTTP：上传 + 推荐流）"
	@echo "  make run             启动服务（$(PORT) 端口）"
	@echo "  make demo            注入演示数据并启动"
	@echo "  make clean           清理数据库、媒体与缓存"

test:
	$(PY) -m unittest discover -s tests -t . -v

test-recommend:
	$(PY) -m unittest tests.test_recommend -v

test-media:
	$(PY) -m unittest tests.test_media -v

test-api:
	$(PY) -m unittest tests.test_api -v

test-auth:
	$(PY) -m unittest tests.test_auth -v

test-exploration:
	$(PY) -m unittest tests.test_exploration -v

test-evaluate:
	$(PY) -m unittest tests.test_evaluate -v

evaluate:
	$(PY) scripts/evaluate.py --out docs/10-recommendation-weight-calibration.md

smoke:
	$(PY) scripts/smoke.py

run:
	$(PY) run.py --port $(PORT)

demo:
	$(PY) run.py --port $(PORT) --seed-demo

clean:
	rm -rf var/ __pycache__ */__pycache__ */*/__pycache__
