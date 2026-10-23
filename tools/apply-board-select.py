#!/usr/bin/env python3
# 让 build_kernel.sh 支持 V2/V3 选板；并写入 board.conf
import pathlib

R = pathlib.Path("/home/dev/ljh/ohos-port/src/ohos")
BK = R / "device/board/rockchip/rk3568/kernel/build_kernel.sh"
CONF = R / "device/board/rockchip/rk3568/kernel/board.conf"

s = BK.read_text()

# 1) 在 KCFLAGS 之后加板型解析（env 优先，其次 board.conf，默认 v3）
anchor = 'export KCFLAGS="-mno-outline-atomics ${KCFLAGS:-}"\n'
block = anchor + '''# 板型选择：环境变量 > board.conf > 默认 v3
BOARD_CONF=${BUILD_SCRIPT_PATH}/kernel/board.conf
if [ -f "${BOARD_CONF}" ]; then . "${BOARD_CONF}"; fi
LUBANCAT_BOARD="${LUBANCAT_BOARD:-v3}"
LUBANCAT_DTS="rk3568-lubancat-2-${LUBANCAT_BOARD}-linux"
echo "[lubancat] board=${LUBANCAT_BOARD} dts=${LUBANCAT_DTS}"
'''
if "LUBANCAT_DTS=" not in s:
    assert anchor in s
    s = s.replace(anchor, block, 1)

# 2) dts 注入改成变量
old_cp = """    # --- LubanCat 2 V3: 注入板级 dts（下一段的 model_list 已改为引用它）---
    cp -f ${BUILD_SCRIPT_PATH}/kernel/dts/rk3568-lubancat-2-v3-linux.dts \\
          ${KERNEL_SRC_TMP_PATH}/arch/arm64/boot/dts/rockchip/
"""
new_cp = """    # --- LubanCat: 注入板级 dts（V2/V3 由 LUBANCAT_BOARD 决定）---
    cp -f ${BUILD_SCRIPT_PATH}/kernel/dts/${LUBANCAT_DTS}.dts \\
          ${KERNEL_SRC_TMP_PATH}/arch/arm64/boot/dts/rockchip/
"""
if old_cp in s:
    s = s.replace(old_cp, new_cp, 1)

# 3) sed 改成按字段替换（换板时可重复执行）
old_sed = """# --- LubanCat 2 V3: 用鲁班猫 dts 替换 toybrick dts（产物名仍是 toybrick.dtb，uboot 不需改）---
sed -i 's#rk3568-toybrick-x0-linux  Image#rk3568-lubancat-2-v3-linux Image#' make-ohos.sh
"""
new_sed = """# --- LubanCat: 把 make-ohos.sh 里 TB-RK3568X0 那行的 dtb 名换成本板（产物名仍是 toybrick.dtb）---
sed -i -E "s#(TB-RK3568X0[[:space:]]+arm64[[:space:]]+0xfe660000[[:space:]]+)[^[:space:]]+#\\1${LUBANCAT_DTS}#" make-ohos.sh
grep -E "TB-RK3568X0" make-ohos.sh | head -1
"""
if old_sed in s:
    s = s.replace(old_sed, new_sed, 1)
elif "TB-RK3568X0[[:space:]]" not in s:
    print("WARN: 未找到旧的 sed 行，请人工检查")

BK.write_text(s)
print("build_kernel.sh 已更新")

# 4) board.conf：当前板子是 V2
CONF.write_text("""# 目标板型：v2 | v3（build_kernel.sh 会读取；环境变量 LUBANCAT_BOARD 可覆盖）
LUBANCAT_BOARD=v2
""")
print("board.conf ->", CONF.read_text().strip().replace("\n", " | "))

for i, l in enumerate(s.splitlines(), 1):
    if "LUBANCAT" in l:
        print(f"  {i}: {l[:120]}")
