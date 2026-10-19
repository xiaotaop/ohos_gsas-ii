# C：实际 HAP 的 SBOM 与原生依赖检查

使用 Python 3.13（载荷含 CPython 3.12 语法，Python 3.11 的源码审计不能替代）。从源码根目录运行：

```sh
python3.13 scripts/Build-HapSbom.py --hap FINAL.hap --manifest RUNTIME_MANIFEST.json --native-build-receipt native-modules.json --output NEW_EVIDENCE_DIR
```

工具重新执行 development HAP 审计，核对清单和包内所有文件的实际 SHA-256；不会信任旧 inventory。输出 CycloneDX 1.5 草稿、逐文件 inventory、SDK llvm-readelf 的 NEEDED/SONAME/RPATH/RUNPATH 记录。不执行 ELF、不改变签名或包字节，输出目录必须是新目录。

2026-10-19 新开发 HAP 的结果：2245 个文件、224 个 ELF（221 个运行时 + app-core/app-fileio/SDK C++ 库）。增加 --native-build-receipt 时，工具核对 8 个实际模块的路径/归属/哈希及包内 LLVM 许可文件，再为静态 FortranRuntime/FortranDecimal 20.1.8 记录 Apache-2.0 WITH LLVM-exception 义务，审查仍为 pending。为 5 个捆绑帮助库单列未知版本/许可，不能将 CPython 或 NumPy/SciPy 的主许可自动套用给 libffi、GDBM、Fortran 与两份 OpenBLAS。逐文件归属来自实际打包清单，父组件声明不等于全部嵌入代码的许可结论。静态链接进解释器/标准库/科学扩展的库仍需 B 提供构建物料和源码范围；仅扫描动态 NEEDED 不能声称 SBOM 完整。

依赖边分类：packaged-filename 仅表示同名文件入包；sdk-filename-only 仅表示当前 SDK sysroot 有此名字；unmatched 表示两处均未找到。三者都不证明设备加载器可见性、符号或 ABI 兼容。SONAME 记录不会伪装成已入包文件。signatureSectionPresent 只表示存在 .codesign 段，不能证明签名有效或正式证书链成立。

当前 unmatched：libc.musl-aarch64.so.1、libgcc_s.so.1，来自捆绑 GNU Fortran/OpenBLAS64 帮助库，仍需核定是否实际分发/加载。133 个 NumPy/SciPy 消费者的 CPython DT_NEEDED 已在独立副本统一到实际解释器 libpython3.12.so，再 strip/签名；该名称已不在未匹配项中。RPATH/RUNPATH 原样列出供重新布局后核对，不更改它们或绕过加载器。此工具永远输出 releaseApproved=false；草稿生成、格式验证和内容审计不能解除许可、签名或真实计算门禁。

格式依据：https://cyclonedx.org/docs/1.5/json/ 。本轮草稿已使用 CycloneDX 官方 1.5 JSON Schema 和其本地引用验证。
