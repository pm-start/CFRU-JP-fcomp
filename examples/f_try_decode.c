/* MIT License (c) 2026 onikoro
 * F 方式のシートを「LZ77 と同じ形のヘッダー付き」で受け取り、生のタイルシートに展開する例。
 * ★ 実機未確認の例です (コンパイルが通ることと、展開の手順が tools/fcomp.py の decode() と同じことだけを確かめています)。
 *
 * データの形: [印 1 バイト][生の大きさ 24 ビット (リトルエンディアン)][F のデータ (docs/FORMAT.md)]
 *   ・tools/fcomp_cli.py pack --mark 0x80 が、この形のファイルを作る
 *   ・VRAM には 1 バイトの書き込みが効かないので、VRAM へは作業用の入れ物に展開してから 16 ビットずつ写す
 */
#include "defines.h"
#include "fcomp.h"

#define F_MARK 0x80

//tools/fcomp_cli.py が書き出す tables.s のシンボル
extern const struct BwFTable gFLitTable, gFDistTable;
extern const u16 gFLitSymbols[], gFLitFast[], gFDistSymbols[], gFDistFast[];
extern const u8 gFDict[];
extern const u32 gFDictSize;
extern void *Malloc(u32 size);			//CFRU 側の関数 (名前と引数は自分の環境で確かめる)
extern void Free(void *p);

//body = [使うタイル × 32 バイト][タイル番号の並び] から、生のシート out (タイルの数 × 32 バイト) を作る
static void FExpandTiles(const u8 *body, u8 *out, u32 numTiles, u32 numUniq, u32 width)
{
	const u8 *idx = body + numUniq * 32;
	u32 i, k;

	for (i = 0; i < numTiles; ++i)
	{
		u32 j = (width == 1) ? idx[i] : (idx[2 * i] | (idx[2 * i + 1] << 8));

		for (k = 0; k < 32; ++k)
			out[i * 32 + k] = body[j * 32 + k];
	}
}

//→ 1 = F のデータとして扱った / 0 = F ではない (呼び元が BIOS に渡す)
u32 FTryDecode(const u8 *src, u8 *dst, u32 vram)
{
	u32 rawSize, numTiles, numUniq, width, bodySize;
	const u8 *data;
	u8 *body, *sheet;
	struct FCompSet set;

	if (src[0] != F_MARK)
		return 0;
	set.dict = gFDict;
	set.dictSize = gFDictSize;
	set.litTable = &gFLitTable;
	set.litSymbols = gFLitSymbols;
	set.litFast = gFLitFast;
	set.distTable = &gFDistTable;
	set.distSymbols = gFDistSymbols;
	set.distFast = gFDistFast;
	rawSize = src[1] | (src[2] << 8) | (src[3] << 16);
	data = src + 4;
	numTiles = FCOMP_NUM_TILES(data);
	numUniq = FCOMP_NUM_UNIQ(data);
	width = FCOMP_WIDTH(data);
	if ((width != 1 && width != 2) || numTiles * 32 != rawSize || numUniq == 0 || numUniq > numTiles)
		return 1;							//不正でも BIOS には渡さない (F のデータを LZ77 として読んでしまうため)
	bodySize = numUniq * 32 + numTiles * width;

	body = Malloc(bodySize);
	sheet = vram ? Malloc(rawSize) : dst;
	if (body == NULL || sheet == NULL)
	{
		if (body != NULL)
			Free(body);
		if (vram && sheet != NULL)
			Free(sheet);
		return 1;
	}
	if (FCompInflate(&set, data, body, bodySize))
	{
		u32 i;

		FExpandTiles(body, sheet, numTiles, numUniq, width);
		if (vram)
			for (i = 0; i < rawSize; i += 2)
				*(u16 *) (dst + i) = sheet[i] | (sheet[i + 1] << 8);
	}
	Free(body);
	if (vram)
		Free(sheet);
	return 1;
}
