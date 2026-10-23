# LubanCat 2 (RK3568) OpenHarmony 6.1 移植

把野火鲁班猫 2（LubanCat 2 V2/V3，RK3568）接入 OpenHarmony 6.1 标准系统。

基线：OpenHarmony `v6.1-Release`（内核 Linux 6.6，产品名 `lubancat_2_v3`，out 目录 `out/rk3568`）。

## 当前进度

| 模块 | 状态 | 说明 |
|---|---|---|
| 串口 | ✅ | 1500000 8N1，`ttyFIQ0` shell 可用 |
| HDMI | ✅ | 1080p60，launcher 桌面正常，USB 鼠标可操作 |
| eMMC | ✅ | 全部分区挂载，userdata F2FS 正常 |
| 网口 | ✅ | eth1 千兆 DHCP 通、NTP 同步（JL2101 走 generic PHY，无需专用驱动） |
| 音频 | 🔶 | 链路已通（audio_host / rk817-codec / i2s 均就位），待实测出声 |
| 触摸 | ⏸ | 配置就绪，等接上 MIPI 屏验证 |
| USB/RTC | ⏸ | 未开始 |

## 目录结构

```
patches/                     全部源码树改动的可重放归档（核心资产）
  apply-all.sh               一键重放（幂等）
  verify.sh                  一键校验（28 项）
  make-archive.sh            改动完成后重新生成归档
  00-tree/                   板级/产品目录整包（新建目录，不在任何 git 仓库）
  10~50-*.patch              四个仓库的单文件改动补丁
  tools/                     dts 生成器与历史修复脚本
env/                         构建机环境脚本（依赖安装、构建包装、repo 拉取）
docs/                        移植实录（踩坑与排查全过程）
tools/                       一次性改造脚本（已被补丁固化，留作参考）
```

## 在新的源码树上复现

```bash
# 前提：已按 OpenHarmony 官方方式 repo sync 到 OpenHarmony-v6.1-Release，
# 且构建机依赖已装（见 env/）
bash patches/apply-all.sh    # 解包板级/产品目录 + 打补丁 + 白名单 + 重新生成 dts
bash patches/verify.sh       # 28 项全过才继续

# 换板型改一行：device/board/rockchip/rk3568/kernel/board.conf（v2|v3）
bash env/build.sh --product-name lubancat_2_v3 --ccache
```

改动完成、上板验证后更新归档：`bash patches/make-archive.sh`。

## 烧录

产物在 `out/rk3568/packages/phone/images/`，用 RKDevTool / SD_Firmware_Tool 按
`parameter.txt` 分区逐个烧录。首次全量：MiniLoaderAll + parameter + uboot + 全部分区
（userdata 必须烧，fstab 是 `f2fs wait,check`）。只改内核时烧 `boot_linux.img` + `resource.img` 即可。

## 踩坑实录（详见 docs/移植进度-lubancat_2_v3.md）

按踩到的时间顺序，每一条都花了真实排查时间：

1. **part 名必须与 subsystem 同名**，改完 part 名 8 个 BUILD.gn 要同步
2. **camera 依赖触发 gn 白名单** → 首轮摘掉 camera/bluetooth
3. **HDMI 零 CRTC 黑屏**：`hdmi_in_vp0` 在 dtsi 里默认 disabled，不打开 VP0 分不到 plane
4. **屏幕停在 uboot logo**：`rk_rga` 默认 disabled，composer 的 blit 走 librga 直接失败；
   且 `/dev/rga` 默认 0660 root:root，HDF 服务用户打不开，ueventd 要加规则
5. **composer_host SIGSEGV 崩溃循环**：vendor 显示库 `DrmDevice::Create()` 返回 nullptr 后
   漏判空就调 `Init()`；open 还要重试（ueventd 建节点晚于驱动启动的竞态）
6. **内核 ThinLTO 缺 `__aarch64_cas4_acq_rel`**：`KCFLAGS=-mno-outline-atomics`
7. **defconfig 自相矛盾**：`# CONFIG_SOUND is not set` 却开着 59 个 `CONFIG_SND_*` 子项，
   全部失效——整个音频子系统从来没编过
8. **OH 内核补丁按 6.7+ 写**：`snd_soc_dai_driver.probe`、`dai->playback_dma_data` 在 6.6 都没有；
   开了 SOUND 后 `sound/soc/rockchip-oh/` 首次参与编译即报错
9. **内核 ASoC 与 HDF audio 抢设备**：HDF dai 自己 `module_platform_driver()` match
   `rockchip,rk3568-i2s-tdm`，内核那套必须全关
10. **HDF codec 靠 dts 子节点 probe**：`compatible = "rockchip,rk817-codec"` 的 codec 节点
    必须有（MFD 带 `.of_compatible` 的 cell 需要 dts 配对才带 of_node），
    但 machine 声卡节点（multicodecs-card）不能加
11. **`compile_standard_whitelist.json` 不能进补丁**：hb 每次构建重排 JSON，diff 变千行噪声，
    且会把条目归位到别的 bucket；用脚本幂等处理
12. **`out` 目录跟 board 名走**（`out/rk3568`），不跟产品名，删错了白丢一次全量构建

## 其他

- `docs/build-issue-01.md`：构建阶段（SDK 下载、node_modules 污染、OOM）的问题记录
- `docs/移植进度-lubancat_2_v3.md`：从零到桌面再到音频的完整移植流水账
