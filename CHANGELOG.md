# Changelog

## Unreleased — 运行时依赖与许可清单（2026-10-20，成员 B）

- 新增 [`docs/DEPENDENCY_LICENSES.md`](docs/DEPENDENCY_LICENSES.md)：按真实载荷字节列出预编译 CPython/NumPy/SciPy 的下载来源、SHA-256、源码地址与 `_sysconfigdata` 记录的构建参数；内嵌第三方库（libffi 3.4.4、GDBM 1.24、OpenSSL 1.1.1w、SQLite 3.49.1、bzip2 1.0.8、XZ 5.8.2、ncurses 6.6、Expat 2.6.4、libmpdec 2.5.1、OpenBLAS 0.3.29）的版本、静态/动态链接方式、消费者与许可证。
- 新增 [`packaging/third-party.dependencies.json`](packaging/third-party.dependencies.json)（机器可读，含逐文件大小/SHA-256）与 [`packaging/licenses/third-party/`](packaging/licenses/third-party/NOTICE.md)（许可原文、NOTICE、`SOURCES.json`）。
- 结论：`numpy.libs/libscipy_openblas64_.so` 与 `libgfortran.so.5` 无任何 DT_NEEDED 消费者，可从载荷安全移除（约 23.4 MiB），并消除 `libgcc_s.so.1`/`libc.musl-aarch64.so.1` 两个未匹配依赖；SciPy 实际使用的 `libscipy_openblas-80d8b5fa.so` 必须保留。

## Unreleased — 远端文档与验收状态统一（2026-10-20）

- 将 README、验收矩阵、接入、依赖、UI、运行时与发布文档统一到 PR #9 合并后的证据：指定设备 internaltesting 签名 HAP 已在 HAD-W32/API23 完成应用内五阶段、独立数值、三类导出及成功任务恢复。
- 区分 B 已交付的基础运行时下载来源/哈希、C 已交付的 8 个 GSAS 模块可复建配方，与仍待审的预编译运行时内嵌第三方库源码/许可；保留旧记录为历史快照。
- 明确失败/取消与生命周期同包补验、API20/API24 范围决策、最终 SBOM/公开分发和社区建仓/上架申请仍未完成；不改变 `releaseApproved=false`。

## Unreleased — 指定设备签名 HAP 与源码伴随包（PR #9，2026-10-19）

- C 的 `release/internaltesting` HAP 在 HAD-W32/API23 干净安装，五份输入、PbSO4 五阶段、GPX/JSON/日志导出、独立数值比较及成功任务重启恢复通过；安装签名阻塞解除。证据与 HAP 哈希见[交付记录](docs/C_SIGNED_HAP_DELIVERY.md)。
- GSAS/移植源码伴随包、8 个原生扩展构建凭据及实际 HAP SBOM 草案已交付；第三方预编译运行时的精确源码/版本/许可、公开分发与上架放行仍待完成。

## Unreleased — C 本地原生运行时与应用内验收（2026-10-19）

- 新增可重建的 OHOS ARM64 8 扩展交叉编译补丁与 LLVM20.1.8 配方，排除 DIFFaX，修复 fmask 的 NumPy API 初始化。
- 将运行时 ELF 装配到 HAP 原生目录，保留版本库名、133 个 Python 依赖名称修复、141 个扩展映射及空命名空间；避免后续 strip 破坏开发签名，并释放解释器初始化线程的 GIL。
- 完成 API26 模拟器实际 HAP 的五阶段计算、数值独立比较、工程导出与取消/恢复验收；修复参数草稿刷新和 ArkTS 页面集成问题。新增实际 HAP 的逐文件 SBOM、静态 LLVM 义务核验与 CI 回归。详见 [C 验收记录](docs/C_NATIVE_ACCEPTANCE.md)。
- 本次提交提供源码、配方和紧凑证据。完整运行时/HAP 留作本地交接；正式签名、API20/API24 真机、完整许可及发布审批仍待完成。

## Unreleased — 扩展来源与载荷冻结顺序（2026-10-19，成员 B）

- 新增 [docs/EXTENSIONS_BUILD.md](docs/EXTENSIONS_BUILD.md)：8 个扩展的上游提交、设备侧 flang 20.1.0 / Meson 诊断构建与导出步骤（引用 `scripts/ohos/`）、既有归档 SHA-256、门禁方式，以及静态链接 LLVM FortranRuntime（Apache-2.0 WITH LLVM-exception）的许可义务；排除 `pydiffax` 的发布构建配方仍待固化。
- `scripts/payload/README.md` 新增 §6“原生扩展与清单冻结顺序”：冻结前必须先 strip 顶层 `libpython3.12.so` 再生成清单（设备侧已验证 `packaged runtime mismatch`），并记录 2230 与 2214 文件差异需逐项核对。
- SBOM 草案 metadata 标注 FortranRuntime 静态链接义务；`distributionReview` 保持 `pending`。

## Unreleased — 真机补充验证与开发增量合并（2026-10-19）

- B PR #6 与 A PR #5 已按依赖顺序通过代码级审核并合入主线；B03 日志 artifact、持久化终态快照、A 端初始化重试与展示/导出入口均为当前代码，不再列为待实现。
- HAD-W32 / HarmonyOS 6.1.0.115 的 HiShell 中，8 个 OHOS aarch64 原生扩展导入、PbSO4 五阶段及 Python Bridge 真实任务通过；本地 2230 文件载荷在不带 `--allow-missing` 的门禁下通过，详见 [真机补充验证](docs/B_DEVICE_VALIDATION_2026-10-19.md)。此前 2214 文件、缺扩展的描述是初次装配版本的历史结果。
- 开发内容审计已为 `libgsas_core.so` 登记 `app-core` 归属；未签名 HAP 的内容检查通过，但设备拒绝调试签名 HAP（`9568257 / fail to verify pkcs7 file`），应用内精修、导出及生命周期仍待验。正式签名、最终 SBOM/许可和发布审计仍由 C 负责；本次合并不是技术放行。

以下 2026-10-19 条目记录各提交当时的状态；其中“未上真机”“缺 8 个扩展”不代表当前本地组装与 HiShell 补充验证的结论。

## Unreleased — 非真机收尾：strip/自签名、启动预检与 SBOM 草案（2026-10-19，成员 B，仅宿主验证）

- 新增 `scripts/ohos/Sign-NativeModules.ps1`：在宿主用 DevEco `llvm-strip`/`llvm-objcopy` 与 `binary-sign-tool.jar` 完成 strip 与自签名，等价于设备侧 `sign-native-modules.sh`。已处理 aarch64 `libgsas_core.so`（348 976 → 243 584 字节，新增 `.codesign`，ELF64/AArch64 与 `NEEDED` 不变）；自签名只适用于开发包，正式证书链仍由成员 C 负责。
- `CoreRuntime.initialize` 增加 GSAS-II 原生扩展预检：真实 refiner 缺模块时返回 `CORE_NOT_READY`（detail 列出缺失模块），不再等到首个任务以 `INTERNAL_ERROR` 失败；假核心跳过预检。新增 5 项测试（预检、跳过、包缺失、部分缺失）。
- 新增 `scripts/payload/make_sbom.py` 与 `packaging/sbom.draft.cdx.json`：从 `components.json` 生成 CycloneDX 1.5 草案（9 组件、含依赖关系；无文件哈希，`distributionReview` 保持 `pending`）。
- 文档一致性：`PHASE3_CORE_BRIDGE` §4 改为设备侧待验项；原生扩展统一为 8 个；`RELEASE_ACCEPTANCE` 的覆盖升级状态更正为“设计+宿主测试完成，设备待验”。

## Unreleased — 载荷原生扩展门禁与影响如实化（2026-10-19，成员 B，仅宿主验证）

- 新增 `scripts/payload/check_gsas_native.py`：发布载荷必须携带 8 个 GSAS-II 编译模块（`pyspg`、`pypowder`、`pytexture`、`fmask`、`histogram2d`、`pack_f`、`unpack_cbf`、`kvec_general`），验证 ELF64/AArch64/ET_DYN，并拒绝 `pydiffax`。缺模块时判为不合格；`--allow-missing` 仅用于开发载荷并打印 DEV-ONLY。新增 7 项合成载荷单元测试。
- 更正原生扩展的影响描述：缺少 `pyspg` 时 `GSASIIobj.SetNewPhase` 无法初始化 `P1SGData`，任何相文件（含 PbSO4 CIF）都无法导入，五阶段精修在设备上不可达；原"对称性/部分路径不可用"低估了影响。同步更新 `PHASE3_NAPI_CORE`、`RUNTIME_PACKAGING`、`DEPENDENCY_AUDIT`、`RELEASE_ACCEPTANCE`、`INTEGRATION_ALIGNMENT` 与 `scripts/payload/README.md`。
- 本机恢复 Windows 基线复跑环境后，`Run-BridgeSelfTest.ps1 -Python <gsas-poc> -DllDirectory D:\mingw64\bin` 23 项通过（2 项按环境跳过），真实 PbSO4 五阶段数值再次通过；设备侧证据仍为空。

## Unreleased — 运行时载荷装配与 aarch64 交叉编译（2026-10-19，成员 B，仅宿主验证）

- 新增 `scripts/payload/`：可复现装配配方与 9 组件清单（`components.json`），锁定 CPython 3.12.9 ohos-aarch64、NumPy 2.2.6、SciPy 1.16.3、PyCifRW 5.0.1、prettytable 3.18.0、wcwidth 0.9.2、ply 3.11、GSAS-II 2.0.0@`2b4aba1b`、bridge 1.1.0，并记录每个下载的 SHA-256。
- 载荷经 `Write-RuntimeManifest.py` 与 `Prepare-Runtime.py` 两级门禁：2214 个文件、约 178 MB，逐文件哈希与内容检查（AArch64 ELF、无归档/字节码/外平台库）通过，状态 `prepared-not-device-validated`。
- 发布裁剪配方：pydiffax 导入块等价替换、25 个 wx/G2shapes GUI 模块删除与 12 处函数内导入中性化，AST 复扫保证无残留；去除 `help/`、`install/`、静态库 `.a`、测试数据与 `.npz` ZIP 容器。
- 修复 `CMakeLists.txt` 在 OHOS 工具链下的库查找：`ohos.toolchain.cmake` 的 `CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY` 使 `find_library` 失效；改为校验并直接链接载荷中的 `libpython3.12.so`。
- 使用 DevEco OHOS 工具链与真实 CPython 3.12.9 头/库完成 `-DGSAS_HAS_PYTHON` aarch64 交叉编译与链接；产物为 ELF64 AArch64 ET_DYN，`NEEDED` 含 `libpython3.12.so`。
- 仍未关闭：设备 dlopen/`Py_Initialize`、HAP 内五阶段数值验收、`pyspg` 等原生扩展（缺 flang 20.1.0）、Sobol QMC（`.npz` 被发布门禁裁剪）。本次未构建 HAP、未上真机。

## Unreleased — B03 终态日志 artifact 与跨进程快照（2026-10-19，成员 B，仅宿主验证）

- `job.failed`/`job.cancelled` 终态载荷新增**可选** `artifacts` 数组（CORE_API v1.1 兼容新增）：仅携带登记返回的 `log` artifact，fileId 必须是登记令牌；Schema、示例、语义验证器、ArkTS 共享模型与门面、UI、测试七处同步。
- 门面按决议顺序"先持久化并登记脱敏日志、再发终态"；登记未完成时事件不携带 `artifacts`，页面提示"日志登记未完成"，不从路径、文件名或历史消息推导。
- 终态快照持久化到 `outputs/<jobId>/core/terminal-snapshot.json`，进程重启后 `getJobSnapshot` 在原生台账缺失时按 jobId 恢复并再校验形状；`PROCESS_INTERRUPTED` 合成快照补齐 `state` 字段；未知/已清理 ID 保持 `JOB_NOT_FOUND`，A 端仅对失效近期 ID 降级。
- 快照与已登记产物一致性纳入断言：交付事件、内存视图与磁盘快照的终态载荷同形（宿主桥测试与 Python 捕获脚本）。
- 修复嵌入层缺陷：`python_host.cpp` 的 `EmitCallback` 注册为 METH_O 却按元组解析参数，真实 CPython 经 §8 调用 `emit_event` 必然抛 TypeError（桩构建与纯 Python 测试均无法暴露）。
- 新增宿主嵌入冒烟 `tests/python-host-embed-smoke.cpp`（不进 CI，需本机 libpython 开发包）：真实嵌入解释器加载真实 bridge 包并跑任务到唯一 `CORE_NOT_READY` 终态，事件跨越 C capsule 边界；已在 x86_64 验证，非 OHOS aarch64 证据。
- 新增运行时依赖：无。真实 CPython/GSAS-II 载荷、OHOS aarch64 上启用 `GSAS_HAS_PYTHON` 的编译/加载与真机证据仍未关闭；本次未构建 HAP。

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

