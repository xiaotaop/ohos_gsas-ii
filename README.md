# ohos_gsas-ii

GSAS-II 面向 HarmonyOS PC 的移植准备仓库。**第二阶段：无 GUI 核心计算 PoC 已通过鸿蒙 PC 真机验证**；第三阶段的正式 ArkUI 页面、文件服务、C++ N-API 和核心门面已合入主线，但应用内真实 Python/GSAS-II 运行时尚未装包，因此当前仍没有可上架的 GUI 安装包。

代码仓库：[GitHub](https://github.com/xiaotaop/ohos_gsas-ii)、[GitCode](https://gitcode.com/2401_86708491/ohos_gsas-ii)。社区申请状态见 [发布交接](docs/PUBLISHING.md)。

GSAS-II 是用于 X 射线及中子衍射等结构分析的上游开源软件。本项目拟先验证其脚本化科学计算核心在 HarmonyOS PC 上的运行与数值一致性，再决定桌面界面的具体实现及上架范围。

## 第二阶段进度

Windows x86-64 基线与 HarmonyOS PC aarch64 真机均已完成同一套五阶段 PbSO4 精修，全部结果满足上游数值容差。真机环境为 HarmonyOS 6.1.0.117、CPython 3.12.9，并使用社区 NumPy/SciPy wheel、真机编译的 PyCifRW 及 flang 20.1.0 构建的 GSAS-II 原生扩展。结果见 `poc/results/harmonyos-aarch64.json`，构建细节见 [第二阶段核心 PoC](docs/PHASE2_CORE_POC.md)、[依赖矩阵](docs/PHASE2_DEPENDENCY_MATRIX.md)和[真机构建配置](scripts/ohos/README.md)。

## 第三阶段接口

ArkUI、文件服务、C++ N-API 和 Python/GSAS-II 核心之间的 v1.0 接口已冻结，见 [核心接口契约](docs/CORE_API.md)。JSON Schema 与可用于界面 mock 的成功/失败示例位于 `contracts/`，可运行 `python scripts/Validate-CoreContracts.py` 校验。

M1 ArkUI 源码映射与接入说明见 [M1 ArkUI 演示](docs/M1_ARKUI.md)，工程位于 `ui-mock/`，按锁定上游 wxPython 源码翻译菜单、数据树、Controls 与 Refine 交互子集。成功、失败、取消、窗口适配及基本键鼠操作已通过 HarmonyOS PC 模拟器验收，附运行截图。演示使用模拟数据，未接入真实计算和文件导出；真机 GUI 验收与正式工程集成待完成。

A/B/C 的工程入口、公共类型、文件服务、初始化、日志产物及组长审核结论，见 [接入对齐清单](docs/INTEGRATION_ALIGNMENT.md)。代码级审核通过不等同于真实运行时、真机或发布验收通过。

成员 C 的正式 PC 工程与持久化文件服务位于 `app/`，支持系统选择器导入、fileId 查询/删除、真实文件导出及原生产物登记。构建和 A/B 接入方式见 [成员 C 交接](docs/MEMBER_C_HANDOFF.md)，组件清单见 [应用依赖初稿](docs/APP_DEPENDENCY_INVENTORY.md)。应用已接入计算 CoreService/N-API 编排；没有真实 Python 头文件、原生库和 `rawfile/runtime/manifest.json` 时仍编译为 `CORE_NOT_READY` 桩，不表示已经形成可上架版本。中文工作目录可运行 `python3 scripts/Build-App.py --check`，脚本在英文临时目录调用 DevEco CLI。

成员 C 的 C01/C02 接收人、复现步骤和剩余确认见 [交接入口](docs/MEMBER_C_HANDOFF.md#0-交接入口与接收顺序2026-10-17)；C 的交付及 A/B 的首轮应用接入均已合入主线。组长已完成 A03～A07、B01～B06 的代码级复核，未关闭项及真实计算、真机验收要求以接入对齐清单为准。

正式 `app/` 已接入五份精修输入的选择、关联持久化和真实文件完整性校验；重选保留旧文件，取消保留原关联。应用包含六组菜单、可拖动分栏、真实输入数据树、参数草稿编辑器，以及五阶段任务/取消/结果/产物导出页面。PR #4 已把 CoreService/N-API、运行时安装器、任务快照和文件租约编排注入正式页面，相关宿主、契约及原生测试通过；但当前 HAP 未包含真实 CPython/GSAS-II 载荷，失败/取消日志也尚未通过终态事件向界面公开可导出的 fileId。开发交接、审核边界和剩余依赖见 [接入对齐清单](docs/INTEGRATION_ALIGNMENT.md)。完整原版 GUI、真实应用内计算与发布验收尚未完成。

A 端最新收尾补齐核心初始化状态/重试、表单保留、失效任务 ID 恢复及 B03 可选日志产物消费入口；40 项会话/门面对接测试通过，ARM64 构建及 21 条目开发包审计通过，并有 API24 模拟器运行时缺失/重试实测。真实计算载荷及 B03 协议侧产物返回仍依赖 B，详见 [A 端接入收尾](docs/INTEGRATION_ALIGNMENT.md#a-端接入收尾2026-10-19)。

后续打包准备提供 [运行时装配与构建留档](docs/RUNTIME_PACKAGING.md)：Build-App 自动保留源码/工具链记录、HAP 和内容清单；Prepare-Runtime 按 B 的清单校验载荷；Audit-Hap 核对实际包内容。当前未打包真实 Python，发布条件见 [验收与材料清单](docs/RELEASE_ACCEPTANCE.md)。

## 持续集成

GitHub Actions 配置位于 `.github/workflows/ci.yml`，在分支推送、面向 `main` 的 Pull Request 以及手动触发时执行 Python 语法、JSON、接口契约、测试样例完整性、Python Bridge 自测、原生文件排他创建、宿主文件服务和 ArkUI mock 状态模型测试。启用方法及云端 CI 的范围见 [持续集成说明](docs/CI.md)。

## 第一阶段成果

- [上游源码锁定](docs/UPSTREAM_LOCK.md)：固定到 `2b4aba1bc44de63a3da9d4495944c3b99e389399`。
- [依赖和编译审查](docs/DEPENDENCY_AUDIT.md)：区分脚本化核心、原 GUI、原生扩展与未锁定项。
- [授权审查](docs/LICENSE_AUDIT.md)：明确 GSAS-II 主许可证、DIFFaX 和 Shapes 的分发门槛。
- [测试计划](docs/TEST_PLAN.md)：上游 PbSO4 样例、SHA-256 和数值参考。
- [第一阶段验收](docs/PHASE1_ACCEPTANCE.md)：已完成项、未完成项和第二阶段入口条件。
- [社区建仓申请草稿](docs/GITCODE_APPLICATION.md)：保留备用；按当前决定，先在个人仓库完成开发，再进入上架流程。
- [无 GUI 核心计算 PoC](poc/core_refinement.py)：统一的桌面/鸿蒙数值验证入口。

校验本仓库内测试样例：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Verify-Fixtures.ps1
```

上游项目：[GSAS-II](https://github.com/AdvancedPhotonSource/GSAS-II)。社区规范：[Harmony PC 开发者社区](https://gitcode.com/OpenHarmonyPCDeveloper/docs)。本仓库与上游团队、OpenHarmonyPCDeveloper 社区均无官方隶属关系；社区接收和应用上架仍需分别审核。

This product includes software produced by UChicago Argonne, LLC under Contract No. DE-AC02-06CH11357 with the Department of Energy.

