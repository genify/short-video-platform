.PHONY: help test test-recommend test-media test-api run demo clean

PY ?= python3
PORT ?= 8080

help:
	@echo "短视频平台 MVP —— 可用目标"
	@echo "  make test            跑全部回归测试（86 项）"
	@echo "  make test-recommend  只跑推荐引擎单测"
	@echo "  make test-media      只跑上传链路单测"
	@echo "  make test-api        只跑端到端 HTTP 测试"
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

run:
	$(PY) run.py --port $(PORT)

demo:
	$(PY) run.py --port $(PORT) --seed-demo

clean:
	rm -rf var/ __pycache__ */__pycache__ */*/__pycache__
