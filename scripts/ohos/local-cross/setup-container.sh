#!/bin/sh
set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl gnupg python3 python3-venv python3-dev pkg-config cmake ninja-build make patch
curl --fail --show-error --location https://apt.llvm.org/llvm-snapshot.gpg.key -o /tmp/llvm-key.asc
gpg --dearmor -o /usr/share/keyrings/llvm.gpg /tmp/llvm-key.asc
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/llvm.gpg] https://apt.llvm.org/jammy/ llvm-toolchain-jammy-20 main' > /etc/apt/sources.list.d/llvm20.list
apt-get update
LLVM_PACKAGE_VERSION='1:20.1.8~++20250708082409+6fb913d3e2ec-1~exp1~20250708202428.132'
apt-get install -y --no-install-recommends "flang-20=$LLVM_PACKAGE_VERSION" "clang-20=$LLVM_PACKAGE_VERSION" "lld-20=$LLVM_PACKAGE_VERSION" "llvm-20-dev=$LLVM_PACKAGE_VERSION"
python3 -m venv /work/host-venv
/work/host-venv/bin/pip install 'numpy==2.2.6' 'meson==1.12.1' 'ninja==1.13.0' 'Cython==3.1.8'
flang-new-20 --version || flang-20 --version
