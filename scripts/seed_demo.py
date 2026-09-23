#!/usr/bin/env python3
"""生成演示数据：创作者、真实 mp4 视频、互动行为，并重建协同过滤。

用法：
    python3 -m scripts.seed_demo          # 独立运行
    python3 run.py --seed-demo            # 起服务前注入演示数据

真实 mp4 由 ffmpeg 的 testsrc 滤镜现场合成（体积小、时长可控），
因此无需往仓库里塞二进制测试资产。
"""

from __future__ import annotations

import hashlib
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import config, media  # noqa: E402
from server.app import Application  # noqa: E402

# (handle, display)
CREATORS = [
    ("foodie_lin", "林小厨"),
    ("pet_daily", "毛孩子日记"),
    ("travel_kai", "阿凯在路上"),
    ("fit_zhou", "周教练"),
    ("book_wang", "王老师读书"),
]

# (文案, 标签, 时长秒)
VIDEOS = [
    ("3分钟搞定深夜食堂 #美食 #家常菜", ["美食", "家常菜"], 6),
    ("这家店的蟹黄面也太顶了 #美食 #探店", ["美食", "探店"], 8),
    ("猫咪第一次见雪的反应 #宠物 #萌宠", ["宠物", "萌宠"], 7),
    ("川西自驾第7天，翻过折多山 #旅行 #自驾", ["旅行", "自驾"], 10),
    ("新手减脂期的一周饮食 #健身 #减脂", ["健身", "减脂"], 9),
    ("《人类简史》到底在讲什么 #读书 #认知", ["读书", "认知"], 11),
    ("空气炸锅版脆皮五花肉 #美食 #懒人食谱", ["美食", "懒人食谱"], 6),
    ("狗狗的睡姿大赏 #宠物 #萌宠", ["宠物", "萌宠"], 7),
]

# 观众：(handle, 兴趣标签, 关注哪个创作者)
VIEWERS = [
    ("viewer_amy", ["美食"], "foodie_lin"),
    ("viewer_ben", ["宠物"], "pet_daily"),
    ("viewer_cara", ["旅行"], "travel_kai"),
    ("viewer_dan", ["美食", "探店"], "foodie_lin"),
]


def synth_mp4(path: str, duration_s: int, size: str = "360x640") -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("需要 ffmpeg 才能生成演示视频")
    subprocess.run(
        [
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc=size={size}:rate=6:duration={duration_s}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            path,
        ],
        capture_output=True, timeout=180, check=True,
    )


def seed(app: Application) -> dict[str, int]:
    db = app.db
    rng = random.Random(20260923)  # 固定种子，保证演示数据可复现

    creator_ids: dict[str, str] = {}
    for handle, display in CREATORS:
        existing = db.get_user_by_handle(handle)
        creator_ids[handle] = (existing or db.create_user(handle, handle, display))["id"]

    # 视频：每 8 小时一条，制造时间梯度供新鲜度特征使用
    video_ids: list[str] = []
    handles = list(creator_ids.items())
    for i, (caption, tags, dur) in enumerate(VIDEOS):
        _handle, creator_id = handles[i % len(handles)]
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as fh:
            tmp_path = fh.name
        dest_abs = ""
        try:
            synth_mp4(tmp_path, dur)
            with open(tmp_path, "rb") as fh:
                digest = hashlib.sha256(fh.read()).hexdigest()
            if db.hash_exists(digest):
                continue  # 幂等：重复播种不会产生重复视频
            video_id = os.urandom(8).hex()
            created_at = time.time() - i * 8 * 3600
            rel = media.storage_path_for(video_id, "seed.mp4", when=created_at)
            dest_abs = os.path.abspath(rel)
            os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
            shutil.move(tmp_path, dest_abs)
            db.create_video(
                video_id=video_id, creator_id=creator_id, caption=caption, tags=tags,
                duration_ms=dur * 1000, width=360, height=640,
                size_bytes=os.path.getsize(dest_abs), sha256=digest, storage_path=rel,
            )
            db.execute("UPDATE videos SET created_at=? WHERE id=?", (created_at, video_id))
            video_ids.append(video_id)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # 观众：注册 + 关注创作者
    viewer_ids: list[tuple[str, list[str]]] = []
    for handle, interests, follow in VIEWERS:
        user = db.get_user_by_handle(handle) or db.create_user(handle, handle, handle)
        db.add_follow(user["id"], creator_ids[follow])
        viewer_ids.append((user["id"], interests))

    # 互动：兴趣匹配的视频高概率点赞/完播，制造可被推荐系统学到的信号
    engagements = 0
    for user_id, interests in viewer_ids:
        for vid in video_ids:
            video = db.get_video(vid)
            if not video:
                continue
            hit = bool(set(video["tags"]) & set(interests))
            roll = rng.random()
            if hit and roll < 0.85:
                for kind in ("view", "complete", "like"):
                    db.add_engagement(user_id, vid, kind, watch_ms=4000)
                    engagements += 1
            elif roll < 0.25:
                db.add_engagement(user_id, vid, "view", watch_ms=1200)
                engagements += 1

    # 给部分视频补足热度，让 pop/qual 特征有区分度
    anon_cache: dict[str, dict] = {}
    for vid in video_ids:
        for _ in range(rng.randint(0, 40)):
            if not db.get_video(vid):
                continue
            handle = f"anon_{rng.randint(0, 20)}"
            fake_user = anon_cache.get(handle) or db.get_user_by_handle(handle)
            if fake_user is None:
                fake_user = db.create_user(handle, handle)
                anon_cache[handle] = fake_user
            db.add_engagement(fake_user["id"], vid, "view", watch_ms=rng.randint(500, 5000))
            engagements += 1
            if rng.random() < 0.25:
                db.add_engagement(fake_user["id"], vid, "like")
                engagements += 1

    pairs = db.rebuild_item_similarity()
    return {
        "users": len(creator_ids) + len(viewer_ids),
        "videos": len(video_ids),
        "engagements": engagements,
        "item_sim_pairs": pairs,
    }


def main() -> int:
    os.makedirs(config.MEDIA_ROOT, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(config.DB_PATH)) or ".", exist_ok=True)
    app = Application()
    info = seed(app)
    print("演示数据写入完成：")
    for k, v in info.items():
        print(f"  {k}: {v}")
    for handle, _ in CREATORS[:1] + VIEWERS[:1]:
        u = app.db.get_user_by_handle(handle)
        if u:
            print(f"  观众/创作者 {handle} -> {u['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
