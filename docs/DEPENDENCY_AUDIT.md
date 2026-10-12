# 依赖与构建审查

依据：锁定提交的 `pyproject.toml`、根目录 `meson.build` 和 `sources/meson.build`。本文件是第一阶段依赖清单，**不是**可运行的 HarmonyOS 依赖锁文件。

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

