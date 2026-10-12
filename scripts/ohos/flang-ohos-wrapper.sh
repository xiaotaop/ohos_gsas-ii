#!/bin/sh
# Make the community flang-20 package usable by Meson's compiler sanity check.

set -eu

WORK_ROOT="${GSAS_OHOS_WORK_ROOT:-$HOME/ohos-gsas-work}"
SDK_ROOT="${OHOS_NATIVE_SDK:-$HOME/.harmonybrew/opt/ohos-sdk-native}"
FLANG_ROOT="${OHOS_FLANG_ROOT:-$WORK_ROOT/flang/fortran-20.1.0-ohos-aarch64}"
REAL_FLANG="$FLANG_ROOT/bin/flang-20"

compile_only=0
for arg in "$@"; do
  case "$arg" in
    -c|-S|-E|-fsyntax-only)
      compile_only=1
      ;;
  esac
done

if [ "$compile_only" -eq 1 ]; then
  exec "$REAL_FLANG" "$@"
fi

exec "$REAL_FLANG" "$@" \
  --target=aarch64-linux-ohos \
  --sysroot="$SDK_ROOT/sysroot" \
  -nostdlib \
  "$SDK_ROOT/sysroot/usr/lib/aarch64-linux-ohos/crti.o" \
  "$SDK_ROOT/sysroot/usr/lib/aarch64-linux-ohos/crtn.o" \
  -L"$FLANG_ROOT/lib/flang-runtime" \
  -L"$SDK_ROOT/llvm/lib/aarch64-linux-ohos" \
  -L"$SDK_ROOT/sysroot/usr/lib/aarch64-linux-ohos" \
  -L"$SDK_ROOT/llvm/lib/clang/15.0.4/lib/aarch64-linux-ohos" \
  -lFortranRuntime -lFortranDecimal -lclang_rt.builtins -lc++ -lc
