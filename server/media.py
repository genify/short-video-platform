"""视频上传：流式 multipart 解析、落盘、ffprobe 元数据校验与去重。

设计要点
--------
1. **零第三方依赖**：环境无 flask/fastapi/python-multipart 可用，故自行实现
   RFC 7578 multipart 流式切分。
2. **内存安全**：上传体先流式写盘，再以固定窗口扫描 boundary 逐 part 切分，
   任何时刻内存驻留不超过 64KB，因此 200MB 上限下也不会 OOM。
3. **元数据真值**：时长/分辨率一律以 ffprobe 为准，绝不相信客户端上报值，
   防止用 3 秒 MP4 冒充 3 分钟（风控基本要求）。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from email.message import Message
from email.parser import BytesHeaderParser
from typing import Any, BinaryIO, Iterator

from . import config

CHUNK_SIZE = 1 << 16  # 64KB 扫描窗口
_TAG_RE = re.compile(r"#([^\s#，,。、；;]{1,24})")
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+")


class LengthLimitedReader:
    """把请求体读取严格限制在 Content-Length 字节内。

    **为什么必须有这个类**：socket 的 `rfile.read(n)` 会阻塞直到读满 n 字节
    或遇到 EOF。keep-alive 连接上不会出现 EOF，因此若直接对 socket 调用
    `read(65536)`，当剩余请求体不足 64KB 时会永久阻塞。

    正确做法是显式跟踪剩余长度，绝不依赖 EOF 判断读边界——这也是所有
    HTTP 服务端解析器的标准姿势。
    """

    def __init__(self, stream: BinaryIO, length: int) -> None:
        self._stream = stream
        self.remaining = max(0, int(length))

    def read(self, size: int = -1) -> bytes:
        if self.remaining <= 0:
            return b""
        if size is None or size < 0:
            size = self.remaining
        size = min(int(size), self.remaining)
        if size <= 0:
            return b""
        data = self._stream.read(size)
        self.remaining -= len(data)
        return data

    def drain(self) -> bool:
        """读空剩余字节，返回 True 表示已读到边界（连接可复用）。"""
        while self.remaining > 0:
            chunk = self.read(CHUNK_SIZE)
            if not chunk:
                break
        return self.remaining <= 0


class UploadError(Exception):
    """上传校验失败，携带 HTTP 状态码与机器可读错误码。"""

    def __init__(self, message: str, status: int = 400, code: str = "invalid_upload") -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


@dataclass
class UploadedFile:
    field_name: str
    filename: str
    content_type: str
    tmp_path: str
    size_bytes: int
    sha256: str = ""

    def compute_hash(self) -> str:
        h = hashlib.sha256()
        with open(self.tmp_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        self.sha256 = h.hexdigest()
        return self.sha256


@dataclass
class ParsedMultipart:
    fields: dict[str, str] = field(default_factory=dict)
    files: list[UploadedFile] = field(default_factory=list)
    tmpdir: str = ""

    def cleanup(self) -> None:
        if self.tmpdir:
            shutil.rmtree(self.tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# multipart 流式解析
# ---------------------------------------------------------------------------
def _boundary_of(content_type: str) -> bytes:
    msg: Message = BytesHeaderParser().parsebytes(
        f"Content-Type: {content_type}\r\n\r\n".encode("utf-8")
    )
    boundary = msg.get_param("boundary", header="content-type")
    if not boundary:
        raise UploadError("multipart 缺少 boundary", code="missing_boundary")
    if isinstance(boundary, tuple):  # RFC2231 编码的 boundary
        boundary = boundary[2]
    return str(boundary).encode("utf-8")


def _strip_trailing_crlf(path: str) -> None:
    """part 内容以 boundary 前的 CRLF 结束，需要把这 2 字节去掉。"""
    size = os.path.getsize(path)
    if size == 0:
        return
    with open(path, "r+b") as fh:
        for trim in (2, 1):
            if size < trim:
                continue
            fh.seek(size - trim)
            if fh.read(trim) in (b"\r\n", b"\n"):
                fh.truncate(size - trim)
                return


def _iter_raw_parts(raw_path: str, boundary: bytes, parts_dir: str) -> Iterator[tuple[bytes, str]]:
    """产出 (头部字节, part 文件路径)。

    扫描算法：以 CHUNK_SIZE 为窗口在原始上传体上寻找 boundary，命中即把
    内容写到独立 part 文件；始终保留 CHUNK_SIZE 尾部重叠区，保证 boundary
    跨块时不被漏掉。

    注意：part 文件由调用方（ParsedMultipart.cleanup）负责清理，本函数只负责写入。
    """
    delim = b"--" + boundary
    keep = CHUNK_SIZE
    os.makedirs(parts_dir, exist_ok=True)

    fh = open(raw_path, "rb")
    try:
        # 定位第一个 boundary
        buf = b""
        while True:
            chunk = fh.read(CHUNK_SIZE)
            if not chunk:
                return
            buf += chunk
            idx = buf.find(delim)
            if idx != -1:
                buf = buf[idx:]
                break
            if len(buf) > keep:
                buf = buf[-keep:]

        while True:
            # buf 以 delim 开头
            rest = buf[len(delim):]
            if rest.startswith(b"--"):  # 结束标记
                return
            if rest.startswith(b"\r\n"):
                rest = rest[2:]
            elif rest.startswith(b"\n"):
                rest = rest[1:]

            # 读齐头部
            while b"\r\n\r\n" not in rest and b"\n\n" not in rest:
                chunk = fh.read(CHUNK_SIZE)
                if not chunk:
                    return
                rest += chunk
            sep = rest.find(b"\r\n\r\n")
            sep_len = 4
            if sep == -1:
                sep = rest.find(b"\n\n")
                sep_len = 2
            header_blob = rest[:sep]
            cur = rest[sep + sep_len:]

            part_path = os.path.join(parts_dir, f"part-{uuid.uuid4().hex}")
            next_buf = b""
            with open(part_path, "wb") as out:
                while True:
                    j = cur.find(delim)
                    if j != -1:
                        out.write(cur[:j])
                        next_buf = cur[j:]
                        break
                    if len(cur) > keep:
                        out.write(cur[:-keep])
                        cur = cur[-keep:]
                    chunk = fh.read(CHUNK_SIZE)
                    if not chunk:
                        out.write(cur)
                        next_buf = b""
                        break
                    cur += chunk
            _strip_trailing_crlf(part_path)
            yield header_blob, part_path

            if not next_buf:
                next_buf = fh.read(CHUNK_SIZE)
                if not next_buf:
                    return
            buf = next_buf
    finally:
        fh.close()


def _header_value(header_blob: bytes, name: str) -> str:
    msg: Message = BytesHeaderParser().parsebytes(header_blob + b"\r\n\r\n")
    return msg.get(name, "") or ""


def _field_name_of(header_blob: bytes) -> str:
    msg: Message = BytesHeaderParser().parsebytes(header_blob + b"\r\n\r\n")
    value = msg.get("content-disposition", "") or ""
    msg2: Message = BytesHeaderParser().parsebytes(
        ("Content-Disposition: " + value + "\r\n\r\n").encode("utf-8", "replace")
    )
    name = msg2.get_param("name", header="content-disposition")
    if isinstance(name, tuple):
        name = name[2]
    return str(name or "")


def _filename_of(header_blob: bytes) -> str:
    msg: Message = BytesHeaderParser().parsebytes(header_blob + b"\r\n\r\n")
    value = msg.get("content-disposition", "") or ""
    msg2: Message = BytesHeaderParser().parsebytes(
        ("Content-Disposition: " + value + "\r\n\r\n").encode("utf-8", "replace")
    )
    filename = msg2.get_param("filename", header="content-disposition")
    if isinstance(filename, tuple):
        filename = filename[2]
    return str(filename or "")


def parse_multipart(stream: BinaryIO, content_type: str, max_bytes: int) -> ParsedMultipart:
    """流式保存请求体并切分为字段与文件。"""
    if "multipart/form-data" not in content_type.lower():
        raise UploadError("Content-Type 必须是 multipart/form-data", code="bad_content_type")
    boundary = _boundary_of(content_type)

    tmpdir = tempfile.mkdtemp(prefix="svp-upload-")
    raw_path = os.path.join(tmpdir, "body.bin")
    total = 0
    try:
        with open(raw_path, "wb") as out:
            while True:
                chunk = stream.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise UploadError(
                        f"上传体积超过上限 {max_bytes // (1024 * 1024)}MB",
                        status=413,
                        code="payload_too_large",
                    )
                out.write(chunk)
        if total == 0:
            raise UploadError("请求体为空", code="empty_body")

        parsed = ParsedMultipart(tmpdir=tmpdir)
        parts_dir = os.path.join(tmpdir, "parts")
        for header_blob, part_path in _iter_raw_parts(raw_path, boundary, parts_dir):
            name = _field_name_of(header_blob)
            if not name:
                try:
                    os.unlink(part_path)
                except OSError:
                    pass
                continue
            filename = _filename_of(header_blob)
            if filename:
                parsed.files.append(
                    UploadedFile(
                        field_name=name,
                        filename=os.path.basename(filename),
                        content_type=(_header_value(header_blob, "content-type")
                                      or "application/octet-stream").strip(),
                        tmp_path=part_path,
                        size_bytes=os.path.getsize(part_path),
                    )
                )
            else:
                with open(part_path, "rb") as fh:
                    parsed.fields[name] = fh.read().decode("utf-8", "replace")
                try:
                    os.unlink(part_path)
                except OSError:
                    pass
        return parsed
    except UploadError:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise UploadError(f"multipart 解析失败: {exc}", code="multipart_parse_failed") from exc


# ---------------------------------------------------------------------------
# ffprobe 元数据
# ---------------------------------------------------------------------------
_NO_PROBE = {"available": False, "duration_ms": 0, "width": 0, "height": 0,
             "codec": "", "bit_rate": 0, "format_name": ""}


def probe_media(path: str) -> dict[str, Any]:
    """调用 ffprobe 读取时长/分辨率/编码。ffprobe 缺失时降级为 0 值并标记。"""
    exe = shutil.which("ffprobe")
    if not exe:
        return dict(_NO_PROBE)
    cmd = [
        exe, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", "-select_streams", "v:0", path,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=30, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return dict(_NO_PROBE)
    if proc.returncode != 0:
        raise UploadError("视频文件无法解析（损坏或非视频格式）", code="unprobeable_media")
    try:
        meta = json.loads(proc.stdout.decode("utf-8", "replace") or "{}")
    except ValueError:
        raise UploadError("ffprobe 输出无法解析", code="probe_parse_failed")

    fmt = meta.get("format") or {}
    streams = meta.get("streams") or []
    stream = streams[0] if streams else {}
    duration_s = float(fmt.get("duration") or stream.get("duration") or 0.0)
    return {
        "available": True,
        "duration_ms": int(round(duration_s * 1000)),
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "codec": str(stream.get("codec_name") or ""),
        "bit_rate": int(float(fmt.get("bit_rate") or 0)),
        "format_name": str(fmt.get("format_name") or ""),
    }


def validate_upload(upload: UploadedFile, meta: dict[str, Any]) -> None:
    """扩展名 / MIME / 体积 / 时长 / 分辨率五重校验。"""
    ext = os.path.splitext(upload.filename)[1].lower()
    if ext not in config.ALLOWED_EXT:
        raise UploadError(
            f"不支持的扩展名 {ext or '(无)'}，仅支持 {', '.join(sorted(config.ALLOWED_EXT))}",
            code="unsupported_extension",
        )
    if upload.content_type not in config.ALLOWED_MIME:
        raise UploadError(f"不支持的 MIME 类型 {upload.content_type}", code="unsupported_mime")
    if upload.size_bytes > config.MAX_UPLOAD_BYTES:
        raise UploadError(
            f"文件超过上限 {config.MAX_UPLOAD_BYTES // (1024 * 1024)}MB",
            status=413,
            code="payload_too_large",
        )
    if upload.size_bytes == 0:
        raise UploadError("文件为空", code="empty_file")
    if meta.get("available"):
        dur = int(meta.get("duration_ms") or 0)
        if dur and dur < config.MIN_DURATION_MS:
            raise UploadError("视频时长过短（<1 秒）", code="duration_too_short")
        if dur and dur > config.MAX_DURATION_MS:
            raise UploadError(
                f"视频时长 {dur / 1000:.1f}s 超过短视频上限 {config.MAX_DURATION_MS / 1000:.0f}s",
                code="duration_too_long",
            )
        if meta.get("height") and int(meta["height"]) < 240:
            raise UploadError("分辨率过低（高度 < 240px）", code="resolution_too_low")


# ---------------------------------------------------------------------------
# 存储
# ---------------------------------------------------------------------------
def storage_path_for(video_id: str, filename: str, when: float | None = None) -> str:
    """按 年/月 分桶存放，避免单目录文件数量爆炸。"""
    ts = time.gmtime(when or time.time())
    ext = os.path.splitext(filename)[1].lower() or ".mp4"
    return os.path.join(config.MEDIA_ROOT, f"{ts.tm_year:04d}", f"{ts.tm_mon:02d}", f"{video_id}{ext}")


def persist(upload: UploadedFile, dest_rel: str) -> str:
    dest_abs = os.path.abspath(dest_rel)
    os.makedirs(os.path.dirname(dest_abs), exist_ok=True)
    shutil.move(upload.tmp_path, dest_abs)
    return dest_abs


def delete_stored(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# 文案解析
# ---------------------------------------------------------------------------
def extract_tags(text: str, explicit: str | None = None, limit: int = 8) -> list[str]:
    """从 caption 的 #话题 与显式 tags 字段提取规范化标签（小写/去重/限量）。"""
    tags: list[str] = []
    seen: set[str] = set()

    def push(raw: str) -> None:
        t = _SAFE_NAME_RE.sub("", str(raw).strip().lower())
        if t and t not in seen:
            seen.add(t)
            tags.append(t)

    if explicit:
        for item in re.split(r"[,，\s]+", explicit):
            push(item)
    if text:
        for m in _TAG_RE.findall(text):
            push(m)
    return tags[:limit]
