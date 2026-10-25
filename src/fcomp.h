#pragma once

/*
 * 自前の圧縮「F 方式」の展開の中核。形式は docs/FORMAT.md、圧縮は tools/fcomp.py
 * （同じ手順の Python の展開器 decode() で検算している）。
 */

struct BwFTable
{
	u16 first[16];		//長さ n の最初の符号
	u16 count[16];		//長さ n の符号の数
	u16 index[16];		//長さ n の最初の記号が symbols の何番目か
};

//1 組の辞書とハフマンの表（用途ごとに別の組を持てる。圧縮器が .s で書き出す）
struct FCompSet
{
	const u8 *dict;
	u32 dictSize;
	const struct BwFTable *litTable;
	const u16 *litSymbols;
	const u16 *litFast;		//先の 10 ビットで引く表
	const struct BwFTable *distTable;
	const u16 *distSymbols;
	const u16 *distFast;	//先の 8 ビットで引く表
};

//F のデータの頭（8 バイト）: u16 タイルの数・u16 使うタイルの数・u8 番号の幅・u8 0・u16 ビット列の語の数
#define FCOMP_NUM_TILES(d) ((d)[0] | ((d)[1] << 8))
#define FCOMP_NUM_UNIQ(d) ((d)[2] | ((d)[3] << 8))
#define FCOMP_WIDTH(d) ((d)[4])
#define FCOMP_NUM_WORDS(d) ((d)[6] | ((d)[7] << 8))

//data（頭 8 バイトつき）のビット列を out に展開する。ちょうど outSize バイトになれば TRUE
bool8 FCompInflate(const struct FCompSet *set, const u8 *data, u8 *out, u32 outSize);
