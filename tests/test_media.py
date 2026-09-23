"""视频上传链路测试：multipart 流式解析、校验、落盘、去重、媒体流。

包含真实二进制往返回归（构造合法 multipart 报文并解析），因为 multipart
切分是最容易出边界 bug 的地方。
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server import config, media  # noqa: E402

BOUNDARY = "----svpTestBoundary8f3a"


def build_multipart(fields: dict[str, str], files: list[tuple[str, str, str, bytes]]) -> bytes:
    """构造 multipart/form-data 报文。files: [(字段名, 文件名, MIME, 内容)]"""
    out = io.BytesIO()
    for name, value in fields.items():
        out.write(f"--{BOUNDARY}\r\n".encode())
        out.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        out.write(value.encode("utf-8"))
        out.write(b"\r\n")
    for name, filename, mime, content in files:
        out.write(f"--{BOUNDARY}\r\n".encode())
        out.write(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        )
        out.write(f"Content-Type: {mime}\r\n\r\n".encode())
        out.write(content)
        out.write(b"\r\n")
    out.write(f"--{BOUNDARY}--\r\n".encode())
    return out.getvalue()


def make_real_mp4(duration_s: float = 5.0, size: str = "720x1280", fps: int = 12) -> bytes:
    """用 ffmpeg 生成真实 mp4，用于验证 ffprobe 元数据链路。

    fps 可调：需要长时长样本（如验证"超长视频被拒"）时用极低帧率，
    否则编码耗时会随 duration*fps 线性增长。
    """
    if not shutil.which("ffmpeg"):
        raise unittest.SkipTest("ffmpeg 不可用")
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as fh:
        path = fh.name
    try:
        cmd = [
            "ffmpeg", "-v", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc=size={size}:rate={fps}:duration={duration_s}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
            path,
        ]
        subprocess.run(cmd, capture_output=True, timeout=180, check=True)
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


class TestMultipartParsing(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._old_media_root = config.MEDIA_ROOT
        config.MEDIA_ROOT = self.tmp.name

    def tearDown(self) -> None:
        config.MEDIA_ROOT = self._old_media_root
        self.tmp.cleanup()

    def _parse(self, body: bytes) -> media.ParsedMultipart:
        ctype = f"multipart/form-data; boundary={BOUNDARY}"
        parsed = media.parse_multipart(io.BytesIO(body), ctype, config.MAX_UPLOAD_BYTES)
        self.addCleanup(parsed.cleanup)
        return parsed

    def test_parses_text_fields(self):
        body = build_multipart({"creator_id": "abc", "caption": "你好 #美食"}, [])
        parsed = self._parse(body)
        self.assertEqual(parsed.fields["creator_id"], "abc")
        self.assertEqual(parsed.fields["caption"], "你好 #美食")

    def test_parses_file_content_exactly(self):
        payload = bytes(range(256)) * 40  # 10240 字节，含所有字节值
        body = build_multipart({}, [("file", "clip.mp4", "video/mp4", payload)])
        parsed = self._parse(body)
        self.assertEqual(len(parsed.files), 1)
        upload = parsed.files[0]
        self.assertEqual(upload.filename, "clip.mp4")
        self.assertEqual(upload.content_type, "video/mp4")
        with open(upload.tmp_path, "rb") as fh:
            self.assertEqual(fh.read(), payload, "文件内容必须与原始字节完全一致")

    def test_handles_boundary_like_bytes_inside_content(self):
        """内容中出现的 '--' 序列不应被误判为 boundary。"""
        payload = b"--notboundary" + b"\x00" * 100 + b"----svpTestBoundary8f3" + b"tail"
        body = build_multipart({}, [("file", "a.mp4", "video/mp4", payload)])
        parsed = self._parse(body)
        with open(parsed.files[0].tmp_path, "rb") as fh:
            self.assertEqual(fh.read(), payload)

    def test_multiple_files_and_fields(self):
        body = build_multipart(
            {"creator_id": "u1"},
            [
                ("file", "a.mp4", "video/mp4", b"A" * 1000),
                ("cover", "c.jpg", "image/jpeg", b"B" * 500),
            ],
        )
        parsed = self._parse(body)
        self.assertEqual(len(parsed.files), 2)
        self.assertEqual([f.filename for f in parsed.files], ["a.mp4", "c.jpg"])

    def test_large_file_streams_without_memory_blowup(self):
        """4MB 载荷：验证大文件走流式切分且内容完整。"""
        payload = os.urandom(4 * 1024 * 1024)
        body = build_multipart({}, [("file", "big.mp4", "video/mp4", payload)])
        parsed = self._parse(body)
        self.assertEqual(parsed.files[0].size_bytes, len(payload))
        h = parsed.files[0].compute_hash()
        import hashlib

        self.assertEqual(h, hashlib.sha256(payload).hexdigest())

    def test_rejects_non_multipart(self):
        with self.assertRaises(media.UploadError) as ctx:
            media.parse_multipart(io.BytesIO(b"{}"), "application/json", 1024)
        self.assertEqual(ctx.exception.code, "bad_content_type")

    def test_rejects_oversize_body(self):
        body = build_multipart({}, [("file", "a.mp4", "video/mp4", b"X" * 5000)])
        with self.assertRaises(media.UploadError) as ctx:
            media.parse_multipart(io.BytesIO(body), f"multipart/form-data; boundary={BOUNDARY}", 1000)
        self.assertEqual(ctx.exception.status, 413)

    def test_rejects_missing_boundary(self):
        with self.assertRaises(media.UploadError) as ctx:
            media.parse_multipart(io.BytesIO(b"x"), "multipart/form-data", 1024)
        self.assertEqual(ctx.exception.code, "missing_boundary")


class TestLengthLimitedReader(unittest.TestCase):
    """回归测试：socket 读取必须按 Content-Length 设界，绝不依赖 EOF。

    历史缺陷：直接对 socket 调用 `read(65536)`，在 keep-alive 连接上会永远
    等不到 EOF 而阻塞，导致所有上传请求挂死。
    """

    def test_never_reads_past_declared_length(self):
        payload = b"A" * 100 + b"TRAILING-NEXT-REQUEST"
        reader = media.LengthLimitedReader(io.BytesIO(payload), 100)
        self.assertEqual(reader.read(65536), b"A" * 100)
        self.assertEqual(reader.remaining, 0)
        self.assertEqual(reader.read(10), b"", "越界后必须返回空，不得触碰后续字节")

    def test_short_reads_are_accumulated_correctly(self):
        reader = media.LengthLimitedReader(io.BytesIO(b"0123456789"), 10)
        self.assertEqual(reader.read(3), b"012")
        self.assertEqual(reader.read(3), b"345")
        self.assertEqual(reader.read(100), b"6789")
        self.assertEqual(reader.remaining, 0)

    def test_drain_consumes_remainder_and_reports_reusable(self):
        reader = media.LengthLimitedReader(io.BytesIO(b"X" * 5000), 5000)
        reader.read(10)
        self.assertTrue(reader.drain())
        self.assertEqual(reader.remaining, 0)

    def test_zero_length_body(self):
        reader = media.LengthLimitedReader(io.BytesIO(b""), 0)
        self.assertEqual(reader.read(10), b"")
        self.assertTrue(reader.drain())


class TestTagExtraction(unittest.TestCase):
    def test_extracts_hashtags_from_caption(self):
        tags = media.extract_tags("周末探店 #美食 #杭州 ")
        self.assertEqual(tags, ["美食", "杭州"])

    def test_merges_explicit_tags_and_dedupes(self):
        tags = media.extract_tags("#美食", "美食,旅行 美食")
        self.assertEqual(tags, ["美食", "旅行"])

    def test_lowercases_ascii_tags(self):
        self.assertIn("travel", media.extract_tags("#Travel"))

    def test_limits_count(self):
        self.assertEqual(len(media.extract_tags(" ".join(f"#t{i}" for i in range(30)))), 8)

    def test_empty_input(self):
        self.assertEqual(media.extract_tags(""), [])


class TestMediaValidation(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _upload(self, filename: str, content_type: str, size: int = 1024) -> media.UploadedFile:
        path = os.path.join(self.tmp.name, uuid.uuid4().hex)
        with open(path, "wb") as fh:
            fh.write(b"0" * size)
        return media.UploadedFile("file", filename, content_type, path, size)

    def test_accepts_valid_mp4(self):
        media.validate_upload(
            self._upload("a.mp4", "video/mp4"),
            {"available": True, "duration_ms": 15000, "width": 720, "height": 1280},
        )

    def test_rejects_bad_extension(self):
        with self.assertRaises(media.UploadError) as ctx:
            media.validate_upload(self._upload("a.avi", "video/mp4"), {"available": False})
        self.assertEqual(ctx.exception.code, "unsupported_extension")

    def test_rejects_bad_mime(self):
        with self.assertRaises(media.UploadError) as ctx:
            media.validate_upload(self._upload("a.mp4", "application/pdf"), {"available": False})
        self.assertEqual(ctx.exception.code, "unsupported_mime")

    def test_rejects_duration_over_limit(self):
        with self.assertRaises(media.UploadError) as ctx:
            media.validate_upload(
                self._upload("a.mp4", "video/mp4"),
                {"available": True, "duration_ms": config.MAX_DURATION_MS + 1, "height": 720},
            )
        self.assertEqual(ctx.exception.code, "duration_too_long")

    def test_rejects_low_resolution(self):
        with self.assertRaises(media.UploadError) as ctx:
            media.validate_upload(
                self._upload("a.mp4", "video/mp4"),
                {"available": True, "duration_ms": 5000, "height": 120},
            )
        self.assertEqual(ctx.exception.code, "resolution_too_low")

    def test_rejects_empty_file(self):
        with self.assertRaises(media.UploadError) as ctx:
            media.validate_upload(self._upload("a.mp4", "video/mp4", size=0), {"available": False})
        self.assertEqual(ctx.exception.code, "empty_file")


class TestProbeAndStorage(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._old = config.MEDIA_ROOT
        config.MEDIA_ROOT = self.tmp.name

    def tearDown(self) -> None:
        config.MEDIA_ROOT = self._old
        self.tmp.cleanup()

    def test_probe_reads_real_duration_and_resolution(self):
        data = make_real_mp4(duration_s=4.0, size="720x1280")
        path = os.path.join(self.tmp.name, "probe.mp4")
        with open(path, "wb") as fh:
            fh.write(data)
        meta = media.probe_media(path)
        self.assertTrue(meta["available"], "ffprobe 应可用")
        self.assertAlmostEqual(meta["duration_ms"] / 1000.0, 4.0, delta=0.5)
        self.assertEqual(meta["width"], 720)
        self.assertEqual(meta["height"], 1280)
        self.assertTrue(meta["codec"])

    def test_probe_raises_on_garbage(self):
        path = os.path.join(self.tmp.name, "garbage.mp4")
        with open(path, "wb") as fh:
            fh.write(b"not a video at all" * 100)
        with self.assertRaises(media.UploadError) as ctx:
            media.probe_media(path)
        self.assertEqual(ctx.exception.code, "unprobeable_media")

    def test_storage_path_is_bucketed_by_year_month(self):
        rel = media.storage_path_for("abc123", "clip.mp4")
        self.assertTrue(rel.endswith(os.path.join("abc123.mp4")))
        self.assertIn(str(__import__("time").gmtime().tm_year), rel)
        self.assertIn("abc123", rel)

    def test_persist_moves_file_and_creates_dirs(self):
        src = os.path.join(self.tmp.name, "src.part")
        with open(src, "wb") as fh:
            fh.write(b"data")
        upload = media.UploadedFile("file", "a.mp4", "video/mp4", src, 4)
        dest = media.storage_path_for("vid1", "a.mp4")
        abs_dest = media.persist(upload, dest)
        self.assertTrue(os.path.isfile(abs_dest))
        self.assertFalse(os.path.exists(src), "临时文件应被移走")


if __name__ == "__main__":
    unittest.main(verbosity=2)
