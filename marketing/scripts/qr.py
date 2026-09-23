#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纯标准库 QR Code 编码器（字节模式 / 纠错等级 M / 版本 1..40 自动选择）。

零第三方依赖：只用 Python 3 标准库（zlib + struct 自拼 PNG）。
实现依据 ISO/IEC 18004：
  * 字节模式（byte mode, 0100），UTF-8 编码；
  * 版本 1..40 自动挑最小可容纳版本；
  * 8 种掩码按标准 4 条罚分规则自动选择；
  * 纠错码字用 GF(256) 上的 Reed-Solomon（本原多项式 0x11D）。

公开 API（其它模块会 import，签名保持稳定）：
  encode(data: str, ecc: str = "M") -> list[list[int]]
      返回 0/1 模块矩阵（1=深色），不含 quiet zone，行列数 = 版本尺寸。
  version_of(data: str, ecc: str = "M") -> int
      返回自动选择的最小版本号（1..40）。
  to_svg(matrix, scale=8, quiet=4, dark="#0b0b0b", light="#ffffff") -> str
      输出 SVG 文本（含 quiet 个模块的静区）。
  to_png(matrix, scale=8, quiet=4) -> bytes
      输出 1-bit 灰度 PNG 字节流（不依赖 PIL）。
"""

from __future__ import annotations

import struct
import zlib

__all__ = ["encode", "version_of", "to_svg", "to_png"]

# ---------------------------------------------------------------- 常量表

# 纠错等级 → 内部编号（L/M/Q/H）。M 为本工具链默认。
_ECC_INDEX = {"L": 0, "M": 1, "Q": 2, "H": 3}

# 纠错等级内部编号 → 格式信息里使用的 2 bit 值（行序 L=01, M=00, Q=11, H=10）。
_ECC_FORMAT_BITS = (1, 0, 3, 2)

# 每个纠错块里的纠错码字数。行序 = L, M, Q, H；每行索引 0 为占位。
_ECC_CODEWORDS_PER_BLOCK = (
    # 版本:  0   1   2   3   4   5   6   7   8   9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31  32  33  34  35  36  37  38  39  40
    (-1,  7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28, 28, 28, 30, 30, 26, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    (-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28),
    (-1, 13, 22, 18, 26, 18, 24, 18, 22, 20, 24, 28, 26, 24, 20, 30, 24, 28, 28, 26, 30, 28, 30, 30, 30, 30, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    (-1, 17, 28, 22, 16, 22, 28, 26, 26, 24, 28, 24, 28, 22, 24, 24, 30, 28, 28, 26, 28, 30, 24, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
)

# 每个版本里纠错块的数量。行序 = L, M, Q, H；每行索引 0 为占位。
_NUM_ECC_BLOCKS = (
    (-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8, 8, 9, 9, 10, 12, 12, 12, 13, 14, 15, 16, 17, 18, 19, 19, 20, 21, 22, 24, 25),
    (-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49),
    (-1, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8, 8, 10, 12, 16, 12, 17, 16, 18, 21, 20, 23, 23, 25, 27, 29, 34, 34, 35, 38, 40, 43, 45, 48, 51, 53, 56, 59, 62, 65, 68),
    (-1, 1, 1, 2, 4, 4, 4, 5, 6, 8, 8, 11, 11, 16, 16, 18, 16, 19, 21, 25, 25, 25, 34, 30, 32, 35, 37, 40, 42, 45, 48, 51, 54, 57, 60, 63, 66, 70, 74, 77, 81),
)


# ---------------------------------------------------------------- 基础工具

def _ecc_index(ecc: str) -> int:
    key = (ecc or "").strip().upper()
    if key not in _ECC_INDEX:
        raise ValueError("不支持的纠错等级：%r（只支持 L/M/Q/H）" % (ecc,))
    return _ECC_INDEX[key]


def _num_raw_data_modules(ver: int) -> int:
    """返回某版本除去功能区后可用于数据的模块总数（bit 数）。"""
    result = (16 * ver + 128) * ver + 64
    if ver >= 2:
        numalign = ver // 7 + 2
        result -= (25 * numalign - 10) * numalign - 55
        if ver >= 7:
            result -= 36
    return result


def _num_data_codewords(ver: int, ecl: int) -> int:
    """某版本 + 纠错等级下的数据码字数量。"""
    return (_num_raw_data_modules(ver) // 8
            - _ECC_CODEWORDS_PER_BLOCK[ecl][ver] * _NUM_ECC_BLOCKS[ecl][ver])


def _byte_mode_capacity_bits(ver: int, ecl: int) -> int:
    return _num_data_codewords(ver, ecl) * 8


def _segment_bit_length(nbytes: int, ver: int) -> int:
    """字节模式段长度：4 bit 模式指示符 + 字符计数指示符 + 数据。"""
    ccb = 8 if ver <= 9 else 16
    return 4 + ccb + 8 * nbytes


# ---------------------------------------------------------------- RS 纠错

def _gf_multiply(x: int, y: int) -> int:
    """GF(256) 乘法，本原多项式 0x11D。"""
    z = 0
    for i in reversed(range(8)):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(degree: int) -> list[int]:
    """生成 Reed-Solomon 生成多项式（除最高次外，转成降幂系数列表）。"""
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_multiply(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_multiply(root, 0x02)
    return result


def _rs_remainder(data: list[int], divisor: list[int]) -> list[int]:
    """多项式除法取余，得到纠错码字。"""
    result = [0] * len(divisor)
    for b in data:
        factor = b ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _gf_multiply(coef, factor)
    return result


# ---------------------------------------------------------------- 位流构造

def _make_data_codewords(data_bytes: bytes, ver: int, ecl: int) -> list[int]:
    """把数据编码成完整的（含补齐的）数据码字序列。"""
    capacity_bits = _byte_mode_capacity_bits(ver, ecl)
    if _segment_bit_length(len(data_bytes), ver) > capacity_bits:
        raise ValueError("数据长度超出该版本容量（这是内部错误，版本选择有误）")

    bits: list[int] = []

    def put(value: int, nbits: int) -> None:
        for i in range(nbits - 1, -1, -1):
            bits.append((value >> i) & 1)

    ccb = 8 if ver <= 9 else 16
    put(0x4, 4)                 # 字节模式指示符
    put(len(data_bytes), ccb)   # 字符计数
    for byte in data_bytes:
        put(byte, 8)

    # 终止符（最多 4 个 0），再补齐到字节边界
    term = min(4, capacity_bits - len(bits))
    if term > 0:
        put(0, term)
    if len(bits) % 8 != 0:
        put(0, 8 - (len(bits) % 8))

    # 交替填充字节 0xEC / 0x11
    pad = 0xEC
    while len(bits) < capacity_bits:
        put(pad, 8)
        pad ^= 0xEC ^ 0x11

    out = bytearray(len(bits) // 8)
    for i, bit in enumerate(bits):
        if bit:
            out[i >> 3] |= 0x80 >> (i & 7)
    return list(out)


def _add_ecc_and_interleave(data: list[int], ver: int, ecl: int) -> list[int]:
    """分块 → 每块算 RS 纠错 → 按标准交织成最终码字序列。"""
    numblocks = _NUM_ECC_BLOCKS[ecl][ver]
    blockecclen = _ECC_CODEWORDS_PER_BLOCK[ecl][ver]
    rawcodewords = _num_raw_data_modules(ver) // 8
    numshortblocks = numblocks - rawcodewords % numblocks
    shortblocklen = rawcodewords // numblocks

    divisor = _rs_divisor(blockecclen)
    blocks: list[list[int]] = []
    k = 0
    for i in range(numblocks):
        datalen = shortblocklen - blockecclen + (0 if i < numshortblocks else 1)
        dat = data[k:k + datalen]
        k += len(dat)
        ecc = _rs_remainder(dat, divisor)
        if i < numshortblocks:
            dat = dat + [0]  # 短块补位，保证交织对齐
        blocks.append(dat + ecc)

    result: list[int] = []
    for i in range(len(blocks[0])):
        for j, blk in enumerate(blocks):
            if i != shortblocklen - blockecclen or j >= numshortblocks:
                result.append(blk[i])
    return result


# ---------------------------------------------------------------- 矩阵绘制

class _QrMatrix:
    """内部可变矩阵：modules[y][x] 为 True(深)/False(浅)，isfunc[y][x] 标记功能区。"""

    def __init__(self, ver: int) -> None:
        self.version = ver
        self.size = ver * 4 + 17
        self.modules = [[False] * self.size for _ in range(self.size)]
        self.isfunc = [[False] * self.size for _ in range(self.size)]
        self.mask = -1

    def _set_func(self, x: int, y: int, dark: bool) -> None:
        self.modules[y][x] = dark
        self.isfunc[y][x] = True

    # --- 各功能图形 ---

    def _draw_finder(self, x: int, y: int) -> None:
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                dist = max(abs(dx), abs(dy))
                xx, yy = x + dx, y + dy
                if 0 <= xx < self.size and 0 <= yy < self.size:
                    self._set_func(xx, yy, dist != 2 and dist != 4)

    def _draw_alignment(self, x: int, y: int) -> None:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                self._set_func(x + dx, y + dy, max(abs(dx), abs(dy)) != 1)

    def _alignment_positions(self) -> list[int]:
        ver = self.version
        if ver == 1:
            return []
        numalign = ver // 7 + 2
        step = 26 if ver == 32 else (ver * 4 + numalign * 2 + 1) // (numalign * 2 - 2) * 2
        result = [(self.size - 7 - i * step) for i in range(numalign - 1)] + [6]
        return list(reversed(result))

    def _draw_function_patterns(self) -> None:
        size = self.size

        # 定位图形（横向 / 纵向时序）
        for i in range(size):
            self._set_func(6, i, i % 2 == 0)
            self._set_func(i, 6, i % 2 == 0)

        # 三个角上的 finder（会覆盖部分时序）
        self._draw_finder(3, 3)
        self._draw_finder(size - 4, 3)
        self._draw_finder(3, size - 4)

        # 对齐图形（跳过与 finder 重叠的三处）
        ap = self._alignment_positions()
        n = len(ap)
        for i in range(n):
            for j in range(n):
                if (i == 0 and j == 0) or (i == 0 and j == n - 1) or (i == n - 1 and j == 0):
                    continue
                self._draw_alignment(ap[i], ap[j])

        # 占位：格式信息与版本信息（真正内容在掩码阶段重画）
        self._draw_format_bits(0)
        self._draw_version()

    def _draw_format_bits(self, mask: int) -> None:
        size = self.size
        data = _ECC_FORMAT_BITS[self._ecc] << 3 | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412

        def bit(i: int) -> bool:
            return ((bits >> i) & 1) != 0

        for i in range(6):
            self._set_func(8, i, bit(i))
        self._set_func(8, 7, bit(6))
        self._set_func(8, 8, bit(7))
        self._set_func(7, 8, bit(8))
        for i in range(9, 15):
            self._set_func(14 - i, 8, bit(i))

        for i in range(8):
            self._set_func(size - 1 - i, 8, bit(i))
        for i in range(8, 15):
            self._set_func(8, size - 15 + i, bit(i))
        self._set_func(8, size - 8, True)  # 固定深色模块

    def _draw_version(self) -> None:
        if self.version < 7:
            return
        rem = self.version
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        bits = self.version << 12 | rem
        for i in range(18):
            b = ((bits >> i) & 1) != 0
            a = self.size - 11 + i % 3
            c = i // 3
            self._set_func(a, c, b)
            self._set_func(c, a, b)

    def _draw_codewords(self, data: list[int]) -> None:
        if len(data) != _num_raw_data_modules(self.version) // 8:
            raise ValueError("码字数量与版本不符（内部错误）")
        i = 0
        total_bits = len(data) * 8
        for right in range(self.size - 1, 0, -2):
            if right <= 6:
                right -= 1
            for vert in range(self.size):
                for j in range(2):
                    x = right - j
                    upward = ((right + 1) & 2) == 0
                    y = (self.size - 1 - vert) if upward else vert
                    if not self.isfunc[y][x] and i < total_bits:
                        self.modules[y][x] = ((data[i >> 3] >> (7 - (i & 7))) & 1) != 0
                        i += 1

    def _apply_mask(self, mask: int) -> None:
        for y in range(self.size):
            for x in range(self.size):
                if mask == 0:
                    invert = (x + y) % 2 == 0
                elif mask == 1:
                    invert = y % 2 == 0
                elif mask == 2:
                    invert = x % 3 == 0
                elif mask == 3:
                    invert = (x + y) % 3 == 0
                elif mask == 4:
                    invert = (x // 3 + y // 2) % 2 == 0
                elif mask == 5:
                    invert = x * y % 2 + x * y % 3 == 0
                elif mask == 6:
                    invert = (x * y % 2 + x * y % 3) % 2 == 0
                elif mask == 7:
                    invert = ((x + y) % 2 + x * y % 3) % 2 == 0
                else:
                    raise ValueError("非法掩码 %d" % mask)
                if invert and not self.isfunc[y][x]:
                    self.modules[y][x] = not self.modules[y][x]

    # --- 罚分（ISO/IEC 18004 §8.8.2）---

    def _finder_penalty_add_history(self, runlen: int, history: list[int]) -> None:
        if history[0] == 0:
            runlen += self.size  # 起始补一段浅色边框
        history.insert(0, runlen)
        history.pop()

    def _finder_penalty_count_patterns(self, history: list[int]) -> int:
        n = history[1]
        core = (n > 0 and history[2] == n and history[3] == n * 3
                and history[4] == n and history[5] == n)
        return ((1 if core and history[0] >= n * 4 and history[6] >= n else 0)
                + (1 if core and history[6] >= n * 4 and history[0] >= n else 0))

    def _finder_penalty_terminate(self, runcolor: bool, runlen: int,
                                  history: list[int]) -> int:
        if runcolor:
            self._finder_penalty_add_history(runlen, history)
            runlen = 0
        runlen += self.size  # 末尾补浅色边框
        self._finder_penalty_add_history(runlen, history)
        return self._finder_penalty_count_patterns(history)

    def _penalty_score(self) -> int:
        size = self.size
        modules = self.modules
        result = 0

        # 规则 1 / 3：同色连续 + finder-like 1:1:3:1:1
        for y in range(size):
            runcolor = False
            runlen = 0
            history = [0] * 7
            for x in range(size):
                if modules[y][x] == runcolor:
                    runlen += 1
                    if runlen == 5:
                        result += 3
                    elif runlen > 5:
                        result += 1
                else:
                    self._finder_penalty_add_history(runlen, history)
                    if not runcolor:
                        result += self._finder_penalty_count_patterns(history) * 40
                    runcolor = modules[y][x]
                    runlen = 1
            result += self._finder_penalty_terminate(runcolor, runlen, history) * 40

        for x in range(size):
            runcolor = False
            runlen = 0
            history = [0] * 7
            for y in range(size):
                if modules[y][x] == runcolor:
                    runlen += 1
                    if runlen == 5:
                        result += 3
                    elif runlen > 5:
                        result += 1
                else:
                    self._finder_penalty_add_history(runlen, history)
                    if not runcolor:
                        result += self._finder_penalty_count_patterns(history) * 40
                    runcolor = modules[y][x]
                    runlen = 1
            result += self._finder_penalty_terminate(runcolor, runlen, history) * 40

        # 规则 2：2x2 同色块
        for y in range(size - 1):
            for x in range(size - 1):
                color = modules[y][x]
                if color == modules[y][x + 1] == modules[y + 1][x] == modules[y + 1][x + 1]:
                    result += 3

        # 规则 4：深浅比例均衡
        dark = sum(row.count(True) for row in modules)
        total = size * size
        k = (abs(dark * 20 - total * 10) + total - 1) // total - 1
        result += k * 10

        return result

    # --- 官方构建流程 ---

    def build(self, data_codewords: list[int], ecl: int, mask: int | None = None) -> None:
        self._ecc = ecl
        self._draw_function_patterns()
        allcodewords = _add_ecc_and_interleave(data_codewords, self.version, ecl)
        self._draw_codewords(allcodewords)

        if mask is not None:
            # 强制掩码（供参考比对测试使用）。ISO/IEC 18004 允许编码器自选 8 个掩码之一，
            # 任何合法掩码解码结果相同，故掩码选择不属可移植性约束。
            if not 0 <= int(mask) <= 7:
                raise ValueError("mask 必须是 0..7")
            self._apply_mask(int(mask))
            self._draw_format_bits(int(mask))
            self.mask = int(mask)
            return

        best_mask = 0
        minpenalty = None
        for m in range(8):
            self._apply_mask(m)
            self._draw_format_bits(m)
            penalty = self._penalty_score()
            if minpenalty is None or penalty < minpenalty:
                minpenalty = penalty
                best_mask = m
            self._apply_mask(m)  # 撤销

        self._apply_mask(best_mask)
        self._draw_format_bits(best_mask)
        self.mask = best_mask
        self.penalty = minpenalty

    def to_matrix(self) -> list[list[int]]:
        return [[1 if v else 0 for v in row] for row in self.modules]


# ---------------------------------------------------------------- 公开 API

def version_of(data: str, ecc: str = "M") -> int:
    """返回能容纳 data（UTF-8 字节模式）的最小 QR 版本号（1..40）。"""
    ecl = _ecc_index(ecc)
    nbytes = len(data.encode("utf-8"))
    for ver in range(1, 41):
        if _segment_bit_length(nbytes, ver) <= _byte_mode_capacity_bits(ver, ecl):
            return ver
    raise ValueError("数据过长：超出版本 40 在纠错等级 %s 下的容量" % ecc.strip().upper())


def encode(data: str, ecc: str = "M", mask: int | None = None) -> list[list[int]]:
    """编码 data 为 0/1 模块矩阵（1=深色），不含 quiet zone。

    mask=None 时按 ISO/IEC 18004 罚分规则自动选掩码；mask=0..7 时强制指定该掩码
    （掩码选择属编码器自选项，任一合法掩码解码结果相同）。
    """
    if not isinstance(data, str):
        raise TypeError("data 必须是 str")
    ecl = _ecc_index(ecc)
    ver = version_of(data, ecc)
    codewords = _make_data_codewords(data.encode("utf-8"), ver, ecl)
    mat = _QrMatrix(ver)
    mat.build(codewords, ecl, mask=mask)
    return mat.to_matrix()


def to_svg(matrix: list[list[int]], scale: int = 8, quiet: int = 4,
           dark: str = "#0b0b0b", light: str = "#ffffff") -> str:
    """把模块矩阵渲染成 SVG 文本（包含 quiet 个模块宽度的静区）。"""
    dim = len(matrix)
    total = (dim + 2 * quiet) * scale
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="%d" height="%d" viewBox="0 0 %d %d" shape-rendering="crispEdges">'
        % (total, total, total, total)
    ]
    if light:
        parts.append('<rect width="100%%" height="100%%" fill="%s"/>' % light)
    segs = []
    for y in range(dim):
        row = matrix[y]
        for x in range(dim):
            if row[x]:
                px = (x + quiet) * scale
                py = (y + quiet) * scale
                segs.append("M%d %dh%dv%dh-%dz" % (px, py, scale, scale, scale))
    if segs:
        parts.append('<path d="%s" fill="%s"/>' % ("".join(segs), dark))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _png_chunk(tag: bytes, payload: bytes) -> bytes:
    return (struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))


def to_png(matrix: list[list[int]], scale: int = 8, quiet: int = 4) -> bytes:
    """把模块矩阵渲染成 1-bit 灰度 PNG 字节流（自拼，不依赖 PIL）。"""
    dim = len(matrix)
    total = (dim + 2 * quiet) * scale
    stride = (total + 7) // 8

    raw = bytearray()
    for y in range(total):
        my = y // scale - quiet
        rowbits = bytearray(stride)
        for x in range(total):
            mx = x // scale - quiet
            dark = 0 <= mx < dim and 0 <= my < dim and bool(matrix[my][mx])
            if not dark:  # 1-bit 灰度：1=白(255)，0=黑(0)
                rowbits[x >> 3] |= 0x80 >> (x & 7)
        raw.append(0x00)  # 每行滤波类型 = None
        raw.extend(rowbits)

    ihdr = struct.pack(">IIBBBBB", total, total, 1, 0, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + _png_chunk(b"IHDR", ihdr)
            + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + _png_chunk(b"IEND", b""))


if __name__ == "__main__":  # pragma: no cover - 手工自检入口
    import sys

    for _s in (sys.argv[1:] or ["https://example.com/?ref=c001", "你好 QR & test"]):
        _ver = version_of(_s)
        _m = encode(_s)
        print("data=%r version=%d dim=%d" % (_s, _ver, len(_m)))
