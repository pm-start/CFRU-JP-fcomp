#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""F 方式の圧縮・展開の command line。MIT License (c) 2026 onikoro

  python tools/fcomp_cli.py pack   out_dir sheet1.bin sheet2.bin ...   # 生の 4bpp シート (32 バイトの倍数) を圧縮
  python tools/fcomp_cli.py unpack out_dir                              # pack の出力を展開して表示 (往復の確認)

pack の出力 (out_dir):
  dict.bin        共通辞書 (ROM に置く)
  tables.json     ハフマンの符号の長さ (lit_len, dist_len)
  tables.s        FCompSet に渡す表のアセンブリ (gFDictSize, gFDict, gFLit*, gFDist*)
  NNNN.fc         シートごとのデータ (8 バイトの頭つき)。--mark 0x80 を付けると先頭に 4 バイト (印 + 生の大きさ 24 ビット) を足す
"""
import argparse
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fcomp as F  # noqa: E402


def tables_asm(dictionary, tables, label='gF'):
    out = ['@ F 方式の共通辞書とハフマンの表 (tools/fcomp_cli.py が作る生成物)', '', '    .section .rodata', '    .align 2',
           '    .global %sDictSize' % label, '%sDictSize:' % label, '    .word %d' % len(dictionary),
           '    .global %sDict' % label, '%sDict:' % label]
    for i in range(0, len(dictionary), 32):
        out.append('    .byte ' + ','.join('0x%02X' % b for b in dictionary[i:i + 32]))
    out += F.ftable_lines(label + 'Lit', tables[0], F.FAST_BITS_LIT)
    out += F.ftable_lines(label + 'Dist', tables[1], F.FAST_BITS_DIST)
    return '\n'.join(out) + '\n'


def pack(out_dir, paths, mark):
    sheets = []
    for p in paths:
        raw = open(p, 'rb').read()
        if len(raw) % F.TILE:
            raise SystemExit('%s: 大きさが 32 バイトの倍数でない' % p)
        sheets.append(raw)
    dictionary, tables, datas = F.encode_all(sheets)
    os.makedirs(out_dir, exist_ok=True)
    open(os.path.join(out_dir, 'dict.bin'), 'wb').write(dictionary)
    json.dump({'lit_len': tables[0], 'dist_len': tables[1], 'sizes': [len(r) for r in sheets]},
              open(os.path.join(out_dir, 'tables.json'), 'w'))
    open(os.path.join(out_dir, 'tables.s'), 'w', newline='\n').write(tables_asm(dictionary, tables))
    tot_raw = tot_c = 0
    for i, (raw, d) in enumerate(zip(sheets, datas)):
        if F.decode(d, dictionary, tables) != raw:
            raise SystemExit('%d 枚目が元に戻らない' % i)
        blob = (bytes([mark]) + len(raw).to_bytes(3, 'little') + d) if mark is not None else d
        open(os.path.join(out_dir, '%04d.fc' % i), 'wb').write(blob)
        tot_raw += len(raw)
        tot_c += len(blob)
    print('%d 枚: %d -> %d バイト (辞書 %d バイトは別)' % (len(sheets), tot_raw, tot_c, len(dictionary)))


def unpack(out_dir):
    dictionary = open(os.path.join(out_dir, 'dict.bin'), 'rb').read()
    j = json.load(open(os.path.join(out_dir, 'tables.json')))
    tables = (j['lit_len'], j['dist_len'])
    for i, size in enumerate(j['sizes']):
        d = open(os.path.join(out_dir, '%04d.fc' % i), 'rb').read()
        if len(d) >= 4 and d[0] not in (0,) and struct.unpack_from('<H', d, 4)[0] * F.TILE == size and \
                int.from_bytes(d[1:4], 'little') == size:
            d = d[4:]                      # --mark 付き
        out = F.decode(d, dictionary, tables)
        print('%04d: %d バイト %s' % (i, len(out), 'OK' if len(out) == size else 'NG'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('pack')
    a.add_argument('out_dir')
    a.add_argument('sheets', nargs='+')
    a.add_argument('--mark', type=lambda x: int(x, 0), default=None)
    b = sub.add_parser('unpack')
    b.add_argument('out_dir')
    args = ap.parse_args()
    if args.cmd == 'pack':
        pack(args.out_dir, args.sheets, args.mark)
    else:
        unpack(args.out_dir)


if __name__ == '__main__':
    main()
