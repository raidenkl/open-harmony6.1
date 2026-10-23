#!/usr/bin/env python3
"""调整 rk3568 defconfig 的音频配置，配合 OH 的 HDF audio 架构。

背景：
1. rk3568 defconfig 原本 `# CONFIG_SOUND/# CONFIG_SND is not set`，与下面 59 个
   CONFIG_SND_* 子项自相矛盾 -> 整个音频子系统从来没编过。
2. 一旦打开，OH 通过 kernel.patch 塞进 `sound/soc/rockchip-oh/` 的那套 Rockchip
   ASoC 驱动编不过：它们用的是 Linux 6.7+ 的 API
   （`snd_soc_dai_driver.probe`、`snd_soc_dai.playback_dma_data` 直连访问、
   `rockchip_i2s_tdm_set_mclk/mclk_calibrate`），6.6 里都没有。
3. 而且这整套驱动和 OH 自己的 HDF audio 抢设备：
   `device/board/rockchip/rk3568/audio_drivers/dai/src/rk3568_dai_linux_driver.c`
   里 `module_platform_driver()` + `of_match_table = "rockchip,rk3568-i2s-tdm"`，
   与内核 `rockchip_i2s_tdm.c` 争同一个节点。

所以正确做法是：保留 ASoC 框架（CONFIG_SND/CONFIG_SND_SOC，HDF audio 要用），
关掉内核这套 Rockchip DAI / machine 驱动，由 HDF audio 接管。
"""
import pathlib
import sys

P = pathlib.Path("/home/dev/ljh/ohos-port/src/ohos/kernel/linux/config/linux-6.6/rk3568/arch/arm64_defconfig")

# 要关掉的：全部是内核侧 Rockchip ASoC DAI / machine 驱动
# （RK3568 上 HDF audio 自己实现了 dai + codec，且这些文件与 6.6 API 不兼容）
TURN_OFF = [
    "SND_SOC_ROCKCHIP_I2S",           # 旧 i2s（rk3288 系），且 i2s.c 需打补丁
    "SND_SOC_ROCKCHIP_I2S_TDM",       # 与 HDF dai 抢 rk3568-i2s-tdm，且 API 不兼容
    "SND_SOC_ROCKCHIP_PDM",           # 无 PDM 硬件需求，API 不兼容
    "SND_SOC_ROCKCHIP_SPDIF",         # 无 SPDIF 需求，API 不兼容
    "SND_SOC_ROCKCHIP_SPDIFRX",       # 同上
    "SND_SOC_ROCKCHIP_MAX98090",      # 鲁班猫没有 max98090
    "SND_SOC_ROCKCHIP_RT5645",        # 鲁班猫没有 rt5645
    "SND_SOC_ROCKCHIP_MULTICODECS",   # 内核 machine driver，HDF 不用
    "SND_SOC_ROCKCHIP_HDMI",          # HDMI 音频本轮不做
]

s = P.read_text()
changed = []

for name in TURN_OFF:
    on_line = "CONFIG_%s=y\n" % name
    off_line = "# CONFIG_%s is not set\n" % name
    if off_line in s:
        continue
    if on_line not in s:
        print("[audio-cfg] !! %s 不在 defconfig 里，跳过" % name)
        continue
    s = s.replace(on_line, off_line, 1)
    changed.append(name)

if changed:
    P.write_text(s)
    for n in changed:
        print("[audio-cfg] - CONFIG_%s" % n)
else:
    print("[audio-cfg] 无需改动")

print("---- 核对（应只剩 ROCKCHIP=y）----")
for line in P.read_text().splitlines():
    if line.lstrip("# ").startswith("CONFIG_SND_SOC_ROCKCHIP") or line.startswith(("# CONFIG_SND_SOC_ROCKCHIP", "CONFIG_SND_SOC_ROCKCHIP")):
        print("   ", line)
