# 构建问题 01：`./build.sh --product-name rk3568` 失败

日期：2026-10-21　主机：dev@10.255.200.150　源码：`~/ljh/ohos-port/src/ohos`（OpenHarmony-6.1-Release）

## 现象

```
out/rk3568/error.log:
ninja: error: '../../prebuilts/ohos-sdk/linux/23/native/sysroot/usr/lib/arm-linux-ohos/libbundle_ndk.z.so',
  needed by 'web/webview/libnweb_ohos_adapter.z.so', missing and no known rule to make it
```

## 原因一：`prebuilts/ohos-sdk/linux/23` 整个目录不存在

- `build/version.gni:17` → `api_version = "23"`
- `build/ohos_var.gni:349` → `current_sdk_home = "//prebuilts/ohos-sdk/linux/${api_version}"`
- webview/nweb 用到的 `libbundle_ndk.z.so` 等 native 库来自这个**预编译 SDK**，源码树里没有对应构建目标（"no known rule"）
- `prebuilts/` 下只有 clang/python/rustc 等工具链，`ohos-sdk` 缺失 → 该目录既没下载也没编过

## 原因二：自己编 SDK 会先死在 parse5（已修）

`--product-name ohos-sdk` 在 `[11955/24001] third_party/parse5:build_parse5_library` 失败：

```
third_party/parse5/packages/parse5/node_modules/typescript/bin/tsc --project .../parse5 ...
../../../../../node_modules/@types/node/ffi.d.ts(94,21): error TS1139: Type parameter declaration expected.
...（数百行 TS1005/TS1139/TS1434）
```

- `ffi.d.ts` 是 `@types/node` **v26.3.0** 才有的文件，语法需要较新的 TypeScript
- OH 自带的是老版本 tsc，且 parse5 自己没有 `node_modules/@types`
- tsc 会沿**目录树向上**自动收集所有 `node_modules/@types`，于是捡到了
  `/home/dev/ljh/node_modules/@types/node`（`~/ljh` 是另一个 pnpm workspace 的根，594MB）
- 相对路径 `../../../../../node_modules/...` 从 `out/sdk` 往上 5 层正好是 `~/ljh`

**结论：源码树放在了一个自带 `node_modules` 的目录下**，TS 类型解析越界。

### 已应用的修复（已验证）

`third_party/parse5/packages/parse5/tsconfig.json` 增加 `"types": []`（禁用自动类型收集）：

```
   "compilerOptions": {
+      "types": [],
```

验证：用构建同一条 tsc 命令编译 parse5，无报错，产出 356K 正常产物。
原文件备份：`/tmp/parse5-tsconfig.json.bak`（重启会丢，需要保留请自行复制走）。

## 原因三（环境层面）：CI 上下不到 6.1 的 SDK

`build/scripts/download_sdk.py` 只查**最近 30 天**的每日构建，而 `OpenHarmony-6.1-Release`
分支最后一次成功构建是 2026-07-31（今天 10-21），所以脚本会静默地"什么也没下"。
要用直链下载。

## 修复步骤

### 1. 放入官方 6.1 SDK（约 3.2GB，解压后约 8~10GB）

```bash
cd ~/ljh/ohos-port/src/ohos/prebuilts
curl -O https://cidownload.openharmony.cn/version/Master_Version/OpenHarmony_6.1.0.31_sp1/20260731_020432/version-Master_Version-OpenHarmony_6.1.0.31_sp1-20260731_020432-ohos-sdk-full_6.1-Release.tar.gz
tar xzf version-Master_Version-OpenHarmony_6.1.0.31_sp1-20260731_020432-ohos-sdk-full_6.1-Release.tar.gz
mkdir -p ohos-sdk/linux/23
mv ohos-sdk/linux/*.zip ohos-sdk/linux/23/
cd ohos-sdk/linux/23 && for z in *.zip; do unzip -q "$z"; done
cd ~/ljh/ohos-port/src/ohos && ls prebuilts/ohos-sdk/linux/23/native/sysroot/usr/lib/arm-linux-ohos/libbundle_ndk.z.so
```

包内结构（已抽样确认）：`manifest_tag.xml`、`ohos-sdk/windows/*.zip`、`ohos-sdk/linux/*.zip`。
windows 部分可删。zip 命名是 `native-linux-x64-6.1.0.31-Release.zip` 这种，与 `23` 目录名无关。

### 2. 重新编译

```bash
cd ~/ljh/ohos-port && bash env/build.sh --product-name rk3568 --ccache
```

> 必须用包装脚本，不要直接 `./build.sh`——否则会撞上下面第二轮失败。

## 第二轮失败：同一根因扩散到 commonlibrary（10 个目标）

放进 SDK 后重建，这次编到 `[20049/119743]` 才失败，错误换了组件：

```
FAILED: obj/commonlibrary/ets_utils/js_api_module/convertxml/js_convertxml.js
../../../../../../../node_modules/@types/node/ffi.d.ts(94,21): error TS1139: ...
```

失败清单（共 10 个，根因相同）：

| 组件 | 模块 |
|---|---|
| `commonlibrary/ets_utils/js_api_module` | convertxml、uri、xml、url、fastbuffer、buffer |
| `commonlibrary/ets_utils/js_util_module` | util、stream、json、container |

原因与 parse5 一模一样，只是这次是 `third_party/typescript/bin/tsc` 在模块目录里直接跑
（`build_ts_js.py` 会 `chdir` 到模块目录再调 tsc），模块自己没有 `tsconfig.json`，
于是 tsc 沿 `convertxml → js_api_module → ets_utils → commonlibrary → ohos → src → ohos-port → ljh`
逐级向上收集 `@types`，第 7 层命中 `/home/dev/ljh/node_modules/@types/node@26.3.0`。

**结论：给 parse5 单独打补丁的方向是错的**（那只是第一块倒下的骨牌）。要治根，必须让
`~/ljh/node_modules` 在构建期间不可见。

### 已实测验证

```bash
cd .../js_api_module/convertxml
mv ~/ljh/node_modules ~/ljh/node_modules.off
../../../../prebuilts/build-tools/common/nodejs/current/bin/node ../../../../third_party/typescript/bin/tsc --outDir /tmp/cv_test
# → 无报错，正常产出 js_convertxml.js
mv ~/ljh/node_modules.off ~/ljh/node_modules
```

### 修复方式一（推荐，保持 ~/ljh 布局）：用包装脚本

`env/build.sh` 会在构建期间把源码树**所有祖先目录**的 `node_modules` 改名隐藏，退出
（正常结束 / 失败 / Ctrl-C）时自动还原；若被 `kill -9` 残留 `.ohos-off`，下次运行会先自愈。

```bash
cd ~/ljh/ohos-port && bash env/build.sh --product-name rk3568 --ccache
```

注意：构建期间 `~/ljh` 下依赖 `node_modules` 的其他 node 项目会暂时不可用。

## 第三轮失败：两个新问题（LFS 指针 + 内核 ThinLTO 符号）

编到 `[34844/99749]`，error.log 里有 2 条 FAILED，分别属于两类完全不同的原因。

### 问题 A：Git LFS 对象没拉下来（libphonenumber）

```
FAILED: obj/third_party/libphonenumber/.../geocoding_data.o
../../third_party/libphonenumber/cpp/src/phonenumbers/geocoding/geocoding_data.cc:1:1:
  error: unknown type name 'version'
version https://git-lfs.github.com/spec/v1
oid sha256:13ab99aa48793a0dea60cb96c2bbe1bd840a0457d59c6a35eaba7cc6f32a6dea
size 28661035
```

工作区里这个文件根本不是 C++ 源码，而是 **Git LFS 指针文件**。

根因：`repo sync` 时机器上还没装 git-lfs（是后来 `install-deps.sh` 装的），也从未执行过
`git lfs install`，所以 lfs 的 clean/smudge filter 没注册，sync 直接把指针写进了工作区。
证据：

```
$ git config --global --get-regexp filter.lfs     # 空
$ cd third_party/libphonenumber && git lfs ls-files
13ab99aa48 - cpp/src/phonenumbers/geocoding/geocoding_data.cc   ← '-' 表示本地没有实体
```

修复：

```bash
git lfs install                                   # 只需一次，注册 filter
cd ~/ljh/ohos-port/src/ohos/third_party/libphonenumber && git lfs pull

# 全树排查（492 个 git 仓库，慢，建议后台跑）
cd ~/ljh/ohos-port/src/ohos && repo forall -c 'git lfs pull'
```

验证：`head -1 .../geocoding_data.cc` 应变成正常的版权注释；`git lfs ls-files` 里该行前缀变 `*`。

### 问题 B：内核链接缺 `__aarch64_cas4_acq_rel`

```
FAILED: ../kernel/src_tmp/linux-6.6/boot_linux ../kernel/checkpoint/compile_check
ld.lld: error: undefined symbol: __aarch64_cas4_acq_rel
>>> referenced by xarray.c
>>>               vmlinux.o:(HdfVNodeAdapterIoctl)
make[4]: *** [scripts/Makefile.vmlinux:37: vmlinux] Error 1
```

排查结论：

| 检查 | 结果 |
|---|---|
| `out/kernel/OBJ/linux-6.6/.config` | `CONFIG_LTO_CLANG_THIN=y`、`CONFIG_ARM64_LSE_ATOMICS=y`、`CONFIG_ARM64_USE_LSE_ATOMICS=y` |
| 单个 `.o`（`lib/xarray.o`、`hdf_vnode_adapter.o`）是否有该未定义符号 | 没有 |
| 哪个文件有这个未定义符号 | 只有 **`vmlinux.o`**（ThinLTO 合并后的对象） |
| 编译参数 | 全部 `--target=aarch64-linux-gnu -march=armv8.5-a`，**没有 `-mno-outline-atomics`** |
| 内核树里有没有禁它的先例 | 只有 `kernel/kcsan/Makefile` 用 `$(call cc-option,-mno-outline-atomics)` |

机制：clang 对 aarch64 默认启用 **outline-atomics**（把原子操作变成对 `__aarch64_cas4_acq_rel`
这类运行时派发桩的调用），而内核是 freestanding，没有任何库提供这个符号。代码生成发生在
ThinLTO 合并阶段，此时 LSE 特性没有生效，于是漏出对派发桩的引用。

**修法一（保守、必定解锁）：关掉 ThinLTO**

内核 `CONFIG_LTO_CLANG_THIN=y` → 改成 `CONFIG_LTO_NONE=y`，然后清掉内核构建目录重编：

```bash
cd ~/ljh/ohos-port/src/ohos
./build.sh --product-name rk3568 --ccache -T kernel   # 或者直接 rm -rf out/kernel 后整体重建
```

代价：镜像变大、编译更慢；对功能无影响。

**修法二（推荐，保留 LTO）：给内核加 `-mno-outline-atomics`**

最省事是走 `KCFLAGS`（kbuild 会把它追加到所有编译，clang 会把它记为 target-feature 写进 bitcode，
LTO 阶段同样遵守）：

```bash
cd ~/ljh/ohos-port
KCFLAGS=-mno-outline-atomics bash env/build.sh --product-name rk3568 --ccache
```

若要固化，在 `out/kernel/src_tmp` 对应的内核源（`kernel/linux/linux-6.6/arch/arm64/Makefile`，
或板级 patch）里加一行：

```
KBUILD_CFLAGS += $(call cc-option,-mno-outline-atomics)
```

改完 `rm -rf out/kernel` 再重编，`llvm-nm vmlinux.o | grep cas4` 应不再出现。

### 处理顺序

1. 先修 LFS（否则每次重编都卡在同一个 `.cc`）
2. 再修内核符号
3. 重跑 `bash env/build.sh --product-name rk3568 --ccache`



### 修复方式二（一次性）：把 node_modules 挪走

`~/ljh/node_modules` 是 2026-09-09 的 pnpm workspace 残留（594MB）。若已不再使用：

```bash
mv ~/ljh/node_modules ~/ljh/node_modules.bak
```

### 修复方式三（最干净）：源码树移出该目录

把 `ohos-port` 放到祖先无 `node_modules` 的位置（例如 `/home/dev/ohos-port`），
`~/ljh` 只留脚本与文档。


## 备选方案：自己编 SDK

```bash
cd ~/ljh/ohos-port/src/ohos
./build.sh --product-name ohos-sdk --ccache     # 产物 out/sdk/ohos-sdk/linux/{ets,js,native,previewer,toolchains}
```
编完需要自己摆到 `prebuilts/ohos-sdk/linux/23/`。前提是 parse5 的 `types: []` 补丁在位，
否则还会被 `~/ljh/node_modules` 干扰。

## 遗留风险

- 其他组件若也用老 tsc 且自身无 `node_modules/@types`，会遇到同样的越界；处理办法相同（加 `"types": []`）。
- 另一条根治路径：把源码树挪到祖先目录没有 `node_modules` 的位置（如 `/home/dev/`），或构建期间临时
  `mv ~/ljh/node_modules ~/ljh/node_modules.off`（会影响 `~/ljh` 下其他 node 项目，慎用）。
- `repo sync` 或 `repo start` 之后再改 third_party 会被覆盖，补丁需放进 `patches/` 并随构建重放。

## 第四轮失败：OOM killer 杀掉 clang++（不是代码问题）

带 `KCFLAGS=-mno-outline-atomics` 重建，内核问题解决（`vmlinux.o` 里已无 `__aarch64_cas4_acq_rel`），
但用户态在 `[4137/21563] ~ [4144/21563]` 处有 3 个目标失败：

```
FAILED: obj/foundation/arkui/ace_engine/adapter/ohos/entrance/ace_ohos_standard_entrance_ohos/ace_container_hybrid_impl.o
FAILED: .../ui_content_impl.o
FAILED: .../ace_container.o
```

可疑点：**error.log 里只有命令行，没有任何编译器诊断**。

验证：把 error.log 里那条一模一样的编译命令手工重跑 → 零输出、正常成功。

结论：进程是被 **SIGKILL** 掉的，不是编译错误。内核日志给出直接证据：

```
sudo dmesg -T | grep -i oom
[Thu Oct 22 00:57:13 2026] oom-kill:...global_oom,task=clang++,pid=355311
[Thu Oct 22 00:57:13 2026] Out of memory: Killed process 355311 (clang++) total-vm:2166752kB, anon-rss:1755840kB
[Thu Oct 22 01:00:55 2026] ... Killed process 355266 (clang++) anon-rss:1715192kB
[Thu Oct 22 01:01:43 2026] ... clang++ invoked oom-killer
```

根因：ninja 默认并发 = 核数 = **64**，而 ArkUI `ace_engine` 这类重模板 C++ 每个 clang++ 峰值
1.5~2GB，64 个并发就要 100GB+，机器只有 62GB（还有别的用户在跑）。三次 OOM 正好对应三个失败目标。

### 修复：限制 ninja 并发

OH 6.1 的 `build.sh --jobs` 是**空实现**（`build/hb/resolver/build_args_resolver.py:1016` 的
`resolve_jobs` 直接 `return`），hb 又固定调用
`prebuilts/build-tools/linux-x86/bin/ninja`，所以只能给这个二进制套一层 wrapper：

```bash
cd ~/ljh/ohos-port/src/ohos/prebuilts/build-tools/linux-x86/bin
mv ninja ninja.real          # 已做过，备份为 ninja.real
cat > ninja <<'EOF'
#!/bin/sh
exec "$(dirname "$0")/ninja.real" -j "${NINJA_JOBS:-16}" "$@"
EOF
chmod +x ninja
```

`env/build.sh` 已内置 `export NINJA_JOBS=16`，直接跑即可：

```bash
cd ~/ljh/ohos-port && bash env/build.sh --product-name rk3568 --ccache
```

调整与回滚：

- 机器空闲时可用 `NINJA_JOBS=24 bash env/build.sh ...`（24×2G≈48G，仍有余量）
- 恢复原状：`cd prebuilts/build-tools/linux-x86/bin && mv ninja.real ninja`

### 附带的资源提醒

- `/` 已用 92%，只剩 158GB（out 约 12G、ccache 11G、源码 40G+）。继续编下去要留意，必要时
  `ccache -C` 或清掉 `out/sdk`（SDK 已经不需要自己编了）。
- `ccache -s` 里 `Errors: 224` 是 OOM 期间产生的无效条目，不影响正确性。


