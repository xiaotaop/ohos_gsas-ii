# 第二阶段：无 GUI 核心计算 PoC

## 目标与验收标准

同一套程序在桌面基线环境和 HarmonyOS PC 目标设备上完成五阶段 PbSO4 精修，五组 Rwp 均满足上游测试的 `rtol=1e-4`、`atol=1e-7`，择优取向系数满足 `rtol=1e-3`。程序还必须验证五份输入文件的 SHA-256，并输出机器可读 JSON。

入口为 `poc/core_refinement.py`，PowerShell 包装脚本为 `scripts/Run-CorePoc.ps1`。它只使用 `GSASIIscriptable`，不启动 wxPython GUI。

## Windows x86-64 基线

2026-10-12 在 Python 3.12.10、NumPy 2.2.6、SciPy 1.16.3、PyCifRW 5.0.1 上，从锁定的上游提交构建 GSAS-II 2.0.0 wheel。编译器为 GCC/gfortran 6.3.0，Meson 1.12.1，Ninja 1.13.2。构建和全部精修通过；结构化结果见 `poc/results/windows-x86_64.json`。

Windows 需要让 Python 能定位 `libgfortran-3.dll` 等 MinGW 运行库。PoC 使用 `--dll-dir` 调用 `os.add_dll_directory()`，不能只修改 PATH。示例：

```powershell
.\scripts\Run-CorePoc.ps1 `
  -Python D:\path\to\venv\Scripts\python.exe `
  -DllDirectory D:\path\to\mingw64\bin `
  -Output poc/results/windows-x86_64.json
```

## HarmonyOS PC 真机结果

2026-10-12 已在 HAD-W24 鸿蒙 PC 上完成验证。设备为 HarmonyOS 6.1.0.117、aarch64、HongMeng Kernel 1.12.0；用户终端安装 CPython 3.12.9、NumPy 2.2.6、SciPy 1.16.3 和 PyCifRW 5.0.1。PyCifRW 的 `StarScan` C 扩展在真机源码构建并成功导入。

设备上的 Harmonybrew SDK 26.0.0.18 提供 Clang 15.0.4。按照 OpenHarmonyPCDeveloper 的 Fortran 项目指导取得 flang 20.1.0 后，先编译、签名并由 Python `ctypes` 加载独立 Fortran 动态库，再通过 Meson 构建固定 GSAS-II 提交的 9 个原生扩展。签名后以下模块全部在真机导入成功：`fmask`、`histogram2d`、`pack_f`、`pydiffax`、`pypowder`、`pyspg`、`pytexture`、`unpack_cbf`、`kvec_general`。

同一 `poc/core_refinement.py` 随后完成五阶段 PbSO4 精修，全部 Rwp 和择优取向系数满足既定容差，结构化结果见 `poc/results/harmonyos-aarch64.json`。运行耗时 14.305 秒。该次测试直接从固定源码树运行，未安装 wheel，所以结果中的 `gsas_ii` 元数据为 `not-installed`；实际提交由结果中的 `upstream_commit` 锁定。

主机 SDK 探测仍可用以下命令重跑：

```powershell
.\scripts\Probe-HarmonyEnvironment.ps1
.\scripts\Probe-OhosPythonIndex.ps1
```

仓库还包含一个不依赖第三方库的 C 探针。以下命令已成功产出 `EM_AARCH64` ELF 共享库：

```powershell
.\scripts\Build-HarmonyCProbe.ps1
```

依赖逐项状态、社区 wheel 可用性和 Flojoy 参考架构见 [第二阶段依赖矩阵](PHASE2_DEPENDENCY_MATRIX.md)。

## 第二阶段验收结论

第二阶段已通过：目标设备、Python 科学计算依赖、C/C++/Fortran 编译链、原生扩展签名加载，以及完整脚本化精修均已真机验证。可复用的 flang 包装器、Meson cross file 和签名脚本位于 `scripts/ohos/`。

进入第三阶段前仍需完成的发布工程工作：

1. 将目前的真机开发构建固化为排除 `pydiffax` 的可重复构建，并生成 wheel 或应用私有 Python 载荷。
2. 为最终进入 HAP 的 Python、NumPy、SciPy、PyCifRW、flang 运行库和 GSAS-II 文件建立 SBOM 与许可证清单。
3. 设计 ArkUI 桌面壳层、后台任务模型、文件选择/保存与错误展示，并验证大文件与长时间精修。
4. 在应用沙箱内完成打包、签名、安装、卸载和冷启动测试；当前 HiShell 用户终端结果不能替代 HAP 集成验证。

## 已识别的工程/合规门槛

- 上游默认构建 `pydiffax`。本次 Windows wheel 为本地可行性诊断而构建，没有发布；HarmonyOS 可分发包必须先取得 DIFFaX 下游分发依据，或修改构建使其不包含 DIFFaX 并验证所需功能不受影响。
- `GSASII/G2shapes.py` 为 GPL-3+，是否纳入最终应用必须单独作兼容性决定。
- 原生扩展依赖编译器运行库。最终包需使用目标系统支持的动态库、静态链接方案或应用私有库目录，并完成相应许可证审查。
- 真机诊断构建中的 `pydiffax` 只用于确认技术可构建性，没有提交或分发二进制。可发布构建仍须排除它或先取得明确的下游分发依据。
- 本阶段证明 GSAS-II 脚本化核心可以在鸿蒙 PC 真机运行，并不代表原 wxPython GUI 已移植，也不代表 HAP 已满足上架要求。
