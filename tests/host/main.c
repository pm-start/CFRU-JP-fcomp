/* ホスト (PC) で src/fcomp.c を動かす検算用。tests/host_c_check.py が生成する tables.inc と sheets を読む */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "defines.h"
#include "../../src/fcomp.h"
#include "tables.inc"

int main(int argc, char **argv)
{
	/* 入力: argv[1] = パックしたシートの並び (u32 データ長, u32 生の大きさ, データ, 期待する生データ) */
	FILE *f = fopen(argv[1], "rb");
	struct FCompSet set = {gFDict, sizeof(gFDict), &gFLitTable, gFLitSymbols, gFLitFast, &gFDistTable, gFDistSymbols, gFDistFast};
	u32 hdr[2];
	int n = 0, bad = 0;

	while (fread(hdr, 4, 2, f) == 2)
	{
		u8 *data = malloc(hdr[0]), *want = malloc(hdr[1]), *out = calloc(hdr[1] + 1, 1);

		fread(data, 1, hdr[0], f);
		fread(want, 1, hdr[1], f);
		/* 展開先は 1 バイトの余りを置き、はみ出し書き込みも見る */
		if (!FCompInflate(&set, data, out, hdr[1]) || memcmp(out, want, hdr[1]) != 0 || out[hdr[1]] != 0)
		{
			printf("NG %d\n", n);
			++bad;
		}
		/* 大きさを 1 小さくして渡すと失敗して返ること */
		memset(out, 0, hdr[1] + 1);
		if (FCompInflate(&set, data, out, hdr[1] - 1))
		{
			printf("NG(短い出力が通った) %d\n", n);
			++bad;
		}
		free(data); free(want); free(out);
		++n;
	}
	printf("%d sheets, %d NG\n", n, bad);
	return bad != 0;
}
