#!/usr/bin/env python3
# P1: 把 hihope/rk3568 的副本改造成 rockchip/rk3568 + lubancat_2_v3 产品
import pathlib

ROOT = pathlib.Path("/home/dev/ljh/ohos-port/src/ohos")
B = ROOT / "device/board/rockchip/rk3568"
V = ROOT / "vendor/rockchip/lubancat_2_v3"

def edit(path, pairs, note=""):
    p = pathlib.Path(path)
    if not p.exists():
        print("MISS:", p)
        return
    s = old = p.read_text()
    hits = []
    for a, b in pairs:
        n = s.count(a)
        hits.append((a[:60], n))
        s = s.replace(a, b)
    if s == old:
        print("NOCHANGE:", p.relative_to(ROOT), note)
    else:
        p.write_text(s)
        print("OK:", p.relative_to(ROOT), "|", ", ".join(f"{n}x {a}" for a, n in hits if n))

# 1) 板级 ohos.build
edit(B / "ohos.build", [
    ('"rockchip_products": {', '"rk3568_lubancat": {'),
    ("//device/board/hihope/${device_name}", "//device/board/rockchip/${device_name}"),
    ("//vendor/hihope/${product_name}", "//vendor/rockchip/${product_name}"),
])

# 2) 产品 ohos.build
edit(V / "ohos.build", [
    ("product_rk3568", "product_lubancat_2_v3"),
    ("//vendor/hihope/rk3568/", "//vendor/rockchip/lubancat_2_v3/"),
    ('"product_hihope"', '"product_rockchip"'),
])

# 3) config.json
edit(V / "config.json", [
    ('"product_name": "rk3568"', '"product_name": "lubancat_2_v3"'),
    ('"device_build_path": "device/board/hihope/rk3568"',
     '"device_build_path": "device/board/rockchip/rk3568"'),
    ('"component": "rockchip_products"', '"component": "rk3568_lubancat"'),
])

# 4) 路径类
edit(V / "product.gni", [("//device/board/hihope/", "//device/board/rockchip/")])
edit(B / "kernel/BUILD.gn", [("//device/board/hihope/", "//device/board/rockchip/")])
edit(B / "bootanimation/BUILD.gn", [("//device/board/hihope/", "//device/board/rockchip/")])

# 5) hdf/audio/codec 的 subsystem_name
for f in ["hdf_config/uhdf/BUILD.gn", "hals/audio/BUILD.gn", "hals/codec/BUILD.gn"]:
    edit(V / f, [('"product_hihope"', '"product_rockchip"')])

# 6) 框架：kernel template 指向新板级目录
edit(ROOT / "build/templates/kernel/ohos_kernel_build.gni",
     [("//device/board/hihope/rk3568/kernel:kernel",
       "//device/board/rockchip/rk3568/kernel:kernel")])

print("\n--- 残留 hihope 引用检查 ---")
for base in (B, V):
    for p in base.rglob("*"):
        if p.is_file() and p.suffix in (".gn", ".gni", ".sh", ".json", ".build", ".txt") or p.name == "ohos.build":
            try:
                t = p.read_text(errors="ignore")
            except Exception:
                continue
            if "hihope" in t:
                for i, line in enumerate(t.splitlines(), 1):
                    if "hihope" in line:
                        print(f"{p.relative_to(ROOT)}:{i}: {line.strip()[:110]}")
