#include "defines.h"
#include "fcomp.h"

/*
 * 自前の圧縮「F 方式」の展開の中核。圧縮は tools/fcomp.py、形式は docs/FORMAT.md
 *
 * ビット列 = LZ77 ＋ ハフマン（Deflate と同じ長さ・距離の区切り。距離は共通辞書のぶん 65536 まで）。32 ビットずつ・下位ビットから
 * 窓は「共通辞書（ROM）＋ いま展開した分」。距離が展開した分より遠ければ辞書の後ろから読む
 *
 * ★ 書き換え可能な static は使えない（CFRU の ROM 配置では .data / .bss を持てないため）。状態はすべて関数の中の変数
 */

static const u16 sLenBase[29] = {3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258};
static const u8 sLenExtra[29] = {0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0};
static const u16 sDistBase[32] = {1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073,
								  4097, 6145, 8193, 12289, 16385, 24577, 32769, 49153};
static const u8 sDistExtra[32] = {0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13, 14, 14};

#define FC_END 256
#define FC_BAD 0xFFFF

//★ 速く引く表（1 ビットずつ調べると遅い）:
//  先の BITS ビット（読む順 = 下位ビットから）で引く。値 = 記号 | (符号の長さ << 9)。0 なら BITS より長い符号 → 遅い道
#define FC_LIT_FAST_BITS 10		//tools/fcomp.py の FAST_BITS_LIT と同じ
#define FC_DIST_FAST_BITS 8

//遅い道（BITS より長い符号）: 1 ビットずつ（正準ハフマン符号・長さごとの最初の符号と数）。→ 記号 | (長さ << 9)、無ければ FC_BAD
static u32 FCompSlowSym(u32 bits, const struct BwFTable *t, const u16 *symbols)
{
	u32 len, code = 0;

	for (len = 1; len <= 15; ++len)
	{
		code = (code << 1) | ((bits >> (len - 1)) & 1);
		if (code - t->first[len] < t->count[len])	//符号なしの比べ方（code < first なら大きな数になる）
			return symbols[t->index[len] + code - t->first[len]] | (len << 9);
	}
	return FC_BAD;
}

//★ ビットの状態（buf・n・p）は関数の中の変数（レジスタ）に置き、記号を引く所はループの中に直接書く
//  （関数を呼んで状態をメモリに通すと 1 記号 約 49 命令かかった・エミュレータでの測定）
//buf を 25 ビット以上にする（1 バイトずつ足す）。頭の語の数より先は 0（壊れたデータで暴走しない・範囲の確かめで止める）
#define FC_REFILL() 	while (n <= 24) { buf |= (u32) ((p < end) ? *p++ : 0) << n; n += 8; }
#define FC_DROP(k) do { buf >>= (k); n -= (k); } while (0)

bool8 FCompInflate(const struct FCompSet *set, const u8 *data, u8 *out, u32 outSize)
{
	const u8 *p = data + 8;
	const u8 *end = p + FCOMP_NUM_WORDS(data) * 4;	//頭の語の数より先は読まない
	const u16 *litFast = set->litFast;
	const u16 *distFast = set->distFast;
	u32 buf = 0, n = 0, pos = 0, i;

	for (;;)
	{
		u32 e, sym;

		FC_REFILL();
		e = litFast[buf & ((1 << FC_LIT_FAST_BITS) - 1)];
		if (e == 0 && (e = FCompSlowSym(buf, set->litTable, set->litSymbols)) == FC_BAD)
			return FALSE;
		FC_DROP(e >> 9);
		sym = e & 0x1FF;

		if (sym < 256)
		{
			if (pos >= outSize)
				return FALSE;
			out[pos++] = sym;
		}
		else if (sym == FC_END)
			break;
		else if (sym <= 285)
		{
			u32 lc = sym - 257;
			u32 len = sLenBase[lc];
			u32 dist, dc, x;

			x = sLenExtra[lc];
			if (x != 0)
			{
				FC_REFILL();
				len += buf & ((1 << x) - 1);
				FC_DROP(x);
			}
			FC_REFILL();
			e = distFast[buf & ((1 << FC_DIST_FAST_BITS) - 1)];
			if (e == 0 && (e = FCompSlowSym(buf, set->distTable, set->distSymbols)) == FC_BAD)
				return FALSE;
			FC_DROP(e >> 9);
			dc = e & 0x1FF;
			if (dc >= 32)
				return FALSE;
			dist = sDistBase[dc];
			x = sDistExtra[dc];
			if (x != 0)
			{
				FC_REFILL();
				dist += buf & ((1 << x) - 1);
				FC_DROP(x);
			}
			if (pos + len > outSize || dist > pos + set->dictSize)
				return FALSE;
			//辞書から読むぶん（距離が展開した分より遠い）と、展開した分から読むぶんに分けて写す（1 バイトごとに判定しない）
			if (dist > pos)
			{
				const u8 *src = set->dict + set->dictSize - (dist - pos);
				u32 fromDict = dist - pos;

				if (fromDict > len)
					fromDict = len;
				len -= fromDict;
				for (i = 0; i < fromDict; ++i)
					out[pos++] = src[i];
			}
			if (len != 0)
			{
				u8 *dst = out + pos;
				const u8 *src = dst - dist;

				pos += len;
				do
				{
					*dst++ = *src++;
				} while (--len != 0);
			}
		}
		else
			return FALSE;
	}
	return pos == outSize;
}
