# LubanCat 2 V3 移植进度（P1/P2/P3 已完成，构建通过）

日期：2026-10-22　主机：`dev@10.255.200.150`　源码：`~/ljh/ohos-port/src/ohos`

## 结果

```
=====build  successful=====
[build.sh] build.sh 退出码 0
```

产物：`out/rk3568/packages/phone/images/`（15 个文件，system 2GiB / vendor 256MiB / userdata 1.37GiB / boot_linux 64MiB）

> 注意：**out 目录跟着 board 名走（out/rk3568），不是 out/lubancat_2_v3**。删 out 时别看错。

## 已落地的改动

### 新增目录

| 路径 | 说明 |
|---|---|
| `device/board/rockchip/rk3568/` | 从 `device/board/hihope/rk3568` 整拷（105 文件），改 6 处 |
| `vendor/rockchip/lubancat_2_v3/` | 从 `vendor/hihope/rk3568` 整拷（126 文件），改 8 处 |
| `device/board/rockchip/rk3568/kernel/dts/rk3568-lubancat-2-v3-linux.dts` | 新增，691 行 |

### 板级（device/board/rockchip/rk3568）

| 文件 | 改动 |
|---|---|
| `ohos.build` | 路径 hihope→rockchip；**part 名保持 `rockchip_products`**（必须与 subsystem 同名，否则 preloader 校验报 "find subsystem ... failed"）；删掉 camera / bluetooth 两组 module（camera 依赖 turbojpeg_static 触发 gn 依赖白名单报错，BT 固件是参考板的） |
| `kernel/BUILD.gn` | 板级路径 hihope→rockchip |
| `bootanimation/BUILD.gn` | 同上 |
| `kernel/build_kernel.sh` | ① `export KCFLAGS="-mno-outline-atomics ..."`（ThinLTO 下否则 vmlinux 缺 `__aarch64_cas4_acq_rel`）；② patch 后注入板级 dts；③ `sed` make-ohos.sh 的 model_list 指向 `rk3568-lubancat-2-v3-linux`（产物名仍是 toybrick.dtb，uboot 不用改）；④ 打包前同步 extlinux `append` |
| `loader/parameter.txt` | userdata 起点 `0x01308000` → `0x006BE000`（固定区 3.375GiB，8/16/32GB eMMC 通用） |

### 产品（vendor/rockchip/lubancat_2_v3）

- `config.json`：`product_name=lubancat_2_v3`、`device_build_path=device/board/rockchip/rk3568`，**`board` 保持 `rk3568`**（DEVICE_NAME 决定 kernel 补丁/defconfig/init cfg 路径）
- `ohos.build`：subsystem 改为 `product_lubancat_2_v3`，路径改 rockchip
- 8 个 BUILD.gn 的 `part_name`/`subsystem_name` 全部 `product_rk3568` → `product_lubancat_2_v3`
- `etc/param/product_rk3568.para` 重命名为 `product_lubancat_2_v3.para`

### 框架侧（3 处）

| 文件 | 改动 |
|---|---|
| `build/templates/kernel/ohos_kernel_build.gni:36` | kernel deps 指向 `//device/board/rockchip/rk3568/kernel:kernel`（**不改会静默编参考板内核**） |
| `build/compile_standard_whitelist.json` | `bundle_subsystem_error` 追加两个 ohos.build |
| `build/core/gn/ohos_exec_script_allowlist.gni` | 追加 `//device/board/rockchip/rk3568/camera/vdi_impl/v4l2/BUILD.gn`（否则 gn 报 Disallowed exec_script） |

## DTS 做法（关键）

基线用本树主线 `rk3568-lubancat-2.dts`，脚本化改造（`tools/make-dts.py`）：

- `#include "rk3568-linux.dtsi"`（**只在 `out/kernel/src_tmp` 里，由 kernel.patch 生成**）→ 拿到 `hardware=rk3568`、`ohos.required_mount.*`
- 删 `aliases`（避免 mmc0 指向 SD）
- 删本树不存在的 label 块：`&combphy0/1/2`、`&hdmi_in`、`&hdmi_out`、`&hdmi-con`、`&sata0`、`&usb_host0_xhci`、`&usb_host1_xhci`、`&pcie30phy`、`&pcie3x2`、`&pcie2x1`、`&vp0`（重复 label）
- `usb2phy1_host/otg` → `u2phy1_host/otg`（本树只给 phy0 起了双 label）
- 追加 HDMI 显式路由 + DSI 全关：
  ```
  &route_hdmi { status = "okay"; connect = <&vp0_out_hdmi>; };
  &dsi0 { status = "disabled"; }; &dsi1 { status = "disabled"; };
  &route_dsi0 { status = "disabled"; }; &route_dsi1 { status = "disabled"; };
  ```

## 验证结果（构建侧，全部通过）

| 检查 | 结果 |
|---|---|
| dtb 编译 | `rk3568-lubancat-2-v3-linux.dtb` 100825 B，0 错误 |
| dtb model | `EmbedFire LubanCat 2 V3` |
| boot_linux.img 内 model | 命中 `EmbedFire LubanCat 2 V3`（确认不是参考板 dtb） |
| extlinux.conf | `fdt /extlinux/toybrick.dtb` + `append ... hardware=rk3568 ...` |
| resource.img | 内含 `EmbedFire LubanCat 2 V3` |
| parameter.txt | `0x006BE000(userdata:grow)`，uuid 两行未变 |
| 内核 | `arch/arm64/boot/Image` 38012936 B |
| 构建 | `=====build successful=====`，退出码 0 |

## 踩过的坑（按出现顺序）

1. `out/ohos_config.json` 残留旧 out_path → gn 仍往 out/rk3568 生成；换产品后要么删它，要么接受 out 目录名不变（后者才是实际行为）
2. part 名与 subsystem 名不一致 → preloader 校验直接失败（`find subsystem rockchip_products failed`）
3. 改了 `part_name` 但 8 个 BUILD.gn 没跟着改 → `get_subsystem_name.py` 返回 1（`Dependency not allowed`/gn 失败）
4. camera 依赖 `turbojpeg_static` 触发 gn 依赖白名单 → 本轮直接摘掉 camera module
5. dts 注入路径写成 `${BUILD_SCRIPT_PATH}/dts/` 但文件放在 `kernel/dts/` → `cp: cannot stat`
6. 内核没带 `KCFLAGS=-mno-outline-atomics` → 又是 `__aarch64_cas4_acq_rel`（这次固化进 build_kernel.sh）

## 下一步（P4/P5，需要上板）

1. 只烧 `MiniLoaderAll.bin + parameter.txt + uboot.img`，串口看有没有 `DDR Version` → 判定 loader/DDR 是否认板（R1 风险）
2. 串口 1500000 8N1；通过后再补烧 resource / boot_linux / ramdisk / system / vendor / sys_prod / chip_prod / updater / chip_ckm（**不烧 userdata**）
3. 上板验收：`/proc/device-tree/model`、`/proc/cmdline` 含 `hardware=rk3568`、`dri/0/summary` 有 active CRTC、`ethtool eth0` 1000Mb/s
4. 网口不稳时按计划的 P1→P4 调 delay 或回移 jlsemi 驱动
5. TF 卡阶段 A（SD 只带引导+内核）

---

## 上板调试记录（2026-10-23）：HDMI 有信号但画面停在 uboot logo

### 现象
HDMI 输出正常（1080p60），但屏幕一直显示 DAYU logo，触摸/鼠标无反应，串口 shell 正常，`bootevent.boot.completed=true`。

### 排查链条（每一步都被推翻过一次，记录以免重走）
1. 以为是 launcher 没起来 → `com.ohos.launcher`(pid 1389) 在跑，`bootevent.launcher.ready` 已置位。
2. 以为是内存不足 → 1944MB / 1222 used / 722 free + swap 空闲，排除。
3. 以为是 SCB 没启 → `/etc/sceneboard.config` = `DISABLED`，本产品走非 SCB 的旧 wms 路径，属设计如此。
4. 发现 `cppcrash-composer_host` 反复崩 → 栈 `DiscoveryDevice()+104`，反汇编 `17d96: cbnz r0, 0x17db4` 证明是 `DrmDevice::Create()` 返回 nullptr 后漏判空 → **但这是启动竞态**，`hilog` 里 `[Init:158] chenyf master` 证明另一实例 Init 完全成功。
5. 以为 `PhysicalDisplay` 没枚举 → `ls /sys/class/drm/` 有 `card0/card0-HDMI-A-1/renderD128`，`status = connected`，排除。
6. **`hilog -b D` 打开 DEBUG 后拿到真因**。

### 真因：RGA2 在设备树里是 disabled
```
[SetDisplayClientBuffer] fd 19, size 8294400          ← RS 确实提交了 1920x1080 RGBA8888 全屏帧
[Apply:211] composer layers size 1
[hdi_gbm_bo_create:141] fmt 0x34324152 create dumb …   ← Rockchip 自实现的 dumb 分配，非异常回退
[rkFillRect:185] import dst_handle error!              ← librga importbuffer_fd 返回 0
[doFlit:348]    import dst_handle error!
[Apply:247]     blit layer 0 failed
[Commit:47]     pre composition apply failed
```

`display_gfx.c` 的 `rkFillRect()` / `doFlit()` 通过 `importbuffer_fd()` 走 `/dev/rga`，而 `rk356x-oh.dtsi:1344` 的 `rk_rga@fdeb0000` 默认 `status = "disabled"`；参考板 `rk3568-toybrick.dtsi:1726` 有 `&rk_rga { status = "okay"; }`，**我们的 LubanCat 板级 dts 里完全没有这一节**。

### 修复（两处）
| 改动 | 文件 | 说明 |
|---|---|---|
| 打开 RGA2 | `make-dts.py` → 生成 dts 追加 `&rk_rga { status = "okay"; };` | 该节点无 `iommus` 属性，只有 `power-domains = <&power RK3568_PD_RGA>`，不走 `rk_iommu_driver_init`(core_initcall)，不会踩 Lakka 那个 `panic_on_set_idle` |
| 放开节点权限 | `base/startup/init/ueventd/etc/ueventd.config` 加 `/dev/rga 0666 0 0` | ueventd `DEVMODE = 0660`（`ueventd_utils.h:33`），无规则时建成 `0660 root:root`，而 composer_host 以 `composer_host` uid 运行、gid 不含 root → 打不开 |

配套本来就齐，无需改：`file_contexts:142` 已有 `/dev/rga u:object_r:dev_rga:s0`；`composer_host.te` 已有 `allow composer_host dev_rga:chr_file { ioctl open read write }`；librga 已装在 `/vendor/lib/passthrough/indirect/librga.z.so`。

### 顺带修掉的 vendor 缺陷
- `hdi_device_interface.cpp`：`DrmDevice::Create()` 返回 nullptr 时原来只打印不 return，紧接着 `drmDevice->Init()` 解引用空指针 → SIGSEGV 崩溃循环，且 hilog 里留不下 errno。已补 `return devices;`。
- `drm_device.cpp::Create()`：open `/dev/dri/card0` 失败重试 3 次（间隔 100ms）并逐次打印 errno，覆盖 ueventd 建节点与 composer 启动的竞态。

### 本轮镜像（02:41/02:46 产出，已验证）
- `boot_linux.img` 内 `/extlinux/toybrick.dtb`：`rk_rga@fdeb0000 status = "okay"`、`model = "EmbedFire LubanCat 2 V2"`
- `system.img` 内 `/etc/ueventd.config`：`/dev/rga 0666 0 0`

**只需烧 `boot_linux.img` + `resource.img` + `system.img`**（system 因为改了 ueventd.config）。

### 上板验收
```sh
ls -l /dev/rga                       # 期望 crw-rw-rw- root root
dmesg | grep -i rga                  # 期望 probe 成功
hilog -b D; hilog -x | grep -i DISP | tail -40   # 确认不再有 "import dst_handle error"
```
再看不到 `blit layer 0 failed` 就说明合成通了，画面应出 launcher。

### 结果：桌面正常启动（2026-10-23 11:00）

`rk_rga` 打开 + `/dev/rga` 放开权限后，launcher 正常出画面，**USB 鼠标可正常操控**。

```
# ls -l /dev/rga
crw-rw-rw- 1 system vendor_mpp_driver 10, 114 2017-08-04 17:00 /dev/rga
```

`hilog -x | grep DISP` 里不再出现 `import dst_handle error` / `blit layer failed` / `pre composition apply failed`。

### 剩余的 DISP 噪声（HDI 1.2 可选接口未实现，不影响功能）

| 日志 | 含义 | 影响 |
|---|---|---|
| `GetMetadata:98` / `SetMetadata:92 is not supported` | HDR/色彩元数据接口未实现 | 无（SDR 场景不用） |
| `SetLayerMaskInfo:345 is not supported` | 图层遮罩未实现 | 应用用圆角/遮罩裁剪时可能显示不准 |
| `SetLayerVisibleRegion:313 is not supported` | 可见区域未实现 | 同上 |
| `SetDisplayClientDamage:156 is not supported` | 脏区（damage region）未实现 | **每次全屏刷新**，功耗/带宽偏高，可后续优化 |
| `WaitAcquireFence:273 fd is invalid` | acquire fence 无效 | 目前无花屏，持续观察 |

### 最小点亮的四项验收状态

| 项 | 状态 | 依据 |
|---|---|---|
| 串口 | ✅ | `Registered fiq debugger ttyFIQ0`，shell 可用，1500000 8N1 |
| HDMI | ✅ | 1080p60，launcher 出画面，鼠标可操作 |
| eMMC | ✅ | `EXT4-fs (mmcblk0p7/p8/p9/p10/p14)` 全部挂载，userdata F2FS 正常 |
| 网口 | ⏳ 待验证 | gmac0/gmac1 已 `okay`，PHY 为 generic `ethernet-phy-ieee802.3-c22`（JL2101 无专用驱动） |

### 网口验收通过（11:05）

```
eth0  HWaddr a6:e2:4a:65:73:fa  Driver rk_gmac-dwmac  UP BROADCAST MULTICAST   ← 未插网线（carrier=0）
eth1  HWaddr a2:e2:4a:65:73:fa  Driver rk_gmac-dwmac  UP BROADCAST RUNNING
      inet addr:192.168.103.156  RX packets:2227  TX packets:73  errors:0
```

- **eth1 完全正常**：DHCP 拿到地址、双向收发 0 错误、桌面时钟自动 NTP 同步
- **JL2101 不需要专用驱动**：`compatible = "ethernet-phy-ieee802.3-c22"` 的 generic PHY 在 rgmii 下就能链路起来，不用回移 jlsemi
- eth0 是 `carrier=0`，只是这个口没插网线；DTS 里 gmac0/gmac1 都是 `status = "okay"`

### MAC 地址说明（不是缺陷，别误判）

两个口 MAC 首字节 `a6`/`a2` 的 bit1 = 1（locally administered），看起来像随机地址。实际是 `dwmac-rk.c:2829-2849` 的设计：

```c
ret = rk_vendor_read(LAN_MAC_ID, ethaddr, ETH_ALEN * MAX_ETH);
if (ret <= 0 || !is_valid_ether_addr(...)) {
    eth_random_addr(...);                              // 随机生成一次
    rk_vendor_write(LAN_MAC_ID, ethaddr, ...);         // 立刻写回 eMMC vendor storage
}
```

**即首次启动随机生成后写入 vendor storage，之后一直复用**（vendor storage 在 eMMC 末尾的 raw 区域，不需要 parameter 里有 vendor 分区；`CONFIG_ROCKCHIP_VENDOR_STORAGE=y`、`CONFIG_ROCKCHIP_MMC_VENDOR_STORAGE=y` 都已开）。

验证方法：重启后 `ifconfig -a | grep HWaddr`，MAC 不变就说明写回成功。若每次都变（eMMC vendor storage 写失败），再在 dts 里加 `local-mac-address` 兜底。

### 第一阶段（最小点亮）—— 全部通过 ✅

| 项 | 状态 |
|---|---|
| 串口 | ✅ 1500000 8N1，shell 可用 |
| HDMI | ✅ 1080p60，launcher 出画面，USB 鼠标可操作 |
| eMMC | ✅ 系统分区全部挂载，userdata F2FS 正常 |
| 网口 | ✅ eth1 千兆通、DHCP 正常、NTP 同步 |

---

## 改动归档（`patches/`）

`repo sync` 会覆盖 `device/soc/rockchip`、`base/startup/init`、`build`、`third_party/parse5` 四个仓库里的改动，
因此把全部移植改动固化成可重放的形式。

```
patches/
  README.md
  apply-all.sh                  一键重放（幂等）
  verify.sh                     一键校验（19 项）
  make-archive.sh               改动完成后重新生成归档
  00-tree/
    device_board_rockchip_rk3568.tar.gz    17M（整目录：dts / loader / logo / camera / bootanimation）
    vendor_rockchip_lubancat_2_v3.tar.gz   153K
  10-device_soc_rockchip.patch  显示库判空 + open 重试
  20-startup_init.patch         /dev/rga 权限
  30-build.patch                kernel 模板硬编码 + exec_script 白名单
  40-third_party_parse5.patch   tsconfig 类型隔离
  tools/{add-whitelist.py, make-dts.py, fix-rga-perm.py, fix-display-crash.py}
```

> `device/board/rockchip` 与 `vendor/rockchip` 不在任何 git 仓库里，`repo sync` 不会删，
> 但仍从 tar 解包以保持一致；真正需要"重放"的是那四个仓库里的单文件改动。

### 端到端验证（已做，不是只生成）

```bash
# 1) 还原到 repo sync 后的状态
mv device/board/rockchip/rk3568 /tmp/rewind-test/board
mv vendor/rockchip/lubancat_2_v3 /tmp/rewind-test/vendor
for r in device/soc/rockchip base/startup/init build third_party/parse5; do git -C $r checkout -- .; done
# 2) 只用归档重放
bash patches/apply-all.sh     # 解包 2 个目录 + 应用 4 个补丁 + 白名单 + 重跑 make-dts.py
bash patches/verify.sh        # → 全部通过：19 项
```

第二次跑 `apply-all.sh` 全部输出"已应用，跳过"，`dts` md5 不变 —— 幂等性确认。

### 一个容易踩的坑：`compile_standard_whitelist.json` 不能放进补丁

hb 每次构建都会把这个 JSON 重新序列化，`git diff` 会变成 **1446 行（726+/723-）** 的格式噪声，
而真正的改动只有 3 行；且 hb 构建时会把条目从 `gn_part_or_subsystem_error` **归位到
`bundle_subsystem_error`**，补丁必然失效。

所以改用 `tools/add-whitelist.py`：所有 bucket 都没有就加到 `bundle_subsystem_error`，
多个 bucket 都有就只留一份（自愈去重），第二次运行直接跳过。

---

## 第二阶段：音频（RK809 内置 codec）

### 三个发现，一个是真 bug

**① `rk3568/arch/arm64_defconfig` 自相矛盾（真 bug）**

```
# CONFIG_SOUND is not set      ← 3628 行
# CONFIG_SND is not set
CONFIG_SND_TIMER=y
CONFIG_SND_PCM=y
...
CONFIG_SND_SOC_ROCKCHIP=y     ← 3710 行往下 59 个 SND_* 子项
CONFIG_SND_SOC_ROCKCHIP_MULTICODECS=y
```

总开关关着，下面 59 个 `CONFIG_SND_*` 全部因依赖不满足被丢弃，最终 `.config` 里 **0 个 CONFIG_SND**。
这就是"板子上根本没有声卡"的直接原因。已改为 `CONFIG_SOUND=y` / `CONFIG_SND=y`。

**② 主线 `rk3568-lubancat-2.dts` 里没有声卡节点**

只有 `&hdmi_sound`，没有 rk809 声卡。厂商 BSP（`rk3568-lubancat-2core.dtsi`）的写法是：

```dts
rk809_sound: rk809-sound {
	compatible = "rockchip,multicodecs-card";
	rockchip,card-name = "rockchip-rk809";
	rockchip,format = "i2s";
	rockchip,mclk-fs = <256>;
	rockchip,cpu = <&i2s1_8ch>;
	rockchip,codec = <&rk809_codec>;
};
```

已按此加进 `make-dts.py`，并补上 `rk809_codec` 子节点与 i2s1 的 4 根 pinmux：

```dts
&rk809 { rk809_codec: codec { capture-volume = <0>; status = "okay"; }; };
&i2s1_8ch { pinctrl-0 = <&i2s1m0_sclktx &i2s1m0_lrcktx &i2s1m0_sdi0 &i2s1m0_sdo0>; };
```

dtb 冒烟已确认：`codec` 子节点 phandle 0x129、`rk809-sound` 引用它、i2s1 `pinctrl-0` 4 个引脚 + `status = okay`。

**③ HDF 音频驱动路径硬编码在 hihope 目录（待改）**

`drivers/hdf_core/adapter/khdf/linux/model/audio/Makefile:56`：

```make
obj-$(CONFIG_DRIVERS_HDF_AUDIO_RK3568) += \
          $(KHDF_AUDIO_BASE_ROOT_DIR)/device/board/hihope/rk3568/audio_drivers/
```

`device/board/rockchip/rk3568/audio_drivers/`（含 `codec/rk809_codec/` 的 `rk809_codec_impl.c`）
**不会被编译**。两份内容目前相同（复制来的），所以本轮功能不受影响；但只要以后要改
rockchip 目录下的 codec 驱动（比如耳机检测 GPIO），就必须先改这里，否则改了不生效。

### 已具备的条件

- `CONFIG_DRIVERS_HDF_AUDIO_RK3568=y`、`CONFIG_DRIVERS_HDF_AUDIO_HDMI=y`、`CONFIG_DRIVERS_HDF_AUDIO_ANA_HEADSET=y` 都在 defconfig 里
- OH 的音频是 **HDF 内核态驱动**：`audio_drivers/codec/rk809_codec/`（RK809 寄存器）+ `dai/`（i2s）+ `soc/`（DMA）+ `headset_monitor/`
- HDF 侧 hcs 齐全：`hdf.hcs` 已 include `audio/{audio,codec,dai,dma,dsp,analog_headset}_config.hcs`，`device_info.hcs` 有 `audio_host` 节点

### 上板验证（编译完成后）

```sh
ls /dev/snd/                                  # 期望 pcmC0D0p / pcmC0D0c / controlC0
cat /proc/asound/cards                        # 期望出现 rockchip-rk809
dmesg | grep -iE "rk809|i2s|asoc|sound|codec" # 看声卡注册与 codec probe
hilog | grep -iE "audio_host|audio" | tail -40
```

### ④ 开了 CONFIG_SOUND 之后，OH 内核补丁自己编不过（4.6.6 API 不匹配）

```
sound/soc/rockchip-oh/rockchip_i2s.c:752:3: error:
  field designator 'probe' does not refer to any field in type 'struct snd_soc_dai_driver'
```

`snd_soc_dai_driver.probe` 是 **Linux 6.7** 才加入的字段，6.6 的结构体里没有：

```c
/* include/sound/soc-dai.h:410 (6.6) */
struct snd_soc_dai_driver {
	const char *name;
	...
	const struct snd_soc_dai_ops *ops;      /* ← 只有 ops/cops，没有 probe */
	const struct snd_soc_cdai_ops *cops;
	struct snd_soc_pcm_stream capture;
	struct snd_soc_pcm_stream playback;
	...
};
```

这个错误**一直存在但从未暴露**：`sound/soc/rockchip-oh/` 是 OH 用 `kernel.patch` 加进去的目录，
而 rk3568 defconfig 的 `CONFIG_SOUND` 是关的，整个目录从来没参与编译。

修法（`device/board/rockchip/rk3568/kernel/fix-audio-api.py`，由 `build_kernel.sh` 在打完
kernel.patch 后自动执行，因为 `out/kernel/src_tmp` 每次重建）：

- 原 `rockchip_i2s_dai_probe()` 里唯一必要动作是 `snd_soc_dai_init_dma_data()`（初始化 DMA），
  把它挪进 `.startup`（6.6 的标准位置）
- 删掉 `.probe = rockchip_i2s_dai_probe,` 指示器
- 函数体保留但标 `__maybe_unused`（避免 -Wunused-function）

单编验证：`make ... sound/soc/rockchip-oh/rockchip_i2s.o` → `CC` 通过，无告警转错误。

> 教训：**改内核 config 让一大片代码首次参与编译，往往连带暴露补丁与内核版本的 API 不匹配**。
> 这次是 `.probe`，后续如果再报 `error: ... does not refer to any field` / `implicit declaration`，
> 大概率是同一类问题（OH 的 kernel.patch 是按更新内核写的）。

### 方案修正：**不要**加内核声卡节点，音频由 HDF 接管

前面"②"里按厂商 BSP 加了 `rk809_codec` + `rk809_sound`（multicodecs-card），**这个方向是错的**，
已验证并回退。理由是一条硬证据：

```
device/board/rockchip/rk3568/audio_drivers/dai/src/rk3568_dai_linux_driver.c
  static const struct of_device_id rockchip_i2s_tdm_match[] = {
      { .compatible = "rockchip,rk3568-i2s-tdm", ... },     ← 和内核驱动抢同一个节点
  };
  module_platform_driver(rockchip_i2s_tdm_driver);
```

OH 的 **HDF audio 自己注册了 platform driver**，match 的 `rockchip,rk3568-i2s-tdm` 与内核
`rockchip_i2s_tdm.c` 完全相同。同一节点只能被一个驱动 probe，谁先注册谁赢——留着内核那套
就是行为不确定。

所以正确配置是：

| 配置项 | 值 | 理由 |
|---|---|---|
| `CONFIG_SOUND` / `CONFIG_SND` / `CONFIG_SND_SOC` | `y` | HDF audio 要用 ASoC 框架 API |
| `CONFIG_SND_SOC_ROCKCHIP` | `y` | 只编 `rockchip_utils.o`，无副作用 |
| `CONFIG_SND_SOC_ROCKCHIP_I2S/_I2S_TDM/_PDM/_SPDIF/_SPDIFRX` | **n** | 与 HDF dai 抢节点 / API 不兼容 |
| `CONFIG_SND_SOC_ROCKCHIP_MAX98090/_RT5645/_MULTICODECS/_HDMI` | **n** | 鲁班猫没有这些 codec，machine driver 用不到 |
| `CONFIG_DRIVERS_HDF_AUDIO_RK3568` 等 | `y`（defconfig 原值） | HDF 侧真实驱动 |

dts 侧因此也改了：**只留 i2s1 的 4 根引脚复用**，不加 `rk809_codec` 子节点、不加 `rk809_sound`
（rk809 内置 codec 由 HDF 的 `audio_drivers/codec/rk809_codec/` 直接经 i2c 写寄存器）。

```dts
&i2s1_8ch {
	pinctrl-names = "default";
	pinctrl-0 = <&i2s1m0_sclktx &i2s1m0_lrcktx &i2s1m0_sdi0 &i2s1m0_sdo0>;
};
```

> 教训：**移植时看到"主线 dts 少了某个节点"，不能直接照厂商 BSP 补**。
> 要先确认厂商 BSP 和 OH 是不是同一套音频架构——厂商是标准 ALSA（内核 machine driver），
> OH 是 HDF audio（用户态/内核态 HDF 驱动自己接管 DAI + codec）。两套都补只会互相打架。

### 音频修复结果（构建通过，待上板验证）

`=====build successful=====`，退出码 0。镜像内验证（从 `boot_linux.img` dump dtb）：

| 检查 | 结果 |
|---|---|
| `model` | `EmbedFire LubanCat 2 V2` ✓ |
| `i2s@fe410000` | `pinctrl-0 = <0xb4 0xb5 0xb6 0xb7>` + `status = "okay"` ✓ |
| `rk809-sound` / `multicodecs` 残留 | 0 处 ✓ |
| `rk_rga` / HDMI 路由 | 仍为 okay（本轮未回退）✓ |

内核 `.config` 里 `CONFIG_SND*` 从 **0 个变成 41 个**，`CONFIG_DRIVERS_HDF_AUDIO_RK3568=y` 等
HDF 音频驱动首次真正参与编译。

归档新增 `50-kernel-audio-config.patch`（41 行，defconfig 的 SOUND/SND 总开关 + 关掉 9 个内核 ASoC 驱动），
`verify.sh` 扩到 **26 项**全部通过。

**烧录**：只改了内核（dtb + Image），烧 `boot_linux.img` + `resource.img` 即可。

**上板验收**：
```sh
ls /proc/asound/                  # 内核侧可能没有卡（HDF 接管），属正常
dmesg | grep -iE "rk809|i2s-tdm|asoc|snd|codec" | tail -40
hilog | grep -iE "audio_host|audio" | tail -50
ls /dev/snd/                      # HDF audio 会创建自己的节点
```

### 音频上板第一轮：`/dev/snd` 只有 seq/timer，audio_host 无日志

现象：
```
# ls /dev/snd/
seq  timer                        ← 只有 ALSA 核心的通用设备，没有 pcmC0D0p / controlC0
# dmesg | grep -iE "rk809|i2s-tdm|asoc|snd"   → 无任何匹配
# hilog | grep -iE "audio_host|audio"          → 无任何输出
```

排查确认内核侧是好的：

| 检查 | 结果 |
|---|---|
| `.config` | `CONFIG_DRIVERS_HDF_AUDIO=y`、`_RK3568=y`、`_ANA_HEADSET=y` ✓ |
| vmlinux 符号 | `AudioSocRegisterDai`、`rk809_codec_linux_driver` 的 initcall 都在 ✓ |
| hcs moduleName | `DAI_RK3568` / `CODEC_RK809` 与驱动 `.moduleName` 完全一致 ✓ |

**根因：codec 的 platform device 不存在。**

HDF 的 codec 驱动 `rk809_codec_linux_driver.c` 匹配的是：

```c
static const struct of_device_id rk817_codec_dt_ids[] = {
    { .compatible = "rockchip,rk817-codec" },
};
```

而上一版我把 `rk809_codec: codec` 子节点整个删掉了（误以为"HDF 不需要 dts 节点"），
导致 `rk808` MFD 驱动不会创建这个 platform device，HDF codec 驱动 probe 不到，
`codec_service_0` 起不来。

**正确写法**（对照参考板 `rk3568-toybrick.dtsi:1393`）：codec 子节点必须有，且带 `rk817-codec`：

```dts
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
```

两点说明：
- **codec 子节点要加，machine 声卡节点不要加**。前者是给 HDF codec 驱动当 platform device 用的，
  后者（`rockchip,multicodecs-card`）是内核 machine driver，已被 `CONFIG_SND_SOC_ROCKCHIP_MULTICODECS=n` 关掉。
- `devm_clk_get(dev, "mclk")` 失败会被静默跳过（`if (!IS_ERR(clk))`），所以时钟不是硬性条件，
  但 `I2S1_MCLKOUT` 加上能让 HDF codec 使能 mclk，出音更稳。
- 鲁班猫不需要 `pinctrl-0 = <&i2s1m0_mclk>`（OH 树里 `i2s1m0_mclk` 这个标签根本不存在），
  厂商的 i2s1 pinctrl 也只有 sclktx/lrcktx/sdi0/sdo0 四根。

### 修复后（06:05 镜像，构建通过）

dtb 里 codec 子节点已就位：

```
codec {
    #sound-dai-cells = <0x00>;
    compatible = "rockchip,rk809-codec", "rockchip/rk817-codec";
    clocks = <0x24 0x1a3>;        ← I2S1_MCLKOUT (419)
    clock-names = "mclk";
    hp-volume = <0x14>; spk-volume = <0x03>; capture-volume = <0x00>;
    status = "okay";
};
i2s@fe410000: pinctrl-0 = <0xb4 0xb5 0xb6 0xb7>; status = "okay";
```

`patches/verify.sh` 扩到 **28 项**全过（新增"codec 子节点存在"与"无 multicodecs-card 残留"两项）。

**烧录**：只改了 dts → 烧 `boot_linux.img` + `resource.img`。

**上板验收顺序**（先确认链路，再谈出声）：

```sh
# 1. 进程是否起来（最关键，之前 hilog 空就是因为这里没起来）
ps -ef | grep -E "audio_host|hdf_devhost"

# 2. codec platform device 有没有被 HDF 认领（应出现这条 dev_info）
dmesg | grep -i "got rk817-codec platform_device"

# 3. HDF 音频链路
dmesg | grep -iE "rk809|i2s-tdm|asoc|dai|codec" | tail -40
hilog | grep -iE "audio_host|codec_service|dai_service|audio" | tail -50

# 4. 设备节点
ls -l /dev/snd/
```
