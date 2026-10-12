# 第二阶段依赖矩阵

本矩阵用于决定无 GUI 核心 PoC 是否具备 HarmonyOS PC aarch64 运行条件。它不把 Windows `.pyd` 视为可移植产物，也不把“社区源有包名”视为已经通过真机验证。

| 组件 | Windows 基线 | HarmonyOS PC 状态 | 第二阶段处置 |
|---|---|---|---|
| CPython | 3.12.10 | 真机已安装并运行 CPython 3.12.9 | 第三阶段集成为应用私有运行时，并直接链接 `libpython3.12.so` |
| NumPy | 2.2.6 | 真机安装 `cp312-ohos_aarch64` 2.2.6 wheel，导入和精修通过 | 锁定 2.2.6，随包放入 `site-packages` 并重签原生库 |
| SciPy | 1.16.3 | 真机安装 `cp312-ohos_aarch64` 1.16.3 wheel，导入和精修通过 | 锁定 1.16.3，与 Windows 基线保持一致 |
| PyCifRW | 5.0.1 | 真机源码构建出 `ohos_aarch64` wheel；`StarScan` 成功导入，完整精修通过 | 固化构建配方；仍可保留纯 Python 扫描器作为降级路径 |
| GSAS-II Python 代码 | 2.0.0 / 固定提交 | Python 层可复制，但社区源无 GSAS-II 项目页 | 从固定提交组装，不依赖在线安装最新版 |
| `pyspg` | gfortran 构建 | flang 20.1.0 真机构建、签名、导入及精修通过 | 固化到排除 DIFFaX 的发布构建 |
| `pypowder` | gfortran 构建 | flang 20.1.0 真机构建、签名、导入及精修通过 | 同上 |
| `pytexture` | gfortran 构建 | flang 20.1.0 真机构建、签名、导入及精修通过 | 同上 |
| `pydiffax` | wheel 默认包含 | 真机诊断构建及导入通过，但存在单独下游分发授权门槛 | 发布构建默认排除，取得依据前不进入分发物 |
| wxPython GUI | 未纳入核心 PoC | 无可直接复用的 HarmonyOS 桌面 wheel | 第二阶段不处理；后续使用原生 ArkUI/ArkWeb 壳层 |

## 已验证事实

- Windows 基线完整运行五阶段 PbSO4 精修，结果见 `poc/results/windows-x86_64.json`。
- 临时移除 PyCifRW 的 `StarScan.cp312-win_amd64.pyd` 后，Windows 完整 PoC 仍然通过；鸿蒙真机随后也成功源码构建并导入 `StarScan`，两条路线均已得到验证。
- 2026-10-12 查询社区 Python 源：NumPy 2.2.6 和 SciPy 1.16.3 均有 `cp312-ohos_aarch64` wheel；PyCifRW 没有 OHOS wheel；`gsas-ii` 项目页返回 404。机器可读快照见 `poc/results/ohos-python-index.json`。
- HAD-W24 真机已连接并确认 HarmonyOS 6.1.0.117、aarch64；设备侧 Harmonybrew SDK 26.0.0.18 的 Clang 15.0.4 和社区 flang 20.1.0 已完成构建验证。
- `scripts/Build-HarmonyCProbe.ps1` 已使用该 SDK 成功生成 `EM_AARCH64` ELF 共享库，说明 C 交叉编译本身不是当前阻塞点。
- `poc/results/harmonyos-aarch64.json` 记录了完整五阶段精修结果，所有验收项通过。

## 参考实现与边界

- Flojoy Studio 鸿蒙移植仓库固定参考提交：`8549836fbad0eb09bef84d1c1f05370525f07ad5`。该实现记录了 CPython 3.12.9、NumPy/SciPy OHOS wheel、应用内直接链接 `libpython3.12.so`、`collectAllLibs=true` 以及原生 `.so` 重签流程。本项目只借鉴架构，不复制其应用代码或二进制载荷。
- 社区开发指南：[鸿蒙应用嵌入 Python 运行时：ArkTS + CPython 混合开发实战](https://gitcode.com/OpenHarmonyPCDeveloper/docs/blob/main/contribute/develop-guide/%E9%B8%BF%E8%92%99%E5%BA%94%E7%94%A8%E5%B5%8C%E5%85%A5Python%E8%BF%90%E8%A1%8C%E6%97%B6-ArkTS%E4%B8%8ECPython%E6%B7%B7%E5%90%88%E5%BC%80%E5%8F%91%E5%AE%9E%E6%88%98.md)。
- 社区 Python 源：<https://pypi.cnb.cool/OpenHarmonyPCDeveloper/pypi/-/packages/simple>。
- 未采用此前调研的实验性 `sxgou/gfortran-harmonyos`。本次使用 OpenHarmonyPCDeveloper Fortran 指导提供的 flang 20.1.0 包；其运行库进入最终分发物前仍需完成来源、许可证和源码义务审计。

## 当前结论

第二阶段鸿蒙核心 PoC 已通过。真机证明 CPython 科学计算依赖、GSAS-II 的 C/Cython/Fortran 原生扩展和完整无 GUI 精修链路均可运行。下一阶段的主要问题已从“核心能否移植”转为“如何形成合规、可重复、可上架的 HAP 与原生桌面体验”。
