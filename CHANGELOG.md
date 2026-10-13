# Changelog

## Unreleased — Phase 3

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

