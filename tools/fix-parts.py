#!/usr/bin/env python3
# 修正 P1 里 part/subsystem 命名不一致导致的 preloader 校验失败
import json, pathlib
ROOT = pathlib.Path("/home/dev/ljh/ohos-port/src/ohos")

# 1) 板级 ohos.build：part 名改回 rockchip_products（与 subsystem 同名，校验直接放行）
p = ROOT / "device/board/rockchip/rk3568/ohos.build"
s = p.read_text()
if '"rk3568_lubancat": {' in s:
    s = s.replace('"rk3568_lubancat": {', '"rockchip_products": {')
    p.write_text(s)
    print("board ohos.build: part 名 -> rockchip_products")

# 2) 产品 config.json：component 改回 rockchip_products
p = ROOT / "vendor/rockchip/lubancat_2_v3/config.json"
s = p.read_text()
if '"component": "rk3568_lubancat"' in s:
    s = s.replace('"component": "rk3568_lubancat"', '"component": "rockchip_products"')
    p.write_text(s)
    print("config.json: component -> rockchip_products")

# 3) 产品 ohos.build：subsystem 用 product_<product_name>，与自动注入的 subsystem 名一致
p = ROOT / "vendor/rockchip/lubancat_2_v3/ohos.build"
s = p.read_text()
if '"product_rockchip"' in s:
    s = s.replace('"product_rockchip"', '"product_lubancat_2_v3"')
    p.write_text(s)
    print("vendor ohos.build: subsystem -> product_lubancat_2_v3")

# 4) hdf/audio/codec 的 subsystem_name 同步
for f in ["hdf_config/uhdf/BUILD.gn", "hals/audio/BUILD.gn", "hals/codec/BUILD.gn"]:
    q = ROOT / "vendor/rockchip/lubancat_2_v3" / f
    if not q.exists():
        continue
    t = q.read_text()
    if '"product_rockchip"' in t:
        q.write_text(t.replace('"product_rockchip"', '"product_lubancat_2_v3"'))
        print("subsystem_name 同步:", f)

print("\n--- 复核 ---")
print((ROOT / "device/board/rockchip/rk3568/ohos.build").read_text()[:220])
d = json.loads((ROOT / "vendor/rockchip/lubancat_2_v3/config.json").read_text())
print([ (s["subsystem"], [c["component"] for c in s.get("components", [])]) for s in d["subsystems"] if "rockchip" in s["subsystem"] ])
