#!/usr/bin/env bash
# LubanCat 2 (RK3568) OpenHarmony 6.1 移植改动 —— 一键重放
#
# 用途：repo sync 会覆盖 device/soc/rockchip、base/startup/init、build、
#       third_party/parse5 四个仓库里的改动；本脚本把它们重新打回去。
#       device/board/rockchip 与 vendor/rockchip 不属于任何 git 仓库，
#       repo sync 不会碰，但仍从归档解包以保持一致。
#
# 用法：bash patches/apply-all.sh
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SRC="$ROOT/src/ohos"
BOARD="$SRC/device/board/rockchip/rk3568"
VENDOR="$SRC/vendor/rockchip/lubancat_2_v3"

die() { echo "[apply] !! $*" >&2; exit 1; }
ok()  { echo "[apply] $*"; }

[ -d "$SRC" ] || die "找不到源码树：$SRC"

# ---------- 1. 板级 / 产品目录（整目录归档） ----------
mkdir -p "$SRC/device/board/rockchip" "$SRC/vendor/rockchip"

for pair in "device_board_rockchip_rk3568.tar.gz:$SRC/device/board/rockchip:board:$BOARD" \
            "vendor_rockchip_lubancat_2_v3.tar.gz:$SRC/vendor/rockchip:product:$VENDOR"; do
    IFS=: read -r tarball dest kind target <<<"$pair"
    if [ -d "$target" ]; then
        ok "已存在 $kind 目录，跳过解包（要重建先 rm -rf）"
        continue
    fi
    [ -f "$HERE/00-tree/$tarball" ] || die "缺归档 $tarball"
    tar xzf "$HERE/00-tree/$tarball" -C "$dest" || die "解包 $tarball 失败"
    ok "解包 $kind 目录"
done

# ---------- 2. 已有仓库的单文件改动（补丁） ----------
apply_patch() {
    local repo="$1" rel="$2"
    local p="$HERE/$rel"
    [ -f "$p" ] || die "缺补丁 $rel"
    if git -C "$SRC/$repo" apply --reverse --check "$p" >/dev/null 2>&1; then
        ok "已应用，跳过 $rel"
    elif git -C "$SRC/$repo" apply --check "$p" >/dev/null 2>&1; then
        git -C "$SRC/$repo" apply "$p" || die "应用失败 $rel"
        ok "应用 $rel"
    else
        die "无法应用 $rel —— $repo 上下文不匹配（源码可能已更新，需要手工 rebase）"
    fi
}

apply_patch device/soc/rockchip 10-device_soc_rockchip.patch
apply_patch base/startup/init   20-startup_init.patch
apply_patch build               30-build.patch
apply_patch third_party/parse5  40-third_party_parse5.patch
apply_patch kernel/linux/config 50-kernel-audio-config.patch

# ---------- 3. 白名单（不用 patch，hb 会重排 JSON） ----------
python3 "$HERE/tools/add-whitelist.py" || die "白名单处理失败"

# ---------- 4. 从主线 dts 重新生成板级 dts ----------
# 归档里已经带了生成好的 dts，但内核源码树更新后必须重跑，
# 否则会把旧的 dtsi 内容固化进板级 dts。
if [ -f "$ROOT/tools/make-dts.py" ]; then
    ( cd "$ROOT/tools" && LUBANCAT_BOARD=v2 python3 make-dts.py && LUBANCAT_BOARD=v3 python3 make-dts.py ) \
        || die "make-dts.py 执行失败"
    ok "已从主线 dts 重新生成 v2/v3 设备树"
else
    ok "未找到 $ROOT/tools/make-dts.py，沿用归档里的 dts"
fi

echo
ok "完成。建议接着跑：bash $HERE/verify.sh"
