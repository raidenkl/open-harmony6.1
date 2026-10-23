#!/usr/bin/env python3
# P2/P3: build_kernel.sh 注入 dts、parameter 分区表、白名单
import json, pathlib

ROOT = pathlib.Path("/home/dev/ljh/ohos-port/src/ohos")
BK = ROOT / "device/board/rockchip/rk3568/kernel/build_kernel.sh"
PARAM = ROOT / "device/board/rockchip/rk3568/loader/parameter.txt"
WL = ROOT / "build/compile_standard_whitelist.json"

s = BK.read_text()
changed = []

# 1) patch 之后注入板级 dts
anchor = "    patch -p1 < ${KERNEL_PATCH}\n"
inject = anchor + """
    # --- LubanCat 2 V3: 注入板级 dts（下一段的 model_list 已改为引用它）---
    cp -f ${BUILD_SCRIPT_PATH}/dts/rk3568-lubancat-2-v3-linux.dts \\
          ${KERNEL_SRC_TMP_PATH}/arch/arm64/boot/dts/rockchip/
"""
if "LubanCat 2 V3: 注入板级 dts" not in s:
    assert anchor in s, "patch 锚点未找到"
    s = s.replace(anchor, inject, 1)
    changed.append("注入 dts cp")

# 2) 把 make-ohos.sh 的 model_list 指向我们的 dts
anchor2 = "eval $MAKE_OHOS_ENV ./make-ohos.sh TB-RK3568X0"
inject2 = """# --- LubanCat 2 V3: 用鲁班猫 dts 替换 toybrick dts（产物名仍是 toybrick.dtb，uboot 不需改）---
sed -i 's#rk3568-toybrick-x0-linux  Image#rk3568-lubancat-2-v3-linux Image#' make-ohos.sh

""" + anchor2
if "用鲁班猫 dts 替换 toybrick dts" not in s:
    assert anchor2 in s, "make-ohos 锚点未找到"
    s = s.replace(anchor2, inject2, 1)
    changed.append("model_list sed")

# 3) 打包 boot_linux 前同步 extlinux append（防 uboot 覆盖 DT bootargs 时丢 hardware=）
anchor3 = "../kernel/src_tmp/${KERNEL_VERSION}/make-boot.sh .."
inject3 = """# --- LubanCat 2 V3: 同步 extlinux append，确保 hardware=rk3568 / PARTUUID 不丢 ---
EXTLINUX_CONF=${KERNEL_SRC_TMP_PATH}/boot_linux/extlinux/extlinux.conf
if [ -f "${EXTLINUX_CONF}" ]; then
    sed -i 's#^[[:space:]]*append .*#append earlycon=uart8250,mmio32,0xfe660000 console=ttyFIQ0 ohos.boot.eng_mode=on root=PARTUUID=614e0000-0000 hardware=rk3568 default_boot_device=fe310000.sdhci rw rootwait#' "${EXTLINUX_CONF}"
    echo "[lubancat] extlinux.conf append synced"
fi

""" + anchor3
if "lubancat] extlinux.conf append synced" not in s:
    assert anchor3 in s, "make-boot 锚点未找到"
    s = s.replace(anchor3, inject3, 1)
    changed.append("extlinux append")

BK.write_text(s)
print("build_kernel.sh:", changed or "无变化")

# 4) parameter.txt: userdata 起点 0x01308000 -> 0x006BE000（8GB eMMC 也装得下）
p = PARAM.read_text()
if "-@0x01308000(userdata:grow)" in p:
    p = p.replace("-@0x01308000(userdata:grow)", "-@0x006BE000(userdata:grow)")
    PARAM.write_text(p)
    print("parameter.txt: userdata 起点已改为 0x006BE000")
elif "-@0x006BE000(userdata:grow)" in p:
    print("parameter.txt: 已是 0x006BE000")
else:
    print("parameter.txt: !! 未找到 userdata 项，需人工检查")
print("  uuid 行:", [l for l in p.splitlines() if l.startswith("uuid:")])

# 5) 白名单
d = json.loads(WL.read_text())
lst = d["bundle_subsystem_error"]
add = ["device/board/rockchip/rk3568/ohos.build", "vendor/rockchip/lubancat_2_v3/ohos.build"]
n = [x for x in add if x not in lst]
if n:
    lst.extend(n)
    WL.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    print("whitelist: 追加", n)
else:
    print("whitelist: 已存在")
