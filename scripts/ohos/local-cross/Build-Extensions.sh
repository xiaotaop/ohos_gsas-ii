#!/bin/sh
# Run in the disposable Ubuntu 22.04 build container described in README.md.
set -eu
export PATH="/work/host-venv/bin:$PATH"
recipe=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test -f /work/GSAS-II/meson.build
test -f /runtime-input/extract/python-3.12.9-ohos-aarch64/include/python3.12/Python.h
test -f /runtime-input/payload/libs/libpython3.12.so
test -f /work/sdk/sysroot/usr/include/stdio.h
# Cross-build configuration is fixed to these mount paths, never the host OS.
cp "$recipe/cross-ohos.ini" /work/cross-ohos.ini
cp "$recipe/ohos-toolchain.cmake" /work/ohos-toolchain.cmake
sh "$recipe/build-fortran-runtime.sh"
cd /work/GSAS-II
patch --dry-run -p1 < "$recipe/gsas-ohos.patch"
patch -p1 < "$recipe/gsas-ohos.patch"
/work/host-venv/bin/meson setup /work/build-ohos /work/GSAS-II --cross-file /work/cross-ohos.ini --buildtype release
/work/host-venv/bin/ninja -C /work/build-ohos -j 4
# Installing the Python source tree is deliberately separate from native build.
find /work/build-ohos/sources -name '*.cpython-312-aarch64-linux-ohos.so' -type f
