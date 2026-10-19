#!/bin/sh
set -eu
cmake -S /work/llvm-project/flang/lib/Decimal -B /work/decimal-build -G Ninja -DCMAKE_TOOLCHAIN_FILE=/work/ohos-toolchain.cmake -DCMAKE_BUILD_TYPE=Release -DLLVM_ENABLE_PIC=ON -DCMAKE_DISABLE_FIND_PACKAGE_Backtrace=TRUE
cmake --build /work/decimal-build --target FortranDecimal -j 4
cmake -S /work/llvm-project/flang/runtime -B /work/runtime-build -G Ninja -DCMAKE_TOOLCHAIN_FILE=/work/ohos-toolchain.cmake -DCMAKE_BUILD_TYPE=Release -DLLVM_ENABLE_PIC=ON -DCMAKE_DISABLE_FIND_PACKAGE_Backtrace=TRUE -DFLANG_RUNTIME_F128_MATH_LIB=
cmake --build /work/runtime-build --target FortranRuntime -j 4
