import pathlib, sys

R = pathlib.Path("/home/dev/ljh/ohos-port/src/ohos")
D = R / "device/soc/rockchip/rk3568/hardware/display/src/display_device"

# ---------- 1) DiscoveryDevice: 补判空，别再用 nullptr 调 Init() ----------
p = D / "hdi_device_interface.cpp"
s = p.read_text()
old = """    std::shared_ptr<HdiDeviceInterface> drmDevice = DrmDevice::Create();
    if (!drmDevice) {
        DISPLAY_LOGE("can not create drm device");
    }
"""
new = """    std::shared_ptr<HdiDeviceInterface> drmDevice = DrmDevice::Create();
    if (!drmDevice) {
        /* vendor 缺陷：原来只打印就继续 -> drmDevice->Init() 在 nullptr 上取 vtable，SIGSEGV。
         * 崩溃循环会让 init 反复拉起 composer_host，且 hilog 里留不下 errno。 */
        DISPLAY_LOGE("can not create drm device, skip init");
        return devices;
    }
"""
if "can not create drm device, skip init" in s:
    print("[1] DiscoveryDevice 已打过补丁")
elif old in s:
    p.write_text(s.replace(old, new, 1))
    print("[1] DiscoveryDevice 判空补丁已应用")
else:
    print("[1] !! 锚点未匹配，需人工检查"); sys.exit(1)

# ---------- 2) DrmDevice::Create: open 失败重试 3 次并逐次打印 errno ----------
p = D / "drm_device.cpp"
s = p.read_text()
old = """    if (mDrmFd == nullptr) {
        const std::string name("rockchip");
        int drmFd = open("/dev/dri/card0", O_RDWR | O_CLOEXEC); // drmOpen(name.c_str(), nullptr);
        if (drmFd < 0) {
            DISPLAY_LOGE("drm file:%{public}s open failed %{public}s", name.c_str(), strerror(errno));
            return nullptr;
        }
"""
new = """    if (mDrmFd == nullptr) {
        const std::string name("rockchip");
        int drmFd = -1;
        /* ueventd 创建 /dev/dri/card0 与 composer_host 启动存在竞态：
         * 首启时节点可能还没出来(ENOENT)，重试几次即可自愈。
         * 每次失败都把 errno 打出来，避免"崩了但不知道为什么"，
         * 也避免 errno 被后续调用覆盖。 */
        for (int retry = 0; retry < 3; retry++) {
            drmFd = open("/dev/dri/card0", O_RDWR | O_CLOEXEC); // drmOpen(name.c_str(), nullptr);
            if (drmFd >= 0) {
                break;
            }
            int err = errno;
            DISPLAY_LOGE("drm file:%{public}s open failed try %{public}d errno %{public}d %{public}s",
                name.c_str(), retry, err, strerror(err));
            usleep(100000); // 100ms
        }
        if (drmFd < 0) {
            return nullptr;
        }
"""
if 'open failed try %{public}d errno' in s:
    print("[2] Create 重试已打过补丁")
elif old in s:
    s = s.replace(old, new, 1)
    if "#include <unistd.h>" not in s:
        s = s.replace('#include <fcntl.h>', '#include <fcntl.h>\n#include <unistd.h>', 1)
    p.write_text(s)
    print("[2] Create 重试 + errno 补丁已应用")
else:
    print("[2] !! 锚点未匹配，需人工检查"); sys.exit(1)

print("---- 结果核对 ----")
print("".join((D/"hdi_device_interface.cpp").read_text().splitlines(True)[28:36]))
print("".join((D/"drm_device.cpp").read_text().splitlines(True)[30:58]))
