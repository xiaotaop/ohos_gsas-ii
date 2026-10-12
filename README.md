# ohos_gsas-ii

GSAS-II 面向 HarmonyOS PC 的移植准备仓库。目前处于**第二阶段：无 GUI 核心计算 PoC**，尚无可运行的鸿蒙安装包，也未宣称移植成功。

GitCode 个人暂存仓库：<https://gitcode.com/2401_86708491/ohos_gsas-ii>。截至 2026-10-12，本地仓库与远端 `main` 已建立并通过 SSH 推送；社区申请状态见 [发布交接](docs/PUBLISHING.md)。

GSAS-II 是用于 X 射线及中子衍射等结构分析的上游开源软件。本项目拟先验证其脚本化科学计算核心在 HarmonyOS PC 上的运行与数值一致性，再决定桌面界面的具体实现及上架范围。

## 第二阶段进度

无 GUI 核心计算 PoC 已加入仓库。Windows x86-64 基线已完成源码编译和五阶段 PbSO4 精修，结果满足上游数值容差；HarmonyOS SDK 的 aarch64 C/C++ 入口也已确认。真机验证当前受两项条件限制：没有连接设备，SDK 没有 GSAS-II 所需的 Fortran 编译器。详见 [第二阶段核心 PoC](docs/PHASE2_CORE_POC.md)和[依赖矩阵](docs/PHASE2_DEPENDENCY_MATRIX.md)。

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

