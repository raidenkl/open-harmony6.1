# LubanCat 2 (RK3568) OpenHarmony 6.1 移植改动归档

把一块野火鲁班猫 2（LubanCat 2 V2/V3，RK3568）接进 OpenHarmony 6.1 标准系统的全部改动，
以可重放的形式固化在这里。

## 为什么需要它

改动分两类，风险不同：

| 类型 | 位置 | `repo sync` 后 |
|---|---|---|
| 新建目录 | `device/board/rockchip/rk3568/`、`vendor/rockchip/lubancat_2_v3/` | 不在任何 git 仓库里，不会被删 |
| 已有仓库的修改 | `device/soc/rockchip`、`base/startup/init`、`build`、`third_party/parse5` | **会被覆盖**，必须重放 |

## 用法

```bash
bash patches/apply-all.sh     # 一键重放（幂等，已应用的会跳过）
bash patches/verify.sh        # 一键校验，全部 OK 才算到位
```

改动完成并上板验证后，更新归档：

```bash
bash patches/make-archive.sh
```

## 内容

```
00-tree/
  device_board_rockchip_rk3568.tar.gz    板级目录整包（含 loader / logo / bootanimation）
  vendor_rockchip_lubancat_2_v3.tar.gz   产品目录整包
10-device_soc_rockchip.patch   显示库两处 vendor 缺陷修复
20-startup_init.patch          /dev/rga 节点权限
30-build.patch                 kernel 模板硬编码 + exec_script 白名单
40-third_party_parse5.patch    tsconfig 类型隔离（防上级 node_modules 干扰）
tools/
  add-whitelist.py             compile_standard_whitelist.json 幂等追加
  make-dts.py                  从主线 dts 生成 v2/v3 板级 dts
  fix-rga-perm.py              历史脚本（/dev/rga 权限，已被 20-startup_init.patch 取代）
  fix-display-crash.py         历史脚本（显示库判空+重试，已被 10-*.patch 取代）
```

## 这批改动解决了什么

按踩坑顺序：

1. **板级/产品目录不存在** → 新建 `device/board/rockchip/rk3568` + `vendor/rockchip/lubancat_2_v3`
2. **框架硬编码 `device/board/hihope/rk3568`** → 改 `build/templates/kernel/ohos_kernel_build.gni`
3. **part 名必须与 subsystem 同名** → 板级/产品 `ohos.build` 统一，白名单补两条
4. **dts 缺 OH bootargs** → 生成时 include `rk3568-linux.dtsi`
5. **HDMI 零 CRTC**（vop2 分不到 plane）→ 开 `&hdmi_in_vp0`、显式 `&route_hdmi`
6. **屏幕停在 uboot logo** → `&rk_rga { status = "okay"; }` + `/dev/rga 0666`
7. **composer_host SIGSEGV 崩溃循环** → 显示库补判空 + open 重试
8. **内核 ThinLTO 缺 `__aarch64_cas4_acq_rel`** → `KCFLAGS=-mno-outline-atomics`

## 注意

- `compile_standard_whitelist.json` **不放进补丁**：hb 每次构建都会重新序列化这个 JSON，
  diff 会变成上千行格式噪声且补丁必然失效，改用 `tools/add-whitelist.py` 幂等追加。
- `make-dts.py` 会在 `apply-all.sh` 末尾自动重跑。它的输入是**当前内核源码树**里的
  `rk3568-lubancat-2.dts`，内核更新后必须重跑，否则板级 dts 会固化成旧内容。
- 换板型改 `device/board/rockchip/rk3568/kernel/board.conf` 一行（`LUBANCAT_BOARD=v2|v3`）。
