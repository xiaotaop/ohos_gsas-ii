# 实验性 CPython 核心重建（尚未通过设备验收）

本配方只生成 OHOS AArch64 `libpython3.12.so`，不重建所有标准库扩展，不签名、不安装，也不批准分发。目的是移除旧核心中静态 libintl 实现，并在派生载荷中排除未使用的 readline、`_gdbm` 和 `libgdbm.so.6`。此前已验收的 25c9ef74… HAP 不受影响。

## 固定输入

- Python 官方 3.12.9 源码包，SHA-256 `45313e4c5f0e8acdec9580161d565cf5fea578e3eabf25df7cc6355bf4afa1ee`。
- 社区补丁提交 `135d712079ae8881b73aa94c4c01c7469ab11e8d`；逐补丁哈希见 `packaging/reviews/community-source-trace-20261020.json`。按顺序应用 81 个补丁，明确跳过不能应用的 0125 venv 补丁；不把这称作原预编译包的精确复建。
- 本目录 cross-configure.patch 修正跨平台构建时用 build_os 处理目标 triplet 的问题。
- 本机 DevEco SDK 中的 clang/compiler-rt 15.0.4、OHOS sysroot。SDK 不随仓库分发；实际输入哈希由构建凭据记录。

```sh
python3.13 scripts/ohos/controlled-cpython/Build-ControlledCore.py \
  --source-archive /absolute/path/Python-3.12.9.tgz \
  --community-repo /absolute/path/cpython \
  --sdk /Applications/DevEco-Studio.app/Contents/sdk/default/openharmony \
  --output /absolute/path/NEW-build-directory
```

`--prepare-only` 仅验证输入、解包并应用补丁。host 工具使用原始官方源码；target 使用固定补丁。macOS 大小写不敏感文件系统上必须构建 `python.exe`，避免 `make python` 将 `Python/` 目录误判为输出。

## 已完成的实验及后续门禁

手动执行相同构建参数已成功产出 AArch64 核心；核心 NEEDED 仅 libc.so，不定义旧 libintl 函数。保留的 218 个消费者所需 Python 动态符号均得到满足，关键 ABI 宏与旧核心一致。SDK 原生库签名、HAP 签名和内容审查通过。固定输入/补丁准备路径已用本脚本复验；尚未声称本脚本完整重跑构建或位级可复现。

凭据见 `packaging/reviews/c-controlled-core-prototype-20261020.json`。无线调试断开，TCP 端口超时，候选尚未安装。符号覆盖不能替代 Core 初始化、五阶段数值、系统导出与进程恢复验收。通过这些检查之前不得将其标成正式替代运行时；若后续安装失败，保留同签名已验收包进行回退，不自动卸载。

发布伴随源码还应包含实际采用的上游归档、固定补丁、此配方及 C 的增量补丁。保留标准库扩展仍来自社区归档，应单独说明，不把核心重建凭据套用到它们。
