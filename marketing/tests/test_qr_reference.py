"""参考比对：用独立实现（api.qrserver.com 渲染的 PNG）验证本编码器。

原理：ISO/IEC 18004 允许编码器在 8 个掩码中自选一个，任一合法掩码解码结果相同，
      因此「掩码选择」不构成可移植性约束。本测试对每个测试串：
        ① 用本编码器分别以 mask=0..7 生成 8 个矩阵；
        ② 下载参考实现的 PNG，还原出参考矩阵；
        ③ 断言参考矩阵必须与本编码器的某个掩码矩阵**逐格完全相等**。
      这同时验证了：数据码字、RS 纠错、交织、格式信息位、版本信息位、模块布点。
      另外报告本编码器自动选出的掩码与参考实现是否一致（不一致不判失败，只记录）。

离线（网络不可用）或缺少 PIL 时：skipTest，并打印跳过原因。
"""

from __future__ import annotations

import io
import sys
import unittest
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "marketing" / "scripts"))

import qr  # noqa: E402

REF_ENDPOINT = "https://api.qrserver.com/v1/create-qr-code/"

# 必须强制字节模式（含小写字母/符号），否则参考实现会自行选择数字/字母数字模式，不可比
_LONG_BYTES = ("https://lcnn.example.com/?utm_source=wechat&utm_medium=creator_recruit"
               "&utm_content=" + "/abc-def.ghi?x=1" * 14)  # 全为小写/符号 → 参考实现无法优化分段
TEST_STRINGS = [
    "https://lcnn.example.com/?utm_source=douyin&utm_medium=creator_recruit"
    "&utm_campaign=pro_launch_p1&utm_content=c001&ref=c001",
    "https://lcnn.example.com/s/abc123?utm_source=xiaohongshu&utm_medium=creator_share&v=2",
    _LONG_BYTES,  # 触发高版本（版本 7+，需版本信息位）
]


def _fetch_reference_matrix(data: str, dim: int) -> list[list[int]]:
    """下载参考 PNG 并还原 dim×dim 模块矩阵（qzone=0，每模块 8 像素）。"""
    from PIL import Image  # 仅测试允许依赖 PIL

    size = dim * 8
    url = "%s?%s" % (
        REF_ENDPOINT,
        urllib.parse.urlencode(
            {"data": data, "size": "%dx%d" % (size, size), "ecc": "M", "qzone": "0"}
        ),
    )
    req = urllib.request.Request(url, headers={"User-Agent": "paperclip-marketing-selftest/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status != 200:
            raise urllib.error.URLError("参考端点返回 HTTP %s" % resp.status)
        blob = resp.read()

    img = Image.open(io.BytesIO(blob)).convert("L")
    if img.size != (size, size):
        raise AssertionError("参考 PNG 尺寸异常：%s != %s" % (img.size, (size, size)))
    px = img.load()
    matrix = []
    for y in range(dim):
        row = []
        for x in range(dim):
            # 取每模块中心像素；1=深色（PNG 中暗像素 < 128）
            row.append(1 if px[x * 8 + 4, y * 8 + 4] < 128 else 0)
        matrix.append(row)
    return matrix


def _network_error_reason() -> str | None:
    try:
        from PIL import Image  # noqa: F401
    except Exception as exc:  # pragma: no cover
        return "缺少 PIL（%s），无法还原参考矩阵" % exc
    try:
        req = urllib.request.Request(
            REF_ENDPOINT + "?data=test&size=80x80&ecc=M&qzone=0",
            headers={"User-Agent": "paperclip-marketing-selftest/1.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status != 200:
                return "参考端点返回 HTTP %s" % resp.status
    except Exception as exc:  # pragma: no cover
        return "网络不可用：%s: %s" % (type(exc).__name__, exc)
    return None


class TestQrAgainstReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._skip_reason = _network_error_reason()
        cls.report: list[str] = []

    def _compare(self, data: str) -> None:
        if self._skip_reason:
            self.skipTest("参考比对被跳过：%s" % self._skip_reason)

        declared_version = qr.version_of(data)
        dim = declared_version * 4 + 17
        candidates = {}
        for mask in range(8):
            candidates[mask] = qr.encode(data, "M", mask=mask)
            self.assertEqual(len(candidates[mask]), dim)

        reference = _fetch_reference_matrix(data, dim)

        matched = [m for m, mat in candidates.items() if mat == reference]
        self.assertTrue(
            matched,
            "参考矩阵与本编码器 8 个掩码矩阵均不相等（version=%d, dim=%d）——编码链路存在真实缺陷"
            % (declared_version, dim),
        )

        auto = qr.encode(data, "M")
        auto_mask = None
        for m, mat in candidates.items():
            if mat == auto:
                auto_mask = m
                break
        self.assertIsNotNone(auto_mask, "自动选掩码的矩阵必须等于某个固定掩码矩阵")

        self.report.append(
            "dim=%d(version=%d) ref_mask=%s auto_mask=%s 一致=%s | 样本=%s…"
            % (
                dim,
                declared_version,
                matched,
                auto_mask,
                auto_mask in matched,
                data[:48],
            )
        )

    def test_reference_c001_link(self) -> None:
        self._compare(TEST_STRINGS[0])

    def test_reference_share_link(self) -> None:
        self._compare(TEST_STRINGS[1])

    def test_reference_high_version(self) -> None:
        self._compare(TEST_STRINGS[2])

    def test_reference_report(self) -> None:
        """打印比对明细（不依赖网络时只打印跳过原因）。"""
        if self._skip_reason:
            print("\n[参考比对] 跳过：%s" % self._skip_reason)
            self.skipTest("参考比对被跳过：%s" % self._skip_reason)
        for line in self.report:
            print("[参考比对] %s" % line)


if __name__ == "__main__":
    unittest.main(verbosity=2)
