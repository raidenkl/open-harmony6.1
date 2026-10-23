#!/usr/bin/env bash
# 校验 LubanCat 2 (RK3568) 移植改动是否完整到位
# 用法：bash patches/verify.sh
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SRC="$ROOT/src/ohos"

PASS=0
FAIL=0

check_file() {     # check_file <路径> <说明>
    if [ -f "$1" ]; then printf '  \033[32mOK\033[0m   %s\n' "$2"; PASS=$((PASS+1))
    else printf '  \033[31mMISS\033[0m %s  (%s)\n' "$2" "$1"; FAIL=$((FAIL+1)); fi
}

check_grep() {     # check_grep <文件> <模式> <说明>
    if [ ! -f "$1" ]; then printf '  \033[31mMISS\033[0m %s  (无文件 %s)\n' "$3" "$1"; FAIL=$((FAIL+1))
    elif grep -qF -- "$2" "$1"; then printf '  \033[32mOK\033[0m   %s\n' "$3"; PASS=$((PASS+1))
    else printf '  \033[31mFAIL\033[0m %s  (缺 "%s" 于 %s)\n' "$3" "$2" "$1"; FAIL=$((FAIL+1)); fi
}

echo "== 1. 板级 / 产品目录 =="
check_file "$SRC/device/board/rockchip/rk3568/ohos.build"                  "board ohos.build"
check_file "$SRC/device/board/rockchip/rk3568/kernel/board.conf"           "board.conf（板型开关）"
check_file "$SRC/device/board/rockchip/rk3568/kernel/build_kernel.sh"      "build_kernel.sh"
check_file "$SRC/device/board/rockchip/rk3568/kernel/fix-audio-api.py"     "音频 ASoC API 兼容补丁脚本"
check_file "$SRC/device/board/rockchip/rk3568/kernel/dts/rk3568-lubancat-2-v2-linux.dts" "v2 dts"
check_file "$SRC/device/board/rockchip/rk3568/kernel/dts/rk3568-lubancat-2-v3-linux.dts" "v3 dts"
check_file "$SRC/vendor/rockchip/lubancat_2_v3/config.json"                "product config.json"

echo "== 2. 内核构建链 =="
check_grep "$SRC/device/board/rockchip/rk3568/kernel/build_kernel.sh" \
           "-mno-outline-atomics"                                          "KCFLAGS 固化（防 __aarch64_cas4_acq_rel）"
check_grep "$SRC/device/board/rockchip/rk3568/kernel/build_kernel.sh" \
           '${BUILD_SCRIPT_PATH}/kernel/dts/'                              "dts 注入路径（board 级 kernel/dts）"
check_grep "$SRC/device/board/rockchip/rk3568/kernel/build_kernel.sh" \
           'LUBANCAT_DTS='                                                 "板型 → dts 名映射"
check_grep "$SRC/device/board/rockchip/rk3568/kernel/build_kernel.sh" \
           'fix-audio-api.py'                                              "音频 API 补丁已接入构建流程"

echo "== 3. 设备树关键节点（v2）=="
DTS="$SRC/device/board/rockchip/rk3568/kernel/dts/rk3568-lubancat-2-v2-linux.dts"
check_grep "$DTS" '&rk_rga { status = "okay"; };'                          "RGA2 打开（否则 blit 失败、画面停 logo）"
check_grep "$DTS" '&hdmi_in_vp0 { status = "okay"; };'                     "HDMI 输入端口（否则 vop2 零 CRTC）"
check_grep "$DTS" 'connect = <&vp0_out_hdmi>;'                             "HDMI 显式路由到 VP0"
check_grep "$DTS" 'pinctrl-0 = <&i2s1m0_sclktx'                            "i2s1 四根引脚复用（HDF dai 用）"
check_grep "$DTS" 'compatible = "rockchip,rk809-codec", "rockchip,rk817-codec";' \
           "codec 子节点（HDF codec 驱动靠它 probe）"
if grep -q 'rockchip,multicodecs-card' "$DTS"; then
    printf '  \033[31mFAIL\033[0m 不应有 multicodecs-card 声卡节点（内核 machine driver 已关）\n'
    FAIL=$((FAIL+1))
else
    printf '  \033[32mOK\033[0m   无内核 machine 声卡节点（HDF 接管）\n'; PASS=$((PASS+1))
fi

echo "== 3b. 内核音频配置（HDF 接管，内核 ASoC 驱动全关）=="
DEFCFG="$SRC/kernel/linux/config/linux-6.6/rk3568/arch/arm64_defconfig"
check_grep "$DEFCFG" "CONFIG_SOUND=y"                                      "CONFIG_SOUND 总开关（原与子项矛盾）"
check_grep "$DEFCFG" "CONFIG_SND=y"                                        "CONFIG_SND 总开关"
check_grep "$DEFCFG" "# CONFIG_SND_SOC_ROCKCHIP_I2S_TDM is not set"        "关掉内核 i2s_tdm（与 HDF dai 抢节点）"
check_grep "$DEFCFG" "# CONFIG_SND_SOC_ROCKCHIP_MULTICODECS is not set"    "关掉内核 machine driver"

echo "== 4. 显示库 vendor 缺陷修复 =="
DISPLAY="$SRC/device/soc/rockchip/rk3568/hardware/display/src/display_device"
check_grep "$DISPLAY/hdi_device_interface.cpp" "skip init"                 "DiscoveryDevice 判空"
check_grep "$DISPLAY/drm_device.cpp"           "open failed try"           "Create open 重试 + errno"

echo "== 5. 设备节点权限 =="
check_grep "$SRC/base/startup/init/ueventd/etc/ueventd.config" \
           "/dev/rga 0666 0 0"                                             "/dev/rga 权限（否则 composer_host 打不开）"

echo "== 6. 框架改动 =="
check_grep "$SRC/build/templates/kernel/ohos_kernel_build.gni" \
           "device/board/rockchip/rk3568/kernel:kernel"                    "kernel 模板去掉 hihope 硬编码"
check_grep "$SRC/build/core/gn/ohos_exec_script_allowlist.gni" \
           "device/board/rockchip/rk3568/camera/vdi_impl/v4l2/BUILD.gn"   "exec_script 白名单"
check_grep "$SRC/build/compile_standard_whitelist.json" \
           "device/board/rockchip/rk3568/ohos.build"                       "part 命名白名单"
check_grep "$SRC/third_party/parse5/packages/parse5/tsconfig.json" \
           '"types": []'                                                   "parse5 类型隔离（防上级 node_modules 干扰）"

echo
if [ "$FAIL" -eq 0 ]; then
    printf '\033[32m全部通过：%d 项\033[0m\n' "$PASS"
    exit 0
else
    printf '\033[31m有 %d 项未通过（通过 %d）\033[0m\n' "$FAIL" "$PASS"
    exit 1
fi
