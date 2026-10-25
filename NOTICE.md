# ライセンスと由来

このリポジトリのファイルは、すべて onikoro が新しく書いたもので、MIT License です（`LICENSE`）。

| ファイル | 扱い |
|---|---|
| `src/fcomp.c` `src/fcomp.h` | MIT（onikoro） |
| `tools/fcomp.py` `tools/fcomp_cli.py` | MIT（onikoro） |
| `tests/*` | MIT（onikoro） |
| `examples/*` | MIT（onikoro） |
| `docs/*` `README.md` | MIT（onikoro） |

## CFRU / CFRU-JP について

このリポジトリには、CFRU（Skeli 氏）と CFRU-JP（kapibarasan000 氏）のソースコードは**1 行も含まれていません**。
CFRU 系のビルドに「組み込む側」の手順を `docs/INTEGRATION.md` に書いているだけです。
CFRU・CFRU-JP 自体のライセンスと著作権は、それぞれの作者の元の扱いのままです。組み込んだ ROM を配るときは、
それぞれのリポジトリのライセンスに従ってください。

## 圧縮の部品について

LZ77 と正準ハフマン符号、および長さ・距離の区切りの表（`LEN_BASE` など）は、Deflate（RFC 1951）で公開されている方式と数値に基づきます。
