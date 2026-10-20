# 依赖与构建审查

依据：锁定提交的 `pyproject.toml`、根目录 `meson.build` 和 `sources/meson.build`。下表是**第一阶段历史风险清单**，不是当前依赖状态或 HarmonyOS 依赖锁。当前 B 的 CPython/NumPy/SciPy 等下载来源、版本和 SHA-256 已记录在[载荷配方](../scripts/payload/README.md)；C 从锁定上游源码重建 8 个 GSAS 原生扩展，指定设备 HAP 已完成应用内五阶段。仍须关闭预编译运行时内嵌第三方库的精确源码、版本和许可，见[C 签名 HAP 交付](C_SIGNED_HAP_DELIVERY.md)及[验收矩阵](RELEASE_ACCEPTANCE.md)。

| 范围 | 上游声明/现状 | HarmonyOS PC 处理方向 | 状态 |
| --- | --- | --- | --- |
| Python 运行时 | CPython `>=3.10`；包声明支持 3.10–3.13 | 先验证 3.12 的目标架构移植与嵌入方案 | 未验证 |
| 脚本核心 | NumPy、SciPy、PyCifRW，无固定精确版本 | 分别确认 HarmonyOS PC 可用版本与 ABI，形成哈希锁定表 | 未锁定 |
| 原始 GUI | wxPython `>=4.1`、Matplotlib、PyOpenGL | 原 GUI 不视为可直接运行；优先定义 ArkUI 前端与脚本核心的最小接口 | 未验证 |
| 原生扩展 | C、Fortran、Cython，NumPy f2py；`pypowder`、`pydiffax`、`histogram2d`、`pack_f`、`pytexture`、`pyspg`、`fmask` 等 | 按目标 CPU/系统重新编译，不复用 Windows/macOS 二进制 | 未验证 |
| 构建系统 | meson-python、Ninja、wheel、Cython、NumPy、pyproject-metadata、tomli；Meson 需要 Fortran 编译器 | 建立 HarmonyOS PC 交叉编译 PoC，记录编译器、SDK、ABI | 未验证 |
| 可选功能 | requests、Pillow、h5py、imageio、pybaselines、xmltodict、seekpath、gitpython、zarr、sympy | MVP 逐项评估，不默认全部捆绑 | 未纳入 |

关键发现：`sources/meson.build` 默认构建 `pydiffax`，而 DIFFaX 的下游再分发许可需要单独确认。因此不能直接以原构建产物作为上架包；必须先确认授权，或证明可在不包含 DIFFaX 的配置下构建并完成功能验收。Shapes (`GSASII/G2shapes.py`) 也应按独立 GPL-3+ 组件处理。

第二阶段开工前需要确定：HarmonyOS PC 设备架构、SDK/编译器版本、Python/NumPy/SciPy 可用版本及来源、是否拥有真实设备测试条件。未确定这些条件前，不能声称“可移植已验证”。

增量核对（2026-10-19，B03 终态 artifact PR `core/b03-terminal-artifacts`）：契约/ArkTS/C++ 嵌入层修复与测试未新增或变更运行时依赖。`GSAS_HAS_PYTHON` 分支已在宿主 x86_64 编译/链接并完成真实嵌入解释器 §8 加载冒烟（并修复其间发现的 emit capsule 缺陷）。

载荷增量核对（2026-10-19）：已按 [RUNTIME_PACKAGING](RUNTIME_PACKAGING.md) §2 装配并过两级门禁的 aarch64 载荷锁定以下版本（逐项来源与 SHA-256 见 [`scripts/payload/README.md`](../scripts/payload/README.md)）：CPython 3.12.9（社区 ohos-aarch64，`libpython3.12.so` + 头文件 + stdlib）、NumPy 2.2.6、SciPy 1.16.3、PyCifRW 5.0.1、prettytable 3.18.0、wcwidth 0.9.2、ply 3.11、GSAS-II 2.0.0@`2b4aba1bc44de63a3da9d4495944c3b99e389399`、bridge 1.1.0。`Write-RuntimeManifest.py` 与 `Prepare-Runtime.py` 在宿主 x86_64 上通过（2214 文件、约 178 MB，状态 `prepared-not-device-validated`）；OHOS aarch64 的 `GSAS_HAS_PYTHON` 交叉编译/链接已完成（§3.2）。**仍未关闭**：设备 dlopen/`Py_Initialize`、HAP 内真实数值验收；**发布阻断**：8 个 GSAS-II 原生扩展（`pyspg` 等，缺 flang 20.1.0）未随载荷发布。`pyspg` 不是可选加速器——缺少它时 `GSASIIobj.SetNewPhase` 的 `P1SGData` 初始化失败，相文件无法导入；`scripts/payload/check_gsas_native.py` 会拒绝该载荷。SciPy Sobol QMC 的 `.npz` 数据因发布门禁不随包发送，属明确裁剪。`distributionReview` 全部仍为 `pending`。

后续补充（同日，以上 2214 文件版本保留为历史审计快照）：在 HAD-W32 的 HiShell 中导入 8 个已签名 aarch64 扩展并运行五阶段；本地 2230 文件组装物不带 `--allow-missing` 通过原生模块门禁，见[真机补充验证](B_DEVICE_VALIDATION_2026-10-19.md)。**现状再更新（2026-10-20）**：C 已从锁定源码重建 8 模块，指定设备签名 HAP 已在应用沙箱完成五阶段与独立数值比较。`distributionReview` 仍为 `pending`，所缺是预编译第三方库的精确来源/许可和公开分发放行，不是 HAP 内计算证据。

