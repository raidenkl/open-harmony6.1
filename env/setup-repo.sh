#!/usr/bin/env bash
# 初始化 OH 6.1 源码工作区（只做 repo init，不下载；sync 由人手动起，便于放 tmux）
# 用法:
#   bash env/setup-repo.sh             # 用分支 OpenHarmony-6.1-Release
#   PIN_TAG=1 bash env/setup-repo.sh   # 用 tag OpenHarmony-v6.1-Release（可复现）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/src/ohos"
MANIFEST_URL="https://gitee.com/openharmony/manifest.git"
BRANCH="${BRANCH:-OpenHarmony-6.1-Release}"
PIN_TAG="${PIN_TAG:-0}"

mkdir -p "$SRC"
cd "$SRC"

if [ -n "$(git config --global user.name || true)" ]; then
  :
else
  git config --global user.name  "${GIT_NAME:-dev}"
  git config --global user.email "${GIT_EMAIL:-dev@localhost}"
  echo "已设置 git 用户：$(git config --global user.name) <$(git config --global user.email)>"
fi
git config --global http.postBuffer 524288000 || true

REF="$BRANCH"
[ "$PIN_TAG" = "1" ] && REF="refs/tags/OpenHarmony-v6.1-Release"

echo "==> repo init  ($MANIFEST_URL  ref=$REF)"
repo init -u "$MANIFEST_URL" -b "$REF" --no-repo-verify

cat > "$ROOT/env/sync.sh" <<'EOF'
#!/usr/bin/env bash
# 增量同步源码。首次约 40GB；断线后重复执行即可续传。
set -euo pipefail
cd "$(dirname "$0")/../src/ohos"
repo sync -c -j"${JOBS:-16}" --no-clone-bundle --optimized-fetch --prune
EOF
chmod +x "$ROOT/env/sync.sh"

echo
echo "==> repo init 完成。下一步："
echo "    tmux new -s ohos"
echo "    cd $ROOT && bash env/sync.sh 2>&1 | tee out/repo-sync-\$(date +%m%d-%H%M).log"
