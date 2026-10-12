# HarmonyOS 真机构建配置

本目录保留第二阶段真机 PoC 实际使用的 flang/Meson 配置。默认路径对应 HiShell 用户终端、Harmonybrew SDK 26.0.0.18、CPython 3.12.9 和 flang 20.1.0；若安装位置不同，应先生成一份替换了绝对路径的 cross file。

已验证工具版本：HarmonyOS 6.1.0.117（aarch64）、Clang 15.0.4、flang 20.1.0、Meson 1.12.1、Ninja 1.13.2。flang 包来自 OpenHarmonyPCDeveloper 的 Fortran 构建指导所列下载地址。

关键点：

- Meson 的 Fortran 健康检查不会使用普通 `fortran_link_args`，因此通过 `flang-ohos-wrapper.sh` 补齐 sysroot、启动对象和运行库。
- Python 扩展最终由 Clang 链接，所以 `c_link_args` 也必须静态链接 `FortranRuntime` 与 `FortranDecimal`；否则模块会在导入时报告 `_FortranA...` 符号缺失。
- HarmonyOS 会拒绝未签名的用户 ELF；构建完成后必须运行 `sign-native-modules.sh`。
- `gsas-ohos-cross.ini` 的绝对路径属于本次验证环境，不应原样用于不同用户或 SDK 版本。
- 本次诊断构建包含了 `pydiffax` 以确认编译能力，但没有提交或分发该二进制。正式分发构建必须先排除它，直到完成 DIFFaX 授权确认。

真机结果见 `poc/results/harmonyos-aarch64.json`。完整五阶段 PoC 直接从固定提交源码树运行，因此结果中的 `gsas_ii` 显示为 `not-installed`；实际执行的源码提交仍由 `upstream_commit` 字段锁定。
