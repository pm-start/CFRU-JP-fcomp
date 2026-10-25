#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C の展開器 (src/fcomp.c) を PC のコンパイラ (clang か gcc) でビルドして、Python の圧縮器の出力を展開させる検算。
C の FCompInflate が出すのは「使うタイルの並び + タイル番号の並び」(F.body_of の中身)。タイルを並べ直すのは呼び出し側 (docs/INTEGRATION.md)。
MIT License (c) 2026 onikoro。  python tests/host_c_check.py    (コンパイラが無ければ SKIP と表示して 0 で終わる)

ARM / Thumb のコードではなく、C の読み方 (ビット列・表・辞書の窓) が圧縮器と合っているかを見る。
実機の Thumb の命令での確認は docs/INTEGRATION.md の「実機での確認」を参照。
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
import fcomp as F  # noqa: E402
import fcomp_cli as C  # noqa: E402
from test_roundtrip import synth_sheets  # noqa: E402


def asm_to_c(dictionary, tables):
    """tables_asm() の出力 (.hword / .byte) を C の配列にする (同じ表を二通りに書かないため、アセンブリから起こす)"""
    out = ['static const u8 gFDict[%d] = {%s};' % (len(dictionary), ','.join(str(b) for b in dictionary))]
    for label in ('gFLit', 'gFDist'):
        lens = tables[0] if label == 'gFLit' else tables[1]
        bits = F.FAST_BITS_LIT if label == 'gFLit' else F.FAST_BITS_DIST
        lines = F.ftable_lines(label, lens, bits)
        cur, vals = None, {}
        for ln in lines:
            m = re.match(r'(\w+):$', ln)
            if m:
                cur = m.group(1)
                vals[cur] = []
            elif ln.strip().startswith('.hword'):
                vals[cur] += [int(x) for x in ln.split('.hword')[1].split(',')]
        t = vals[label + 'Table']
        out.append('static const struct BwFTable %sTable = {{%s},{%s},{%s}};' % (
            label, ','.join(map(str, t[0:16])), ','.join(map(str, t[16:32])), ','.join(map(str, t[32:48]))))
        for part in ('Symbols', 'Fast'):
            out.append('static const u16 %s%s[] = {%s};' % (label, part, ','.join(map(str, vals[label + part]))))
    return '\n'.join(out) + '\n'


def find_cc():
    for c in (os.environ.get('CC'), 'clang', 'gcc', 'cc'):
        if c and shutil.which(c):
            return shutil.which(c)
    return None


def main():
    cc = find_cc()
    if not cc:
        print('SKIP: C コンパイラ (clang / gcc) が見つからない')
        return 0
    sheets = synth_sheets(seed=7)
    dictionary, tables, datas = F.encode_all(sheets)
    with tempfile.TemporaryDirectory() as td:
        open(os.path.join(HERE, 'host', 'tables.inc'), 'w').write(asm_to_c(dictionary, tables))
        blob = b''.join(struct.pack('<II', len(d), len(F.body_of(r)[0])) + d + F.body_of(r)[0] for d, r in zip(datas, sheets))
        packed = os.path.join(td, 'sheets.bin')
        open(packed, 'wb').write(blob)
        exe = os.path.join(td, 'host_check.exe' if os.name == 'nt' else 'host_check')
        r = subprocess.run([cc, '-O1', '-fsanitize=undefined' if 'gcc' in cc and os.name != 'nt' else '-O1', '-I', os.path.join(HERE, 'host'),
                            '-o', exe, os.path.join(HERE, 'host', 'main.c'), os.path.join(HERE, '..', 'src', 'fcomp.c')],
                           capture_output=True, text=True)
        os.remove(os.path.join(HERE, 'host', 'tables.inc'))
        if r.returncode:
            print(r.stderr)
            return 1
        r = subprocess.run([exe, packed], capture_output=True, text=True)
        print(r.stdout.strip())
        return r.returncode


if __name__ == '__main__':
    sys.exit(main())
