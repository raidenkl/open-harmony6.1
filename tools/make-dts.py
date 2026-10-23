#!/usr/bin/env python3
# 生成 OH 版 dts：rk3568-lubancat-2-<v2|v3>-linux.dts
# 基线：out/kernel/src_tmp/linux-6.6/.../rk3568-lubancat-2.dts（本树主线版）
# 用法：LUBANCAT_BOARD=v2 python3 make-dts.py    （默认 v3）
import os, re, pathlib, sys

BOARD = os.environ.get("LUBANCAT_BOARD", "v3").lower()
if BOARD not in ("v2", "v3"):
    sys.exit("LUBANCAT_BOARD 只能是 v2 或 v3")

ROOT = pathlib.Path("/home/dev/ljh/ohos-port/src/ohos")
DTS_DIR = ROOT / "out/kernel/src_tmp/linux-6.6/arch/arm64/boot/dts/rockchip"
SRC = DTS_DIR / "rk3568-lubancat-2.dts"
NAME = f"rk3568-lubancat-2-{BOARD}-linux"
DST_SRC = DTS_DIR / f"{NAME}.dts"
DST_BOARD = ROOT / f"device/board/rockchip/rk3568/kernel/dts/{NAME}.dts"

def remove_block(lines, header_pat):
    """按 header 正则找到块起点，用花括号配平删除整块，返回删除行数"""
    rx = re.compile(header_pat)
    for i, ln in enumerate(lines):
        if rx.match(ln):
            depth = 0
            for j in range(i, len(lines)):
                depth += lines[j].count("{") - lines[j].count("}")
                if depth == 0 and j > i:
                    del lines[i:j + 1]
                    return j - i + 1
            return 0
    return -1

lines = SRC.read_text().splitlines(keepends=True)
for pat in [r"^&combphy0\s*\{", r"^&combphy1\s*\{", r"^&combphy2\s*\{",
            r"^&hdmi_in\s*\{", r"^&hdmi_out\s*\{", r"^&vp0\s*\{",
            r"^&sata0\s*\{", r"^&usb_host0_xhci\s*\{", r"^&usb_host1_xhci\s*\{",
            r"^&pcie3x2\s*\{", r"^&pcie2x1\s*\{", r"^&pcie30phy\s*\{",
            r"^\thdmi-con\s*\{", r"^\taliases\s*\{"]:
    n = remove_block(lines, pat)
    if n < 0:
        print("  WARN 未找到块:", pat)

text = "".join(lines)

if "rk3568-linux.dtsi" not in text:
    text = text.replace('#include "rk3568.dtsi"',
                        '#include "rk3568.dtsi"\n#include "rk3568-linux.dtsi"', 1)

text = text.replace('model = "EmbedFire LubanCat 2";',
                    f'model = "EmbedFire LubanCat 2 {BOARD.upper()}";')
text = text.replace('compatible = "embedfire,lubancat-2", "rockchip,rk3568";',
                    f'compatible = "embedfire,lubancat-2-{BOARD}", "rockchip,rk3568";')

text = text.replace("&usb2phy1_host", "&u2phy1_host").replace("&usb2phy1_otg", "&u2phy1_otg")

text = text.replace("""&uart2 {
	status = "okay";
};""", """&uart2 {
	/* OH 用 fiq-debugger 占用 UART2（serial-id=2），8250 节点必须 disabled */
	status = "disabled";
};""")

def set_delay(txt, node, tx, rx):
    m = re.search(r"(&%s\s*\{)(.*?)(\n\};)" % node, txt, re.S)
    if not m:
        print("  !! 未找到 &%s 块" % node)
        return txt
    body = re.sub(r"tx_delay = <0x[0-9a-fA-F]+>;", f"tx_delay = <0x{tx:02x}>;", m.group(2))
    body = re.sub(r"rx_delay = <0x[0-9a-fA-F]+>;", f"rx_delay = <0x{rx:02x}>;", body)
    return txt[:m.start(2)] + body + txt[m.end(2):]

if BOARD == "v2":
    text = set_delay(text, "gmac0", 0x22, 0x0e)
    text = set_delay(text, "gmac1", 0x22, 0x07)
    board_extra = ""
else:
    text = set_delay(text, "gmac0", 0x42, 0x34)
    text = set_delay(text, "gmac1", 0x4a, 0x31)
    text = text.replace("gpios = <&gpio0 RK_PC7 GPIO_ACTIVE_LOW>;",
                        "gpios = <&gpio1 RK_PA4 GPIO_ACTIVE_LOW>;")
    board_extra = """
/* ---- V3: 外挂 RTC（HYM8563/BM8563MA @0x51），关掉 rk809 片内 RTC ---- */
&i2c0 {
	hym8563: hym8563@51 {
		compatible = "haoyu,hym8563";
		reg = <0x51>;
		#clock-cells = <0>;
		clock-frequency = <32768>;
		clock-output-names = "hym8563";
		status = "okay";
	};
};

&rk809 {
	rtc {
		status = "disabled";
	};
};
"""

text += """
/* ---- OH: HDMI 显式路由（不写 = vop2 零 CRTC = 黑屏），DSI 本轮全关 ---- */
&hdmi_in_vp0 { status = "okay"; };   /* dtsi 默认 disabled，不打开 VP0 分不到 plane */
&hdmi_in_vp1 { status = "disabled"; };
&hdmi { status = "okay"; };

&route_hdmi {
	status = "okay";
	connect = <&vp0_out_hdmi>;
};

/* ---- OH: RGA2 必须打开 ----
 * composer 的 gfx 合成走 librga（display_gfx.c -> importbuffer_fd -> /dev/rga）。
 * rk356x-oh.dtsi 里 rk_rga 默认 disabled，参考板 rk3568-toybrick.dtsi:1726 是 okay。
 * 不开的后果：import dst_handle error -> blit layer 0 failed -> pre composition apply failed
 *            -> 画面永远停在 uboot logo（HDMI 有信号但内容不更新）。
 * 注：rk_rga 节点没有 iommus 属性，不会触发 vendor 内核 rk_iommu_driver_init 的上电 panic。 */
&rk_rga { status = "okay"; };

/* ---- OH: i2s1 引脚复用 ----
 * RK3568 的 i2s1_8ch（rockchip,rk3568-i2s-tdm）由 OH 的 HDF audio 接管：
 * device/board/rockchip/rk3568/audio_drivers/dai/src/rk3568_dai_linux_driver.c
 * 自己 module_platform_driver() 并 match "rockchip,rk3568-i2s-tdm"，
 * 所以内核侧 CONFIG_SND_SOC_ROCKCHIP_I2S_TDM 必须为 n（否则两者抢同一节点）。
 * 这里只负责把 4 根 I2S 引脚复用打开，HDF dai 才有波形。
 *
 * rk809 内置 codec：HDF 的 codec 驱动（audio_drivers/codec/rk809_codec/
 * rk809_codec_linux_driver.c）match 的是 "rockchip,rk817-codec"，
 * 所以 codec 子节点**必须存在且带这个 compatible**，否则它 probe 不到、
 * audio_host 拿不到 codec。但不要加 multicodecs-card 声卡节点——
 * 那是内核 machine driver（CONFIG_SND_SOC_ROCKCHIP_MULTICODECS 已关）。 */
&rk809 {
	rk809_codec: codec {
		#sound-dai-cells = <0>;
		compatible = "rockchip,rk809-codec", "rockchip,rk817-codec";
		clocks = <&cru I2S1_MCLKOUT>;
		clock-names = "mclk";
		hp-volume = <20>;
		spk-volume = <3>;
		capture-volume = <0>;
		status = "okay";
	};
};

&i2s1_8ch {
	pinctrl-names = "default";
	pinctrl-0 = <&i2s1m0_sclktx
		     &i2s1m0_lrcktx
		     &i2s1m0_sdi0
		     &i2s1m0_sdo0>;
};

&dsi0 { status = "disabled"; };
&dsi1 { status = "disabled"; };
&route_dsi0 { status = "disabled"; };
&route_dsi1 { status = "disabled"; };
""" + board_extra

DST_SRC.write_text(text)
DST_BOARD.parent.mkdir(parents=True, exist_ok=True)
DST_BOARD.write_text(text)
print(f"[{BOARD}] 生成 {DST_SRC.name} ({len(text.splitlines())} 行) → 板级目录已同步")
