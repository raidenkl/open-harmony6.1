#!/usr/bin/env bash
# 安装 OpenHarmony 6.1 编译依赖（Ubuntu 22.04）
#
# 注意：gcc-multilib / g++-multilib 与交叉编译器 **在包层面互斥**
#   gcc-11-arm-linux-gnueabi 声明了 Conflicts: gcc-multilib
# 所以直接装 gcc-multilib 会被 apt 判定为"要么卸交叉编译器、要么装不上"。
# 解决：装带版本号的 gcc-11-multilib（功能一样，不触发那条 Conflicts）。
#
# 用法：
#   SUDO_PASS='xxx' bash env/install-deps.sh      # 非交互
#   bash env/install-deps.sh                      # 已配免密 sudo 时直接跑
set -euo pipefail

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  if [ -n "${SUDO_PASS:-}" ]; then
    SUDO() { printf '%s\n' "$SUDO_PASS" | sudo -S -p '' "$@"; }
  else
    SUDO() { sudo "$@"; }
  fi
else
  SUDO() { "$@"; }
fi

echo "==> apt update"
SUDO apt-get update -y

BASE_PKGS="
  bison ccache default-jdk flex gcc-arm-linux-gnueabi gcc-arm-none-eabi
  genext2fs liblz4-tool libssl-dev mtd-utils mtools openssl ruby scons
  unzip u-boot-tools zip git git-lfs gnupg gperf build-essential curl
  zlib1g-dev lib32ncurses5-dev libx11-dev lib32z1-dev libxml2-utils
  xsltproc m4 bc gnutls-bin python3-pip libgl1-mesa-dev libc6-dev-i386
  libelf-dev lz4 cpio rsync file patch jq dosfstools autoconf automake
  libtool python-is-python3 ninja-build pkg-config libncurses5
  libstdc++-12-dev
"

# 32 位宿主工具链：用带版本号的包名绕开 Conflicts: gcc-multilib
GCC_MAJOR="$(gcc -dumpversion | cut -d. -f1)"
MULTILIB_PKGS="gcc-${GCC_MAJOR}-multilib g++-${GCC_MAJOR}-multilib"

echo "==> 基础构建依赖"
SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y $BASE_PKGS

echo "==> 32 位 multilib（gcc-${GCC_MAJOR}-multilib）"
if SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y $MULTILIB_PKGS; then
  echo "    OK"
else
  echo "    WARN: multilib 安装失败，已跳过。"
  echo "          OH 的 arm64 标准系统构建不依赖它；只有编译 32 位宿主工具时才需要。"
  echo "          交叉编译器必须保留，不要为了 multilib 卸掉 gcc-*-linux-gnu*。"
fi

echo "==> 检查 /bin/sh"
if [ "$(readlink -f /bin/sh)" != "/bin/bash" ]; then
  echo "WARN: /bin/sh 指向 $(readlink -f /bin/sh)，OH 构建脚本要求 bash。"
  echo "      修复：sudo dpkg-reconfigure dash   （选择 No）"
fi

echo "==> 完成后跑一次体检：bash env/check-env.sh"
