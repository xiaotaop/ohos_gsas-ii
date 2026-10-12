# 第二阶段依赖矩阵

本矩阵用于决定无 GUI 核心 PoC 是否具备 HarmonyOS PC aarch64 运行条件。它不把 Windows `.pyd` 视为可移植产物，也不把“社区源有包名”视为已经通过真机验证。

| 组件 | Windows 基线 | HarmonyOS PC 状态 | 第二阶段处置 |
|---|---|---|---|
| CPython | 3.12.10 | 社区方案已在 aarch64 上验证 CPython 3.12.9 嵌入；本仓库尚未取得运行时载荷 | 采用 ArkTS/ArkUI 外壳加应用内直接链接 `libpython3.12.so` 的路线 |
| NumPy | 2.2.6 | 社区 Python 源存在 `cp312-ohos_aarch64` 2.2.6 wheel | 锁定 2.2.6，随包放入 `site-packages` 并重签原生库 |
| SciPy | 1.16.3 | 社区 Python 源存在 `cp312-ohos_aarch64` 1.16.3 wheel | 锁定 1.16.3，与 Windows 基线保持一致 |
| PyCifRW | 5.0.1 | 社区源没有 OHOS wheel；`StarScan` 是可选 C 加速器 | 优先使用纯 Python `standard` 扫描器；本阶段已在移除 `StarScan.pyd` 后重跑 PoC 并通过 |
| GSAS-II Python 代码 | 2.0.0 / 固定提交 | Python 层可复制，但社区源无 GSAS-II 项目页 | 从固定提交组装，不依赖在线安装最新版 |
| `pyspg` | gfortran 构建 | 必需的 f2py/Fortran 扩展；尚无 OHOS wheel | 需要 OHOS Fortran 工具链或等价的可信预编译产物 |
| `pypowder` | gfortran 构建 | 必需的 f2py/Fortran 扩展；尚无 OHOS wheel | 同上 |
| `pytexture` | gfortran 构建 | 必需的 f2py/Fortran 扩展；尚无 OHOS wheel | 同上 |
| `pydiffax` | wheel 默认包含 | 本 PoC 不直接导入；存在单独下游分发授权门槛 | 鸿蒙构建默认排除，取得依据前不进入分发物 |
| wxPython GUI | 未纳入核心 PoC | 无可直接复用的 HarmonyOS 桌面 wheel | 第二阶段不处理；后续使用原生 ArkUI/ArkWeb 壳层 |

## 已验证事实

- Windows 基线完整运行五阶段 PbSO4 精修，结果见 `poc/results/windows-x86_64.json`。
- 临时移除 PyCifRW 的 `StarScan.cp312-win_amd64.pyd` 后，完整 PoC 仍然通过，所有 Rwp 与择优取向系数相对标准基线的差值均为 0。结果见 `poc/results/windows-x86_64-no-starscan.json`。这证明本用例可避开 PyCifRW 的 C 加速器，但仍需在鸿蒙真机复验。
- 2026-10-12 查询社区 Python 源：NumPy 2.2.6 和 SciPy 1.16.3 均有 `cp312-ohos_aarch64` wheel；PyCifRW 没有 OHOS wheel；`gsas-ii` 项目页返回 404。机器可读快照见 `poc/results/ohos-python-index.json`。
- 本机 HarmonyOS SDK 6.0.2/API 22 的 Clang 能识别 `aarch64-unknown-linux-ohos`，但 SDK 内没有 gfortran/flang；`hdc` 当前也未发现设备。见 `poc/results/harmony-environment.json`。
- `scripts/Build-HarmonyCProbe.ps1` 已使用该 SDK 成功生成 `EM_AARCH64` ELF 共享库，说明 C 交叉编译本身不是当前阻塞点。

## 参考实现与边界

- Flojoy Studio 鸿蒙移植仓库固定参考提交：`8549836fbad0eb09bef84d1c1f05370525f07ad5`。该实现记录了 CPython 3.12.9、NumPy/SciPy OHOS wheel、应用内直接链接 `libpython3.12.so`、`collectAllLibs=true` 以及原生 `.so` 重签流程。本项目只借鉴架构，不复制其应用代码或二进制载荷。
- 社区开发指南：[鸿蒙应用嵌入 Python 运行时：ArkTS + CPython 混合开发实战](https://gitcode.com/OpenHarmonyPCDeveloper/docs/blob/main/contribute/develop-guide/%E9%B8%BF%E8%92%99%E5%BA%94%E7%94%A8%E5%B5%8C%E5%85%A5Python%E8%BF%90%E8%A1%8C%E6%97%B6-ArkTS%E4%B8%8ECPython%E6%B7%B7%E5%90%88%E5%BC%80%E5%8F%91%E5%AE%9E%E6%88%98.md)。
- 社区 Python 源：<https://pypi.cnb.cool/OpenHarmonyPCDeveloper/pypi/-/packages/simple>。
- 有实验性第三方项目 `sxgou/gfortran-harmonyos` 声称可在 HarmonyOS 上构建 gfortran，但 2026-10-12 检查的提交 `212e43e1ee6b5471428df07fc6afa342d7fc7b65` 没有正式 release，也未包含明确许可证文件，且尚未在本项目 SDK/API 和 GSAS-II f2py 扩展上验证。因此它只能作为技术线索，当前不可作为发布依赖直接纳入。

## 当前结论

第二阶段桌面基线和可移植依赖审查已完成。鸿蒙核心 PoC 还不能标记为通过：必须先获得可审计的 OHOS Fortran 编译链，生成 `pyspg`、`pypowder`、`pytexture`，随后连接鸿蒙 PC 运行同一测试脚本。仅安装 NumPy/SciPy wheel 不足以运行 GSAS-II 精修。
