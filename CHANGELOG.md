# Changelog

## Unreleased — B03 终态日志 artifact 与跨进程快照（2026-10-19，成员 B，仅宿主验证）

- `job.failed`/`job.cancelled` 终态载荷新增**可选** `artifacts` 数组（CORE_API v1.1 兼容新增）：仅携带登记返回的 `log` artifact，fileId 必须是登记令牌；Schema、示例、语义验证器、ArkTS 共享模型与门面、UI、测试七处同步。
- 门面按决议顺序"先持久化并登记脱敏日志、再发终态"；登记未完成时事件不携带 `artifacts`，页面提示"日志登记未完成"，不从路径、文件名或历史消息推导。
- 终态快照持久化到 `outputs/<jobId>/core/terminal-snapshot.json`，进程重启后 `getJobSnapshot` 在原生台账缺失时按 jobId 恢复并再校验形状；`PROCESS_INTERRUPTED` 合成快照补齐 `state` 字段；未知/已清理 ID 保持 `JOB_NOT_FOUND`，A 端仅对失效近期 ID 降级。
- 快照与已登记产物一致性纳入断言：交付事件、内存视图与磁盘快照的终态载荷同形（宿主桥测试与 Python 捕获脚本）。
- 新增依赖：无。真实 CPython/GSAS-II 载荷、`GSAS_HAS_PYTHON` 编译/加载与真机证据仍未关闭；本次未构建 HAP。

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

