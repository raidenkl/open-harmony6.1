#!/usr/bin/env bash
# 带重试的 repo sync。gitcode 的 DNS 在并发高时会偶发解析失败，单次失败不代表网络不可用。
# 用法: setsid nohup bash env/run-sync.sh </dev/null >/dev/null 2>&1 &
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT/out/repo-sync.log"
JOBS="${JOBS:-12}"
cd "$ROOT/src/ohos" || exit 1

exec >>"$LOG" 2>&1
echo "############ sync start $(date '+%F %T') jobs=$JOBS ############"

for i in 1 2 3 4 5; do
  echo "===== pass $i $(date '+%F %T') ====="
  if repo sync -c -f -j"$JOBS" --no-clone-bundle; then
    echo "############ SYNC OK $(date '+%F %T') ############"
    exit 0
  fi
  echo "===== pass $i failed, sleep 60s ====="
  sleep 60
done

echo "############ SYNC FAILED after 5 passes $(date '+%F %T') ############"
exit 1
