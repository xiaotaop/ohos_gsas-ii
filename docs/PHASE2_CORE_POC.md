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

## HarmonyOS PC 探测结果

本机已安装 HarmonyOS 6.0.2/API 22 SDK。其 Clang 15.0.4 可识别 `aarch64-unknown-linux-ohos`，C/C++ 交叉编译入口可用；SDK 内没有 gfortran 或 flang，`hdc list targets` 当前返回 `[Empty]`。完整快照见 `poc/results/harmony-environment.json`，可用以下命令重新生成：

```powershell
.\scripts\Probe-HarmonyEnvironment.ps1
.\scripts\Probe-OhosPythonIndex.ps1
```

仓库还包含一个不依赖第三方库的 C 探针。以下命令已成功产出 `EM_AARCH64` ELF 共享库，用来区分“SDK C 工具链可用”和“GSAS-II Fortran 工具链仍缺失”这两个事实：

```powershell
.\scripts\Build-HarmonyCProbe.ps1
```

依赖逐项状态、社区 wheel 可用性和 Flojoy 参考架构见 [第二阶段依赖矩阵](PHASE2_DEPENDENCY_MATRIX.md)。

## HarmonyOS PC 待验证项

1. 确认目标设备 CPU 架构、HarmonyOS PC SDK/API 版本和可用的 Python 3.12 运行时。
2. 按社区实践取得 CPython 3.12.9 运行时，使用已存在的 NumPy/SciPy OHOS wheel，并以纯 Python 模式安装 PyCifRW；不得复用 Windows `.pyd`。
3. 验证实验性 OHOS gfortran 路线，为目标平台配置 Meson cross file、NumPy 头文件和 Fortran/C 链接参数，先只构建 `pyspg`、`pypowder`、`pytexture`。
4. 在真机运行同一 `core_refinement.py`，提交结果 JSON，并与 Windows 基线逐阶段比较。
5. 对最终要分发的动态运行库建立 SBOM，确认许可证和源码提供义务。

## 已识别的工程/合规门槛

- 上游默认构建 `pydiffax`。本次 Windows wheel 为本地可行性诊断而构建，没有发布；HarmonyOS 可分发包必须先取得 DIFFaX 下游分发依据，或修改构建使其不包含 DIFFaX 并验证所需功能不受影响。
- `GSASII/G2shapes.py` 为 GPL-3+，是否纳入最终应用必须单独作兼容性决定。
- 原生扩展依赖编译器运行库。最终包需使用目标系统支持的动态库、静态链接方案或应用私有库目录，并完成相应许可证审查。
- 当前结果证明脚本化核心及数值基线在 Windows x86-64 可复现，也证明 PyCifRW 的可选 `StarScan` 加速器不是本用例的硬依赖；不等于已在 HarmonyOS PC 上运行。
