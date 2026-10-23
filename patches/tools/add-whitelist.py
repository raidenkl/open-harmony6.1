#!/usr/bin/env python3
"""把 LubanCat 的 ohos.build 加入 compile_standard_whitelist.json（幂等 + 自愈）。

不用 patch 处理这个文件：hb 每次构建都会把 JSON 重新序列化，
diff 会变成上千行格式噪声，补丁极易失效。

背景：hb 构建时会把 part 名与 subsystem 名不一致的条目归到
`bundle_subsystem_error`，如果这里再往 `gn_part_or_subsystem_error` 加一份
就会出现同一路径落在两个 bucket 里。所以本脚本：
  - 所有 bucket 都没有 -> 加到 bundle_subsystem_error
  - 多个 bucket 都有   -> 只保留 bundle_subsystem_error，其余删掉
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]  # -> ohos-port
CFG = ROOT / "src/ohos/build/compile_standard_whitelist.json"

WANT = [
    "device/board/rockchip/rk3568/ohos.build",
    "vendor/rockchip/lubancat_2_v3/ohos.build",
]
# 顺序即优先级：hb 最终会把条目归到第一个
BUCKETS = ["bundle_subsystem_error", "gn_part_or_subsystem_error"]


def main() -> int:
    if not CFG.is_file():
        print("[whitelist] !! 找不到 %s" % CFG)
        return 1

    data = json.loads(CFG.read_text())
    for k in BUCKETS:
        data.setdefault(k, [])

    changed = False
    for item in WANT:
        present = [k for k in BUCKETS if item in data[k]]
        if not present:
            data[BUCKETS[0]].append(item)
            print("[whitelist] + %s -> %s" % (item, BUCKETS[0]))
            changed = True
        elif len(present) > 1:
            for k in present[1:]:
                while item in data[k]:
                    data[k].remove(item)
                print("[whitelist] - %s <- %s（去重）" % (item, k))
            changed = True

    if not changed:
        print("[whitelist] 条目已就位且无重复，跳过")
        return 0

    CFG.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
