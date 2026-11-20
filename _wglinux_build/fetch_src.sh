#!/usr/bin/env bash
# 从 cgit plain 端点批量拉取 wireguard-linux 核心源码（stable 分支）
set -u
BASE="https://git.zx2c4.com/wireguard-linux/plain"
REF="stable"
DEST="wireguard-linux-src"
mkdir -p "$DEST/drivers/net/wireguard" "$DEST/include/uapi/linux" "$DEST/Documentation/networking"

FILES_DRV="Kconfig Makefile main.c device.c peer.c allowedips.c allowedips.h noise.c noise.h messages.h send.c receive.c socket.c sysfs.c timers.c ratelimiter.c ratelimiter.h version.h queueing.h cookie.c cookie.h chacha20.c poly1305.c curve25519.c blake2s.c siphash.c dmessage.c hashtable.h selftest/allowedips.h"
FILES_UAPI="wireguard.h"
FILES_DOC="wireguard.rst"

ok=0; fail=0
for f in $FILES_DRV; do
  mkdir -p "$DEST/drivers/net/wireguard/$(dirname "$f")"
  out="$DEST/drivers/net/wireguard/$f"
  code=$(curl -sL -w '%{http_code}' "$BASE/drivers/net/wireguard/$f?h=$REF" -o "$out")
  if [ "$code" = "200" ] && [ -s "$out" ]; then ok=$((ok+1)); else fail=$((fail+1)); echo "FAIL drv/$f ($code)"; rm -f "$out"; fi
done
for f in $FILES_UAPI; do
  code=$(curl -sL -w '%{http_code}' "$BASE/include/uapi/linux/$f?h=$REF" -o "$DEST/include/uapi/linux/$f")
  if [ "$code" = "200" ] && [ -s "$DEST/include/uapi/linux/$f" ]; then ok=$((ok+1)); else fail=$((fail+1)); echo "FAIL uapi/$f ($code)"; rm -f "$DEST/include/uapi/linux/$f"; fi
done
for f in $FILES_DOC; do
  code=$(curl -sL -w '%{http_code}' "$BASE/Documentation/networking/$f?h=$REF" -o "$DEST/Documentation/networking/$f")
  if [ "$code" = "200" ] && [ -s "$DEST/Documentation/networking/$f" ]; then ok=$((ok+1)); else fail=$((fail+1)); echo "FAIL doc/$f ($code)"; rm -f "$DEST/Documentation/networking/$f"; fi
done
echo "OK=$ok FAIL=$fail"
echo "=== 下载清单 ==="
find "$DEST" -type f | sort
