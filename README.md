# CFRU-JP-fcomp

GBA ROM ハック向けの、**4bpp タイルシート用の自前の圧縮「F 方式」**（展開器 C・圧縮器 Python）と、CFRU 系のビルドへの組み込み方です。

- 作者: onikoro
- ライセンス: MIT（`LICENSE`、由来の一覧は `NOTICE.md`）
- 対象: CFRU（Skeli 氏）/ CFRU-JP（kapibarasan000 氏）系のビルド。これらのコード自体は含みません。

## どんな圧縮か

キャラクターの絵のようなタイルシートは、同じタイルが何度も出てきます。F 方式は次を組み合わせます。

1. シートの中の同じタイルを 1 つにまとめる（タイル番号の並びを別に持つ）
2. LZ77 + ハフマン（Deflate と同じ区切り）
3. 多くのシートに出るタイルを集めた**共通辞書**（ROM に 1 つ）を LZ77 の窓の手前に置く
4. ハフマンの表は全シートで 1 組

BIOS の LZ77 は辞書も専用のハフマンも持たないので、同じ種類の絵が大量にある ROM では、より小さくできる可能性があります。
縮み方は絵の性質しだいです。自作の図形で作ったテスト（`tests/test_roundtrip.py`）では 81,408 バイトが約 24,600 バイトになりました（合成データの数字で、実際の絵の縮み方ではありません。圧縮のたびに数十バイト変わることがあります）。

展開は Thumb の C で、BIOS の LZ77 より遅くなります。速さが要る場面（画面の切り替わりで大きなシートを読む等）は、実機で確かめてください。

## 中身

```
src/fcomp.c, fcomp.h        展開器 (C)
tools/fcomp.py              圧縮器 + 検算用の展開器 decode() (Python)
tools/fcomp_cli.py          コマンドライン (pack / unpack)
examples/lz_dispatch.s      LZ77 の入口に差し込む振り分け役の例 (Thumb)
examples/f_try_decode.c     F のデータを生のシートに戻す例 (VRAM 対応)
tests/test_roundtrip.py     Python だけの往復の検算
tests/host_c_check.py       PC の C コンパイラで展開器を動かす検算
docs/FORMAT.md              データ形式
docs/INTEGRATION.md         CFRU への組み込み方
```

## 使い方（最短）

```
python tools/fcomp_cli.py pack out sheet_a.bin sheet_b.bin --mark 0x80   # 圧縮
python tools/fcomp_cli.py unpack out                                      # 展開して往復を確認
python tests/test_roundtrip.py                                            # 検算 (Python のみ)
python tests/host_c_check.py                                              # 検算 (C コンパイラが要る。無ければ SKIP)
```

Python 3 だけで動きます（外部ライブラリなし）。組み込みは `docs/INTEGRATION.md` を読んでください。

## 確認していること／していないこと

- 確認: Python の圧縮 → Python の展開で元に戻る / Python の圧縮 → PC 向けにビルドした C の展開で元に戻る（どちらも自作の図形のテストデータ）
- 未確認（このリポジトリの範囲では）: 実機・エミュレータでの動作。`examples/` は組み込みの例で、コンパイルが通ることしか確かめていません。

## 注意

- 変更を加えた ROM の配布の可否は、元になる ROM・ビルド環境（CFRU など）の扱いに従ってください。
- 絵のデータは含みません。テストは自作の図形です。
