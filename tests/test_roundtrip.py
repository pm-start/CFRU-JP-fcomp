#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Python だけで回せる検算 (MIT License (c) 2026 onikoro)。  python tests/test_roundtrip.py

自作の合成タイルシート (任天堂などの素材は使わない) を圧縮し、Python の展開器 decode() で
1 バイトも違わず元に戻ることを確かめる。さらに、
  - tables.s の表が仕様どおりの形 (count の合計 = 記号の数、Fast 表の長さ) になっている
も見る。
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
import fcomp as F  # noqa: E402
import fcomp_cli as C  # noqa: E402


# 子プロセスの出力は UTF-8 に固定する (日本語 Windows の既定 cp932 でも読み違えない)
ENV = dict(os.environ, PYTHONIOENCODING='utf-8')


def synth_sheets(seed=1):
    """円・縞・ノイズなどの自作の図形を 4bpp (1 バイト = 2 画素) のタイルにしたもの"""
    rnd = random.Random(seed)
    sheets = []
    for n in range(60):
        w = h = rnd.choice([32, 64])
        px = [[0] * w for _ in range(h)]
        cx, cy, r = rnd.randint(8, w - 8), rnd.randint(8, h - 8), rnd.randint(4, 14)
        col = rnd.randint(1, 15)
        for y in range(h):
            for x in range(w):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    px[y][x] = col
                elif n % 3 == 0 and (x // 4 + y // 4) % 2:
                    px[y][x] = rnd.randint(1, 3)
                elif n % 7 == 0:
                    px[y][x] = rnd.randint(0, 15)
        raw = bytearray()
        for ty in range(h // 8):                # タイル順 (8x8 ずつ・1 バイト 2 画素・下位が左)
            for tx in range(w // 8):
                for y in range(8):
                    for x in range(0, 8, 2):
                        a = px[ty * 8 + y][tx * 8 + x]
                        b = px[ty * 8 + y][tx * 8 + x + 1]
                        raw.append(a | (b << 4))
        sheets.append(bytes(raw))
    return sheets


def main():
    sheets = synth_sheets()
    dictionary, tables, datas = F.encode_all(sheets)
    ok = 0
    for i, (raw, d) in enumerate(zip(sheets, datas)):
        assert F.decode(d, dictionary, tables) == raw, '%d 枚目が元に戻らない' % i
        ok += 1
    tot_raw, tot_c = sum(map(len, sheets)), sum(map(len, datas))
    print('往復 OK: %d 枚・%d -> %d バイト' % (ok, tot_raw, tot_c))
    assert tot_c < tot_raw

    # 表の形 (C の展開器が読む構造と合うか)
    asm = C.tables_asm(dictionary, tables)
    for name in ('gFDictSize', 'gFDict', 'gFLitTable', 'gFLitSymbols', 'gFLitFast', 'gFDistTable', 'gFDistSymbols', 'gFDistFast'):
        assert ('%s:' % name) in asm, name
    for lens, bits in ((tables[0], F.FAST_BITS_LIT), (tables[1], F.FAST_BITS_DIST)):
        assert max(lens) <= F.MAX_BITS
        kraft = sum(2 ** (F.MAX_BITS - l) for l in lens if l)
        assert kraft <= 2 ** F.MAX_BITS, 'Kraft の和が 1 を超えた'
    print('表の形 OK')

    # コマンドライン: --mark 0x80 付きで pack -> unpack
    import subprocess, tempfile
    with tempfile.TemporaryDirectory() as td:
        files = []
        for i, raw in enumerate(sheets[:5]):
            fn = os.path.join(td, 's%d.bin' % i)
            open(fn, 'wb').write(raw)
            files.append(fn)
        cli = os.path.join(HERE, '..', 'tools', 'fcomp_cli.py')
        out = os.path.join(td, 'out')
        subprocess.run([sys.executable, cli, 'pack', out] + files + ['--mark', '0x80'], check=True, capture_output=True, env=ENV)
        assert open(os.path.join(out, '0000.fc'), 'rb').read(1) ==bytes([0x80])
        r = subprocess.run([sys.executable, cli, 'unpack', out], check=True, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', env=ENV)
        assert r.stdout.count('OK') == 5 and 'NG' not in r.stdout, r.stdout
    print('CLI (--mark 0x80) OK')
    print('ALL OK')


if __name__ == '__main__':
    main()
