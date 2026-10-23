import pathlib, sys

R = pathlib.Path("/home/dev/ljh/ohos-port/src/ohos")
U = R / "base/startup/init/ueventd/etc/ueventd.config"
s = U.read_text()

# /dev/rga 没有规则 -> 按 DEVMODE(0660) + root:root 建节点，
# 而 composer_host 以 composer_host uid 运行（gid 不含 root），打不开。
# graphics 设备统一 0666，和 /dev/dri/card0 保持一致。
if "/dev/rga " in s:
    print("[ueventd] 已存在规则，跳过")
else:
    anchor = "/dev/dri/card0-HDMI-A-1 0666 0 1003\n"
    add = "/dev/rga 0666 0 0\n"
    if anchor in s:
        s = s.replace(anchor, anchor + add, 1)
    else:
        # 兜底：插在 [device] 段的 /dev/dri 行后面
        import re
        m = re.search(r"^/dev/dri[^\n]*\n", s, re.M)
        if not m:
            print("[ueventd] !! 找不到锚点"); sys.exit(1)
        s = s[:m.end()] + add + s[m.end():]
    U.write_text(s)
    print("[ueventd] 已加 /dev/rga 0666 0 0")

print("---- 核对 ----")
for line in U.read_text().splitlines():
    if "/dev/dri" in line or "/dev/rga" in line:
        print("   ", line)
