@ MIT License (c) 2026 onikoro
@ LZ77 展開の入口で「先頭 1 バイトが F の印」のものだけ自前の展開器へ回す振り分け役の例。
@ ★ 実機未確認の例です。入口の番地・書き換え方は ROM ごとに違うので docs/INTEGRATION.md を読んで自分の ROM で確かめてください。
@
@ 呼び出しの約束 (BIOS の LZ77UnCompWram / LZ77UnCompVram と同じ): r0 = 元 (ヘッダー付き) / r1 = 先
@ ここに来る前に r2 に「VRAM なら 1・WRAM なら 0」を入れておく (入口の 2 つの小さな踏み台がやる)。
@ r2 / r3 は BIOS も壊すので壊してよい。

    .arch armv4t
    .text
    .align 2
    .thumb

    .global LzUnCompDispatch
    .thumb_func
LzUnCompDispatch:
    ldrb r3, [r0]
    cmp r3, #0x80                @ F 方式の印 (好きな値に変えてよい。BIOS の形式 0x10 / 0x20 / 0x30 / 0x50 とぶつからない値)
    beq .Lf
.Lbios:
    cmp r2, #0
    bne .Lvram
    swi 0x11                     @ LZ77UnCompWram
    bx lr
.Lvram:
    swi 0x12                     @ LZ77UnCompVram
    bx lr

.Lf:
    push {r0-r2, lr}
    ldr r3, =FTryDecode          @ examples/f_try_decode.c  → 1 = 展開した (または不正で何もしない) / 0 = F ではない
    bl .Lcallr3
    cmp r0, #0
    pop {r0-r2}
    pop {r3}
    mov lr, r3                   @ 高いレジスタへの mov は旗 (cmp の結果) を変えない
    beq .Lbios
    bx lr

.Lcallr3:
    bx r3

    .pool
