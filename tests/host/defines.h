/* ホスト (PC) でビルドするための defines.h の代わり。src/fcomp.c が使う型だけ */
#pragma once
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint8_t bool8;
#define TRUE 1
#define FALSE 0
