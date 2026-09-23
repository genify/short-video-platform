"""渠道 2 落地包生成器单测：URL 规则 / 幂等 / 非法输入 / 生成物可读性。"""

from __future__ import annotations

import csv
import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "marketing" / "scripts" / "make_creator_links.py"

_spec = importlib.util.spec_from_file_location("make_creator_links", SCRIPT)
mcl = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(mcl)

HEADER = "creator_code,name,platform,vertical,handle,channel_url,batch,is_demo,notes"

GOOD_ROWS = [
    "c001,待录入,douyin,food-home,,,B1,0,",
    "c001,待录入,xiaohongshu,food-home,,,B1,0,",  # 同一 code 的第二平台（合法）
    "d001,演示,douyin,local-life,@demo_x,,DEMO,1,",
]


def write_csv(tmp: Path, rows: list[str]) -> Path:
    path = tmp / "creators.csv"
    path.write_text("\n".join([HEADER] + rows) + "\n", encoding="utf-8")
    return path


def run_gen(csv_path: Path, outdir: Path) -> tuple[int, str, str]:
    buf_out, buf_err = io.StringIO(), io.StringIO()
    with redirect_stdout(buf_out), redirect_stderr(buf_err):
        code = mcl.main(
            [
                "--input",
                str(csv_path),
                "--outdir",
                str(outdir),
                "--landing-base",
                "https://land.example.com/",
                "--app-base",
                "https://app.example.com/",
            ]
        )
    return code, buf_out.getvalue(), buf_err.getvalue()


class TestCreatorLinks(unittest.TestCase):
    def test_url_rules_and_placeholders(self) -> None:
        recruit, share = mcl.build_urls(
            "https://land.example.com/", "https://app.example.com", "douyin", "c001"
        )
        self.assertEqual(
            recruit,
            "https://land.example.com/?utm_source=douyin&utm_medium=creator_recruit"
            "&utm_campaign=pro_launch_p1&utm_content=c001&ref=c001",
        )
        # 占位符必须保留为字面量
        self.assertIn("/s/{video_id}?", share)
        self.assertTrue(share.endswith("&v={variant}"))
        self.assertIn("utm_medium=creator_share", share)
        # utm 参数顺序固定
        order = [recruit.index(k) for k in
                 ("utm_source", "utm_medium", "utm_campaign", "utm_content", "ref")]
        self.assertEqual(order, sorted(order))

    def test_generation_files_and_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            csv_path = write_csv(tmp, GOOD_ROWS)
            out = tmp / "out"
            code, out_text, err = run_gen(csv_path, out)
            self.assertEqual(code, 0, err)
            self.assertIn("3 条链接", out_text)

            registry = out / "links.csv"
            rows = list(csv.DictReader(registry.open(encoding="utf-8")))
            self.assertEqual(len(rows), 3)
            link_ids = sorted(r["link_id"] for r in rows)
            self.assertEqual(link_ids, ["c001_douyin", "c001_xiaohongshu", "d001_douyin"])
            for row in rows:
                self.assertIn("utm_content=%s" % row["creator_code"], row["recruit_url"])
                svg = out / row["qr_svg"]
                png = out / row["qr_png"]
                self.assertTrue(svg.is_file() and png.is_file())
                self.assertIn("<svg", svg.read_text(encoding="utf-8"))
                self.assertEqual(png.read_bytes()[:4], b"\x89PNG")
                self.assertGreaterEqual(int(row["qr_version"]), 1)

            art_txt = (out / "links" / "c001_douyin.txt").read_text(encoding="utf-8")
            self.assertIn("招募链接", art_txt)
            self.assertIn("不得替换为短链或去参数链接", art_txt)

            # 幂等：第二次运行输出逐字节一致
            before = {p: p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}
            code2, _, err2 = run_gen(csv_path, out)
            self.assertEqual(code2, 0, err2)
            after = {p: p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}
            self.assertEqual(set(before), set(after))
            for path, blob in before.items():
                self.assertEqual(blob, after[path], "%s 第二次运行输出不一致" % path)

    def test_duplicate_code_platform_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            csv_path = write_csv(tmp, ["c001,a,douyin,food-home,,,B1,0,", "c001,b,douyin,food-home,,,B1,0,"])
            code, _, err = run_gen(csv_path, tmp / "out")
            self.assertEqual(code, 1)
            self.assertIn("重复的 (creator_code, platform)", err)
            self.assertFalse((tmp / "out" / "links.csv").exists())

    def test_invalid_code_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            csv_path = write_csv(tmp, ["BAD-CODE,x,douyin,food-home,,,B1,0,"])
            code, _, err = run_gen(csv_path, tmp / "out")
            self.assertEqual(code, 1)
            self.assertIn("非法", err)

    def test_invalid_vertical_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            csv_path = write_csv(tmp, ["c001,x,douyin,gaming,,,B1,0,"])
            code, _, err = run_gen(csv_path, tmp / "out")
            self.assertEqual(code, 1)
            self.assertIn("vertical", err)

    def test_lexicon_blocks_banned_text(self) -> None:
        """台账文本字段若含 hard_ban 词（如「保底曝光500」），生成必须被拒绝。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            csv_path = write_csv(tmp, ["c001,保底曝光500,douyin,food-home,,,B1,0,"])
            code, _, err = run_gen(csv_path, tmp / "out")
            self.assertEqual(code, 1)
            self.assertIn("HB-01", err)

    def test_missing_column_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            bad = tmp / "bad.csv"
            bad.write_text("creator_code,platform\nc001,douyin\n", encoding="utf-8")
            code, _, err = run_gen(bad, tmp / "out")
            self.assertEqual(code, 1)
            self.assertIn("缺少列", err)

    def test_real_ledger_template_runs(self) -> None:
        """仓库内台账模板（20 正式 + 2 演示）必须可直接生成。"""
        template = ROOT / "marketing" / "data" / "seed_creators.csv"
        self.assertTrue(template.is_file())
        with tempfile.TemporaryDirectory() as tmpdir:
            code, out_text, err = run_gen(template, Path(tmpdir) / "out")
            self.assertEqual(code, 0, err)
            self.assertIn("22 条链接", out_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
