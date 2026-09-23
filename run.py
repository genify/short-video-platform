#!/usr/bin/env python3
"""短视频平台 MVP 启动入口。

    python3 run.py                 # 监听 127.0.0.1:8080
    python3 run.py --port 9000
    python3 run.py --seed-demo     # 生成演示数据（含真实 mp4，需 ffmpeg）
"""

from __future__ import annotations

import argparse
import os
import sys

from server import config
from server.app import Application, serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="短视频平台 MVP")
    parser.add_argument("--host", default=os.environ.get("SVP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SVP_PORT", "8080")))
    parser.add_argument("--db", default=config.DB_PATH)
    parser.add_argument("--media-root", default=config.MEDIA_ROOT)
    parser.add_argument("--seed-demo", action="store_true", help="写入演示数据后启动")
    args = parser.parse_args(argv)

    config.DB_PATH = args.db
    config.MEDIA_ROOT = args.media_root
    os.makedirs(os.path.dirname(os.path.abspath(args.db)) or ".", exist_ok=True)
    os.makedirs(args.media_root, exist_ok=True)

    app = Application()
    if args.seed_demo:
        from scripts.seed_demo import seed

        info = seed(app)
        print(f"[seed] 用户 {info['users']} 个 / 视频 {info['videos']} 个 / 行为 {info['engagements']} 条")

    httpd = serve(args.host, args.port, app)
    print(f"短视频平台 MVP 已启动: http://{args.host}:{args.port}")
    print("推荐流: GET /api/feed?user_id=<uuid>&size=10")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n正在关闭…")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
