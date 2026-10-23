#!/usr/bin/env bash
# 用法: source env/ohos-env.sh
# 进入 OH 6.1 编译环境的统一出口，避免每次手动拼 PATH。
export OHOS_PORT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export OHOS_SRC="$OHOS_PORT_ROOT/src/ohos"

# 源码树自带工具链优先，不要用宿主机 gcc/clang/node 覆盖
if [ -d "$OHOS_SRC/prebuilts/python/linux-x86/current/bin" ]; then
  export PATH="$OHOS_SRC/prebuilts/python/linux-x86/current/bin:$PATH"
fi
if [ -d "$OHOS_SRC/prebuilts/build-tools/linux-x86/bin" ]; then
  export PATH="$OHOS_SRC/prebuilts/build-tools/linux-x86/bin:$PATH"
fi
if [ -d "$OHOS_SRC/out/ohos-sdk/linux" ]; then
  export OHOS_SDK="$OHOS_SRC/out/ohos-sdk/linux"
fi

# ccache：全量编译第二次起快一倍以上
export USE_CCACHE=1
export CCACHE_DIR="${CCACHE_DIR:-$HOME/.ccache}"
export CCACHE_EXEC="$(command -v ccache || true)"

# 构建并发：64 核机器上给 16~24 保守值，避免链接期 OOM
export JOBS="${JOBS:-16}"

alias ohcd='cd "$OHOS_SRC"'
alias ohbuild='cd "$OHOS_SRC" && bash build/build.sh'
alias ohcheck='bash "$OHOS_PORT_ROOT/env/check-env.sh"'

echo "OHOS_SRC=$OHOS_SRC  JOBS=$JOBS"
