#!/usr/bin/env bash
# OH 构建包装器：构建期间临时隐藏源码树祖先目录里的 node_modules
#
# 背景：OH 的 third_party/typescript（老版本 tsc）会沿目录树向上自动收集所有
#   node_modules/@types。源码树放在 ~/ljh 下，而 ~/ljh 是另一个 pnpm workspace 的根，
#   里面有 @types/node@26（ffi.d.ts 用了新语法），导致 commonlibrary/ets_utils 下
#   十几个模块编译报 TS1005/TS1139。把祖先的 node_modules 在构建期间移开即可。
#
# 用法: bash env/build.sh --product-name rk3568 --ccache
# 说明: 退出（含 Ctrl-C / 失败）时自动还原；若被 kill -9 残留 .ohos-off，下次运行会自动还原。
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/src/ohos"
SUFFIX=".ohos-off"
RESTORED=0
declare -a HIDDEN=()

# 并发上限：64 核机器上 64 个 clang++ 峰值可达 110GB，会触发 OOM killer 静默杀掉编译进程
# （表现：ninja 报 FAILED 但 error.log 里没有任何编译器报错）。默认 16，可用 NINJA_JOBS 覆盖。
export NINJA_JOBS="${NINJA_JOBS:-16}"
echo "[build.sh] NINJA_JOBS=$NINJA_JOBS"

restore() {
  [ "$RESTORED" = "1" ] && return 0
  RESTORED=1
  for p in "${HIDDEN[@]:-}"; do
    [ -n "$p" ] && [ -d "${p}${SUFFIX}" ] && mv "${p}${SUFFIX}" "$p" && echo "[build.sh] 已还原 $p"
  done
}
trap restore EXIT INT TERM

# 1) 清理上次残留
d="$(cd "$SRC" && pwd)"
while [ "$d" != "/" ]; do
  if [ -d "${d}/node_modules${SUFFIX}" ] && [ ! -d "${d}/node_modules" ]; then
    mv "${d}/node_modules${SUFFIX}" "${d}/node_modules"
    echo "[build.sh] 清理残留，已还原 ${d}/node_modules"
  fi
  d="$(dirname "$d")"
done

# 2) 隐藏祖先里的 node_modules（不含源码树内部各组件自己的）
d="$(dirname "$SRC")"
while [ "$d" != "/" ]; do
  if [ -d "${d}/node_modules" ]; then
    mv "${d}/node_modules" "${d}/node_modules${SUFFIX}"
    HIDDEN+=("${d}/node_modules")
    echo "[build.sh] 构建期间隐藏 ${d}/node_modules"
  fi
  d="$(dirname "$d")"
done

cd "$SRC" || exit 1
./build.sh "$@"
RC=$?
echo "[build.sh] build.sh 退出码 $RC"
exit $RC
