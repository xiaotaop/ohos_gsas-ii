# Changelog

## Unreleased — 运行时载荷装配与 aarch64 交叉编译（2026-10-19，成员 B，仅宿主验证）

- 新增 `scripts/payload/`：可复现装配配方与 9 组件清单（`components.json`），锁定 CPython 3.12.9 ohos-aarch64、NumPy 2.2.6、SciPy 1.16.3、PyCifRW 5.0.1、prettytable 3.18.0、wcwidth 0.9.2、ply 3.11、GSAS-II 2.0.0@`2b4aba1b`、bridge 1.1.0，并记录每个下载的 SHA-256。
- 载荷经 `Write-RuntimeManifest.py` 与 `Prepare-Runtime.py` 两级门禁：2214 个文件、约 178 MB，逐文件哈希与内容检查（AArch64 ELF、无归档/字节码/外平台库）通过，状态 `prepared-not-device-validated`。
- 发布裁剪配方：pydiffax 导入块等价替换、25 个 wx/G2shapes GUI 模块删除与 12 处函数内导入中性化，AST 复扫保证无残留；去除 `help/`、`install/`、静态库 `.a`、测试数据与 `.npz` ZIP 容器。
- 修复 `CMakeLists.txt` 在 OHOS 工具链下的库查找：`ohos.toolchain.cmake` 的 `CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY` 使 `find_library` 失效；改为校验并直接链接载荷中的 `libpython3.12.so`。
- 使用 DevEco OHOS 工具链与真实 CPython 3.12.9 头/库完成 `-DGSAS_HAS_PYTHON` aarch64 交叉编译与链接；产物为 ELF64 AArch64 ET_DYN，`NEEDED` 含 `libpython3.12.so`。
- 仍未关闭：设备 dlopen/`Py_Initialize`、HAP 内五阶段数值验收、`pyspg` 等原生扩展（缺 flang 20.1.0）、Sobol QMC（`.npz` 被发布门禁裁剪）。本次未构建 HAP、未上真机。

## Unreleased — B03 终态日志 artifact 与跨进程快照（2026-10-19，成员 B，仅宿主验证）

- `job.failed`/`job.cancelled` 终态载荷新增**可选** `artifacts` 数组（CORE_API v1.1 兼容新增）：仅携带登记返回的 `log` artifact，fileId 必须是登记令牌；Schema、示例、语义验证器、ArkTS 共享模型与门面、UI、测试七处同步。
- 门面按决议顺序"先持久化并登记脱敏日志、再发终态"；登记未完成时事件不携带 `artifacts`，页面提示"日志登记未完成"，不从路径、文件名或历史消息推导。
- 终态快照持久化到 `outputs/<jobId>/core/terminal-snapshot.json`，进程重启后 `getJobSnapshot` 在原生台账缺失时按 jobId 恢复并再校验形状；`PROCESS_INTERRUPTED` 合成快照补齐 `state` 字段；未知/已清理 ID 保持 `JOB_NOT_FOUND`，A 端仅对失效近期 ID 降级。
- 快照与已登记产物一致性纳入断言：交付事件、内存视图与磁盘快照的终态载荷同形（宿主桥测试与 Python 捕获脚本）。
- 修复嵌入层缺陷：`python_host.cpp` 的 `EmitCallback` 注册为 METH_O 却按元组解析参数，真实 CPython 经 §8 调用 `emit_event` 必然抛 TypeError（桩构建与纯 Python 测试均无法暴露）。
- 新增宿主嵌入冒烟 `tests/python-host-embed-smoke.cpp`（不进 CI，需本机 libpython 开发包）：真实嵌入解释器加载真实 bridge 包并跑任务到唯一 `CORE_NOT_READY` 终态，事件跨越 C capsule 边界；已在 x86_64 验证，非 OHOS aarch64 证据。
- 新增运行时依赖：无。真实 CPython/GSAS-II 载荷、OHOS aarch64 上启用 `GSAS_HAS_PYTHON` 的编译/加载与真机证据仍未关闭；本次未构建 HAP。

## Unreleased — Phase 3

- 合并 ArkUI M1 mock 与 Python Bridge，并将两者的可脱机自测纳入 GitHub Actions。
- 修复 Bridge 未初始化错误映射、非法字段类型校验和 fileId 符号链接越界检查。
- 固定测试样例的原始字节与换行格式，确保 Windows 与 Linux Runner 使用相同 SHA-256。
- 新增 GitHub Actions 持续集成，自动检查 Python 语法、JSON、核心接口契约和测试样例完整性。
- 冻结 ArkUI、FileService、C++ N-API 和 Python Bridge 之间的核心接口 v1.0。
- 新增精修请求与核心事件 JSON Schema、成功/失败示例和无第三方依赖的契约校验脚本。
- 明确单任务状态机、文件 ID 与沙箱规则、事件顺序、取消语义、错误码和集成验收条件。

## Unreleased — Phase 2

- 新增无 GUI 的 GSASIIscriptable PbSO4 精修 PoC 和结构化结果格式。
- 在 Windows x86-64 上从锁定源码构建 GSAS-II 2.0.0，验证 C/Fortran 扩展和五阶段数值基线。
- 验证移除 PyCifRW 可选 `StarScan` C 加速器后核心 PoC 仍通过。
- 新增 HarmonyOS SDK/设备探测脚本、社区 Python wheel 探测脚本和依赖矩阵。
- 记录 Windows 原生 DLL 搜索要求，并确认 HarmonyOS SDK 的 aarch64 C/C++ 工具链可用。
- 在 HarmonyOS 6.1.0.117 aarch64 真机安装 CPython 3.12.9、NumPy、SciPy 和源码构建的 PyCifRW。
- 使用社区 flang 20.1.0 与 Meson 构建、签名并导入 GSAS-II 的 C/Cython/Fortran 原生扩展。
- 在鸿蒙 PC 真机完成同一套五阶段 PbSO4 精修，全部数值验收项通过，并提交结构化结果及可复现构建配置。

## Unreleased — Phase 1

- 固定 GSAS-II 上游提交与源码包地址。
- 记录运行、编译和 GUI 依赖，以及单独授权组件。
- 引入五个未修改的上游 PbSO4 测试样例并建立 SHA-256 校验。
- 准备社区建仓申请与阶段验收材料。

