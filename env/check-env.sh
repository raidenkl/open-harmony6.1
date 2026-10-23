#!/usr/bin/env bash
# OpenHarmony 6.1 编译环境体检（只读，不修改系统）
# 用法: bash env/check-env.sh [输出文件]
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/docs/00-环境体检报告.md}"
mkdir -p "$(dirname "$OUT")"

PASS=0; WARN=0; FAIL=0
declare -a LINES

line() { LINES+=("$1"); }
ok()   { PASS=$((PASS+1)); line "| $1 | $2 | PASS |"; }
warn() { WARN=$((WARN+1)); line "| $1 | $2 | WARN |"; }
bad()  { FAIL=$((FAIL+1)); line "| $1 | $2 | FAIL |"; }

# ---------- 系统 ----------
OS_PRETTY="unknown"
[ -r /etc/os-release ] && OS_PRETTY="$(. /etc/os-release; echo "$PRETTY_NAME")"
KERNEL="$(uname -r)"
ARCH="$(uname -m)"

case "$ARCH" in
  x86_64) ok "架构" "$ARCH" ;;
  *)      bad "架构" "$ARCH（需 x86_64）" ;;
esac

case "$OS_PRETTY" in
  *22.04*) ok "发行版" "$OS_PRETTY" ;;
  *20.04*) warn "发行版" "$OS_PRETTY（可用，部分新预编译件可能缺库）" ;;
  *24.04*|*25.*|*26.*) warn "发行版" "$OS_PRETTY（非官方支持，需补 libtinfo5 等旧库）" ;;
  *) bad "发行版" "$OS_PRETTY（建议 Ubuntu 22.04）" ;;
esac

# /bin/sh 必须是 bash
SHDEST="$(readlink -f /bin/sh 2>/dev/null || echo /bin/sh)"
case "$SHDEST" in
  */bash) ok "/bin/sh" "→ bash" ;;
  *)      bad "/bin/sh" "→ $SHDEST（OH 构建脚本要求 bash，dash 会在数组/管道处异常退出）" ;;
esac

# 用户名/家目录英文
if printf '%s' "$HOME" | LC_ALL=C grep -q '[^ -~]'; then
  bad "家目录路径" "$HOME（含非 ASCII，脚本路径拼接会出错）"
else
  ok "家目录路径" "$HOME"
fi

# ---------- 资源 ----------
NPROC="$(nproc)"
if [ "$NPROC" -ge 16 ]; then ok "CPU 核数" "$NPROC"
elif [ "$NPROC" -ge 8 ]; then warn "CPU 核数" "$NPROC（建议 16+，全量编译会慢一倍）"
else bad "CPU 核数" "$NPROC"; fi

MEM_GB=$(( $(awk '/MemTotal/{print $2}' /proc/meminfo) / 1024 / 1024 ))
SWAP_GB=$(( $(awk '/SwapTotal/{print $2}' /proc/meminfo) / 1024 / 1024 ))
if [ "$MEM_GB" -ge 32 ]; then ok "内存" "${MEM_GB}GB"
elif [ "$MEM_GB" -ge 16 ]; then warn "内存" "${MEM_GB}GB（链接 vmlinux 有 OOM 风险，需 swap ≥16GB）"
else bad "内存" "${MEM_GB}GB（会 OOM，退出码 137）"; fi
if [ "$SWAP_GB" -ge 8 ]; then ok "Swap" "${SWAP_GB}GB"
else warn "Swap" "${SWAP_GB}GB（建议 ≥8GB）"; fi

AVAIL_GB=$(df -BG --output=avail "$ROOT" | tail -1 | tr -dc '0-9')
if [ "${AVAIL_GB:-0}" -ge 300 ]; then ok "可用磁盘" "${AVAIL_GB}GB"
elif [ "${AVAIL_GB:-0}" -ge 200 ]; then warn "可用磁盘" "${AVAIL_GB}GB（源码 40G+prebuilts 17G+out 80G，偏紧）"
else bad "可用磁盘" "${AVAIL_GB}GB（至少需要 200GB，建议 300GB）"; fi

# ---------- 工具 ----------
check_cmd() { # name, min-hint, level
  local name="$1" hint="$2" lvl="$3"
  if command -v "$name" >/dev/null 2>&1; then ok "$name" "$(command -v "$name")"
  else
    if [ "$lvl" = "bad" ]; then bad "$name" "缺失（$hint）"; else warn "$name" "缺失（$hint）"; fi
  fi
}
check_cmd repo   "repo init/sync 必需" bad
check_cmd git    "源码管理" bad
check_cmd python3 "构建脚本" bad
check_cmd java   "SDK/构建工具" bad
check_cmd node   "仅在 prebuilts 缺失时需要" warn
check_cmd npm    "同上" warn
check_cmd ninja  "gn/ninja 构建" warn
check_cmd clang  "宿主机 clang（OH 用自带 clang-15）" warn
check_cmd ccache "加速增量编译" warn
check_cmd unzip  "解压" bad
check_cmd zip    "打包" bad
check_cmd rsync  "同步" warn
check_cmd bc     "内核脚本" warn
check_cmd cpio   "ramdisk" warn
check_cmd mkfs.vfat "EFI/分区镜像" warn
check_cmd mcopy  "mtools" warn
check_cmd genext2fs "system 镜像" warn
check_cmd mkimage "u-boot 镜像" warn
check_cmd scons  "部分组件构建" warn
check_cmd flex   "编译" warn
check_cmd bison  "编译" warn
check_cmd openssl "签名/证书" warn
check_cmd ruby   "部分脚本" warn

# ---------- 版本 ----------
PYV="$(python3 -V 2>&1 | awk '{print $2}')"
line "| python3 版本 | $PYV | 参考 |"
JV="$(java -version 2>&1 | head -1)"
line "| java 版本 | ${JV//|/ } | 参考 |"
line "| 内核 | $KERNEL | 参考 |"

# ---------- 网络 ----------
GITEE_OK="no"; TAG=""
if timeout 40 git ls-remote https://gitee.com/openharmony/manifest.git >/dev/null 2>&1; then
  GITEE_OK="yes"
  ok "gitee 访问" "git ls-remote 成功"
  TAG="$(timeout 40 git ls-remote --tags https://gitee.com/openharmony/manifest.git 2>/dev/null | grep -F 'OpenHarmony-v6.1-Release' | head -1 | awk '{print $2}')"
  if [ -n "$TAG" ]; then ok "manifest 基线" "$TAG"
  else warn "manifest 基线" "未找到 v6.1-Release tag，需人工确认分支"; fi
else
  bad "gitee 访问" "git ls-remote 失败（repo sync 无法进行，需代理或镜像）"
fi

if timeout 15 curl -sI https://repo.huaweicloud.com >/dev/null 2>&1; then
  ok "prebuilts 源" "repo.huaweicloud.com 可达"
else
  warn "prebuilts 源" "repo.huaweicloud.com 不可达（prebuilts_download.sh 可能失败）"
fi

# ---------- 输出 ----------
{
  echo "# OpenHarmony 6.1 编译环境体检报告"
  echo
  echo "- 主机：\`$(hostname)\`　用户：\`$(whoami)\`　时间：$(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "- 目标目录：\`$ROOT\`"
  echo "- 汇总：**PASS $PASS / WARN $WARN / FAIL $FAIL**"
  echo
  echo "| 检查项 | 结果 | 判定 |"
  echo "|---|---|---|"
  printf '%s\n' "${LINES[@]}"
  echo
  if [ "$FAIL" -gt 0 ]; then
    echo "> 存在 FAIL 项，先修掉再开始 repo sync / 编译。"
  elif [ "$WARN" -gt 0 ]; then
    echo "> 无 FAIL，WARN 项按需处理（多数是可选工具，影响的是打包步骤而非编译）。"
  else
    echo "> 全部通过，可以开始编译。"
  fi
} > "$OUT"

printf '%s\n' "${LINES[@]}"
echo
echo "汇总：PASS=$PASS WARN=$WARN FAIL=$FAIL"
echo "报告已写入：$OUT"
