#!/usr/bin/env bash
# 从当前源码树重新生成归档（改动完成、上板验证通过后跑一次）
# 用法：bash patches/make-archive.sh
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SRC="$ROOT/src/ohos"

[ -d "$SRC" ] || { echo "找不到源码树 $SRC" >&2; exit 1; }
mkdir -p "$HERE/00-tree"

echo "== 工具脚本 =="
mkdir -p "$HERE/tools"
for f in make-dts.py fix-rga-perm.py fix-display-crash.py; do
    if [ -f "$ROOT/tools/$f" ]; then
        cp -f "$ROOT/tools/$f" "$HERE/tools/" && echo "  $f"
    fi
done

echo "== 整目录归档（新建目录，不在任何 git 仓库里） =="
tar czf "$HERE/00-tree/device_board_rockchip_rk3568.tar.gz" \
    -C "$SRC/device/board/rockchip" rk3568
tar czf "$HERE/00-tree/vendor_rockchip_lubancat_2_v3.tar.gz" \
    -C "$SRC/vendor/rockchip" lubancat_2_v3
du -h "$HERE/00-tree/"*.tar.gz

echo "== 补丁 =="
git -C "$SRC/device/soc/rockchip" diff > "$HERE/10-device_soc_rockchip.patch"
git -C "$SRC/base/startup/init"   diff > "$HERE/20-startup_init.patch"
# 注意：compile_standard_whitelist.json 故意排除（hb 每次构建重排格式，
# 会产生上千行噪声且补丁极易失效），由 tools/add-whitelist.py 幂等处理。
git -C "$SRC/build" diff -- \
    templates/kernel/ohos_kernel_build.gni \
    core/gn/ohos_exec_script_allowlist.gni > "$HERE/30-build.patch"
git -C "$SRC/third_party/parse5"  diff > "$HERE/40-third_party_parse5.patch"
# 内核 defconfig：CONFIG_SOUND/CONFIG_SND 总开关（原来与 59 个 SND_* 子项自相矛盾）
git -C "$SRC/kernel/linux/config" diff > "$HERE/50-kernel-audio-config.patch"

for p in "$HERE"/*.patch; do
    printf '%-40s %4d 行\n' "$(basename "$p")" "$(wc -l < "$p")"
done

echo
echo "完成。产物在 $HERE"
