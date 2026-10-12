#!/bin/sh
# Strip old signatures and self-sign every native module in a Meson build tree.

set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 MESON_BUILD_DIR" >&2
  exit 2
fi

SDK_ROOT="${OHOS_NATIVE_SDK:-$HOME/.harmonybrew/opt/ohos-sdk-native}"
SIGN_TOOL="${OHOS_BINARY_SIGN_TOOL:-$HOME/.harmonybrew/opt/ohos-sdk-toolchains/lib/binary-sign-tool}"
BUILD_DIR="$1"

find "$BUILD_DIR" -name '*.so' -type f | while read -r so_file; do
  "$SDK_ROOT/llvm/bin/llvm-strip" --strip-debug "$so_file"
  "$SDK_ROOT/llvm/bin/llvm-objcopy" --remove-section=.codesign "$so_file"
  "$SIGN_TOOL" sign -inFile "$so_file" -outFile "$so_file" -selfSign 1
done
