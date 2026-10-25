#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F 方式の圧縮器（Python）と、検算用の展開器 decode()。MIT License (c) 2026 onikoro

GBA の 4bpp タイルシート（8x8 タイル = 32 バイトの並び）を縮める自前の形式。
  1. タイルの使い回し: 同じ 32 バイトのタイルを 1 つにして「使うタイルの並び」＋「タイル番号の並び」にする
  2. LZ77 + ハフマン（Deflate と同じ長さ・距離の区切り方。距離は共通辞書のぶん 65536 まで）
  3. 共通辞書: 多くのシートに出てくるタイルを集めたもの（ROM に置き、展開器が直接読む）
  4. ハフマンの表は全シートの統計から 1 組だけ

1 シートのデータ（4 バイトそろえ）:
  u16 タイルの数 / u16 使うタイルの数 (U) / u8 番号の幅 (1 か 2) / u8 0 / u16 ビット列の語 (32 ビット) の数
  ＋ ハフマンのビット列（下位ビットから・32 ビットずつ）: 使うタイル (U x 32 バイト) ＋ 番号の並び

  encode_all(sheets) -> (共通辞書, (lit_len, dist_len), [シートごとのデータ])
  decode(data, dictionary, tables) -> 生のシート（検算用。C の展開器 src/fcomp.c と同じ手順）
"""
import collections
import heapq
import struct

TILE = 32
MIN_MATCH, MAX_MATCH = 3, 258
DICT_TILES = 1024                     # 共通辞書 32KB
MAX_BITS = 15

# Deflate の長さの区切り（符号 257〜285）: (下限, 追加のビット数)
LEN_BASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258]
LEN_EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0]
# 距離の区切り: Deflate の 30 個（〜32768）＋ 2 個（〜65536）
DIST_BASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073,
             4097, 6145, 8193, 12289, 16385, 24577, 32769, 49153]
DIST_EXTRA = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14]
END = 256
NUM_LIT = 257 + len(LEN_BASE)         # 0〜255 文字・256 終わり・257〜285 長さ
NUM_DIST = len(DIST_BASE)


def _code_of(value, bases):
    i = len(bases) - 1
    while bases[i] > value:
        i -= 1
    return i


# ------------------------------------------------------------ 1. タイルの使い回し
def split_tiles(raw):
    tiles = [raw[i:i + TILE] for i in range(0, len(raw), TILE)]
    uniq, index, where = [], [], {}
    for t in tiles:
        if t not in where:
            where[t] = len(uniq)
            uniq.append(t)
        index.append(where[t])
    return uniq, index


def body_of(raw):
    """→ (中身のバイト, 全タイル数, 使うタイル数, 番号の幅)"""
    uniq, index = split_tiles(raw)
    width = 1 if len(uniq) <= 256 else 2
    idx = bytes(index) if width == 1 else b''.join(struct.pack('<H', i) for i in index)
    return b''.join(uniq) + idx, len(index), len(uniq), width


# ------------------------------------------------------------ 3. 共通辞書
def build_dictionary(sheets):
    seen = collections.Counter()
    for raw in sheets:
        for t in set(raw[i:i + TILE] for i in range(0, len(raw), TILE)):
            seen[t] += 1
    common = [t for t, n in seen.most_common(DICT_TILES) if n > 1]
    return b''.join(common)


# ------------------------------------------------------------ 2. LZ77（辞書つきの窓・ハッシュの鎖・一歩先読み）
def lz_tokens(body, dictionary, max_chain=64):
    """→ [('L', byte) か ('M', 長さ, 距離)]"""
    buf = dictionary + body
    start = len(dictionary)
    head = {}
    prev = {}

    def insert(i):
        if i + MIN_MATCH <= len(buf):
            k = buf[i:i + MIN_MATCH]
            prev[i] = head.get(k)
            head[k] = i

    for i in range(0, start):
        insert(i)

    def longest(i):
        best_len, best_dist = 0, 0
        if i + MIN_MATCH > len(buf):
            return 0, 0
        j = head.get(buf[i:i + MIN_MATCH])
        chain = 0
        limit = min(MAX_MATCH, len(buf) - i)
        while j is not None and chain < max_chain:
            d = i - j
            if d > 65536:
                break
            n = 0
            while n < limit and buf[j + n] == buf[i + n]:
                n += 1
            if n > best_len:
                best_len, best_dist = n, d
                if n == limit:
                    break
            j = prev.get(j)
            chain += 1
        return best_len, best_dist

    out = []
    i = start
    while i < len(buf):
        n, d = longest(i)
        if n >= MIN_MATCH:
            n2, _d2 = longest(i + 1) if i + 1 < len(buf) else (0, 0)
            if n2 > n + 1:                                   # 一歩先のほうが長ければ 1 文字出して先へ
                out.append(('L', buf[i]))
                insert(i)
                i += 1
                continue
            out.append(('M', n, d))
            for k in range(i, i + n):
                insert(k)
            i += n
        else:
            out.append(('L', buf[i]))
            insert(i)
            i += 1
    return out


# ------------------------------------------------------------ 4. ハフマン（長さを MAX_BITS までに抑えた正準符号）
def code_lengths(freqs, max_bits=MAX_BITS):
    syms = [(f, s) for s, f in enumerate(freqs) if f > 0]
    lengths = [0] * len(freqs)
    if len(syms) == 1:
        lengths[syms[0][1]] = 1
        return lengths
    heap = [(f, i, [s]) for i, (f, s) in enumerate(syms)]
    heapq.heapify(heap)
    cnt = len(heap)
    while len(heap) > 1:
        f1, _a, s1 = heapq.heappop(heap)
        f2, _b, s2 = heapq.heappop(heap)
        for s in s1 + s2:
            lengths[s] += 1
        heapq.heappush(heap, (f1 + f2, cnt, s1 + s2))
        cnt += 1
    # 長すぎる符号を縮める（いちばん長いものを 1 段上げ、短いものを 1 つ下げる・Kraft の和を保つ）
    while max(lengths) > max_bits:
        for s, l in enumerate(lengths):
            if l > max_bits:
                lengths[s] = max_bits
        kraft = sum(2 ** (max_bits - l) for l in lengths if l)
        cap = 2 ** max_bits
        while kraft > cap:
            s = max((l, s) for s, l in enumerate(lengths) if 0 < l < max_bits)[1]
            kraft -= 2 ** (max_bits - lengths[s] - 1)
            lengths[s] += 1
    return lengths


def canonical(lengths):
    """→ {記号: (符号, 長さ)}（符号は上位ビットから読む並び・書くときに反転する）"""
    code, out = 0, {}
    bl_count = collections.Counter(l for l in lengths if l)
    next_code = {}
    for bits in range(1, MAX_BITS + 1):
        code = (code + bl_count.get(bits - 1, 0)) << 1
        next_code[bits] = code
    for s, l in enumerate(lengths):
        if l:
            out[s] = (next_code[l], l)
            next_code[l] += 1
    return out


def _rev(v, n):
    r = 0
    for _ in range(n):
        r = (r << 1) | (v & 1)
        v >>= 1
    return r


class BitWriter(object):
    def __init__(self):
        self.acc, self.n, self.out = 0, 0, bytearray()

    def put(self, v, n):
        self.acc |= v << self.n
        self.n += n
        while self.n >= 8:
            self.out.append(self.acc & 0xFF)
            self.acc >>= 8
            self.n -= 8

    def flush(self):
        if self.n:
            self.out.append(self.acc & 0xFF)
        self.acc, self.n = 0, 0
        while len(self.out) % 4:
            self.out.append(0)
        return bytes(self.out)


def encode_tokens(tokens, lit_code, dist_code):
    w = BitWriter()

    def sym(code, s):
        c, l = code[s]
        w.put(_rev(c, l), l)
    for t in tokens:
        if t[0] == 'L':
            sym(lit_code, t[1])
        else:
            _k, n, d = t
            lc = _code_of(n, LEN_BASE)
            sym(lit_code, 257 + lc)
            if LEN_EXTRA[lc]:
                w.put(n - LEN_BASE[lc], LEN_EXTRA[lc])
            dc = _code_of(d, DIST_BASE)
            sym(dist_code, dc)
            if DIST_EXTRA[dc]:
                w.put(d - DIST_BASE[dc], DIST_EXTRA[dc])
    sym(lit_code, END)
    return w.flush()


def encode_all(sheets, max_chain=256):
    dictionary = build_dictionary(sheets)
    parts = []
    lit_f = [0] * NUM_LIT
    dist_f = [0] * NUM_DIST
    for raw in sheets:
        body, ntiles, nuniq, width = body_of(raw)
        toks = lz_tokens(body, dictionary, max_chain)
        for t in toks:
            if t[0] == 'L':
                lit_f[t[1]] += 1
            else:
                lit_f[257 + _code_of(t[1], LEN_BASE)] += 1
                dist_f[_code_of(t[2], DIST_BASE)] += 1
        lit_f[END] += 1
        parts.append((toks, ntiles, nuniq, width))
    # すべての記号に 1 を足しておく（編集で新しい絵を足しても符号が引ける）
    lit_len = code_lengths([f + 1 for f in lit_f])
    dist_len = code_lengths([f + 1 for f in dist_f])
    lit_code, dist_code = canonical(lit_len), canonical(dist_len)
    datas = []
    for toks, ntiles, nuniq, width in parts:
        bits = encode_tokens(toks, lit_code, dist_code)
        head = struct.pack('<HHBxH', ntiles, nuniq, width, len(bits) // 4)
        datas.append(head + bits)
    return dictionary, (lit_len, dist_len), datas


# ------------------------------------------------------------ 表を .s に書く（src/fcomp.h の struct BwFTable・記号の並び・速く引く表）
FAST_BITS_LIT, FAST_BITS_DIST = 10, 8   # src/fcomp.c の FC_LIT_FAST_BITS / FC_DIST_FAST_BITS と同じ


def ftable_lines(label, lengths, fast_bits):
    """正準ハフマン符号の表（src/fcomp.h の struct BwFTable ＋ 記号の並び）。fcomp.canonical と同じ符号の振り方"""
    count = [0] * 16
    for l in lengths:
        if l:
            count[l] += 1
    first, index = [0] * 16, [0] * 16
    code, idx = 0, 0
    for bits in range(1, 16):
        code = (code + (count[bits - 1] if bits > 1 else 0)) << 1 if bits > 1 else 0
        first[bits] = code
        index[bits] = idx
        idx += count[bits]
    syms = [s for l in range(1, 16) for s in range(len(lengths)) if lengths[s] == l]
    out = ['    .align 2', '    .global %sTable' % label, '%sTable:' % label]
    for arr in (first, count, index):
        out.append('    .hword ' + ', '.join(str(v) for v in arr))
    out += ['    .global %sSymbols' % label, '%sSymbols:' % label]
    for i in range(0, len(syms), 16):
        out.append('    .hword ' + ', '.join(str(v) for v in syms[i:i + 16]))
    # 速く引く表（1 ビットずつ調べると遅い）: 先の FAST_BITS ビット（読む順 = 下位ビットから）で引く。
    #   値 = 記号 | (符号の長さ << 9)。0 なら FAST_BITS より長い符号 → 1 ビットずつの遅い道
    fast = [0] * (1 << fast_bits)
    nxt = list(first)
    for s in range(len(lengths)):
        l = lengths[s]
        if not l:
            continue
        c = nxt[l]
        nxt[l] += 1
        if l > fast_bits:
            continue
        r = int(format(c, '0%db' % l)[::-1], 2)
        for x in range(1 << (fast_bits - l)):
            fast[r | (x << l)] = s | (l << 9)
    out += ['    .global %sFast' % label, '%sFast:' % label]
    for i in range(0, len(fast), 16):
        out.append('    .hword ' + ', '.join(str(v) for v in fast[i:i + 16]))
    return out


# ------------------------------------------------------------ 展開（検算用・C の展開器と同じ手順）
def _decode_table(lengths):
    """(長さ, 符号) → 記号"""
    return {(l, c): s for s, (c, l) in canonical(lengths).items()}


def decode(data, dictionary, tables):
    ntiles, nuniq, width, nwords = struct.unpack_from('<HHBxH', data, 0)
    bits = int.from_bytes(data[8:8 + 4 * nwords], 'little')
    pos = [0]

    def get(n):
        v = (bits >> pos[0]) & ((1 << n) - 1)
        pos[0] += n
        return v
    lit_t, dist_t = _decode_table(tables[0]), _decode_table(tables[1])

    def sym(t):
        c, l = 0, 0
        while True:
            c = (c << 1) | get(1)
            l += 1
            if (l, c) in t:
                return t[(l, c)]
    out = bytearray()
    D = len(dictionary)
    while True:
        s = sym(lit_t)
        if s < 256:
            out.append(s)
        elif s == END:
            break
        else:
            lc = s - 257
            n = LEN_BASE[lc] + (get(LEN_EXTRA[lc]) if LEN_EXTRA[lc] else 0)
            dc = sym(dist_t)
            d = DIST_BASE[dc] + (get(DIST_EXTRA[dc]) if DIST_EXTRA[dc] else 0)
            for _ in range(n):
                p = len(out) - d
                out.append(out[p] if p >= 0 else dictionary[D + p])
    tiles = [bytes(out[i * TILE:(i + 1) * TILE]) for i in range(nuniq)]
    idx = out[nuniq * TILE:]
    if width == 1:
        order = list(idx[:ntiles])
    else:
        order = [struct.unpack_from('<H', idx, 2 * i)[0] for i in range(ntiles)]
    return b''.join(tiles[i] for i in order)
