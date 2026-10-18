# ArkUI、核心与文件服务接入对齐清单

更新日期：2026-10-19。面向成员 A（界面）、B（核心）、C（文件服务与打包）及组长/集成负责人。

当前正式应用基线包含成员 A 的 ArkUI 页面、成员 C 的文件服务，以及成员 B 在 GitHub PR #4 交付的 C++ N-API、CoreService 和运行时安装器。本文同时记录已经完成的组长审核和后续仍需关闭的事项；**仅第 6 节确认记录中的结论视为团队决议，其余说明不修改或取代冻结的 [CORE_API v1.0](CORE_API.md)**。当前仓库没有真实 CPython/GSAS-II 载荷，应用内真实计算、真机 GUI 和发布验收仍未完成。

## C01/C02 交付状态（2026-10-17）

成员 C 在 `release/stages-1-2` 交付正式 `app/` 工程和真实 FileService，实现提交 `3d6957d`；运行时装配和 HAP 审计工具随后由 `release/runtime-tooling` 交付。两个 PR 均已由组长审核并合入 `main`（主线合并提交 `97206f1`、`4be5488`）。包名调整及 Windows 重建证据由主线后续提交 `85f23b0`、`a4c2f8c` 完成，成员 C 无需因此重新提交或返工。[成员 C 交接](MEMBER_C_HANDOFF.md)继续作为 A/B 接入说明；PR 合并不等同于真实核心、真机和上架验收通过。

| 事项 | C 已交付的实现 | 剩余接入/确认及负责人 |
|---|---|---|
| A01 工程入口 | `app/entry`、EntryAbility、`pages/Index`，公共文件类型在 `contracts/Files.ets` | C 的工程入口已随 PR 审核合入；A 的正式页面已按阶段性开发增量通过组长审核，`ui-mock/` 暂保留为演示与测试且不进入正式 HAP |
| A02 工具链与应用 | 开发包 `com.gsasii.desktop`、0.1.0，最低20/目标24；Windows Command Line Tools 26.0.0.851/SDK 26.0.0.105 的 Release 构建及 HAP 内容审计已通过 | bundleName 和当前 Windows 开发构建基线已由组长确认；C 按原分工完成真机签名及 API20/24 兼容验证，上架显示名与验收系统仍待最终确认 |
| A03 初始化 | Ability 预热文件服务；AppServices 提供进程期 FileService/CoreService 单例；运行时安装后初始化核心 | 代码级有条件通过；真实载荷/设备初始化未验，核心失败后缺少独立的用户重试入口 |
| A04 类型 | FileRole、AppFile、FileServiceError、CoreConfig、JobSnapshot、终态摘要和 CoreError 已有 ArkTS 实现 | 代码与冻结契约对照通过；后续字段变更仍须走 CORE_API §12 |
| A05 文件选择 | FilePickerService；导入取消返回 undefined，导出取消返回 false；三种输入角色；核心侧校验五文件格式/组合 | 归属及语义通过，模拟器已有选择器证据；真实集成包和真机仍待验 |
| A06 jobId | 页面生成 UUID；先订阅再启动；原生门保存进程期唯一性并拒绝并发任务 | 代码和宿主并发测试通过；设备时序仍列入正式验收 |
| A07 文件与产物 | 门面解析输入、锁定租约，completed 前登记真实产物，终态后释放 | 代码边界通过；B03 可发现性已在增量 PR `core/b03-terminal-artifacts` 完成宿主级实现（待组长复核）；真实 GPX/JSON/日志调用链仍待关闭 |
| B01 输入生命周期 | beginJob 固定启动时输入并持久化引用，活动引用拒绝删除；所有终态释放租约 | 代码级通过；真机任务期间删除及异常退出仍待验 |
| B02 导出交互 | 系统保存选择器、真实写入、同名确认取消保留原文件；取消与失败分开反馈 | 代码级通过；真实计算产物导出仍待验 |
| B03 日志 | 失败/取消先写脱敏日志并登记为 log，再发终态；终态事件携带登记返回的 artifact/fileId | 增量 PR `core/b03-terminal-artifacts` 已按第 6 节决议同步契约、Schema、示例、验证器、ArkTS 类型、门面、UI 与测试（仅宿主验证，待组长复核）；登记未完成时事件不带 `artifacts`，页面如实提示，不推导 fileId；真机与真实载荷仍待关闭 |
| B04/B05 重启与终态 | 进程期服务、活动/最近 jobId、快照回放、唯一终态、取消 ACK、PROCESS_INTERRUPTED 均已实现；终态快照另持久化到 `outputs/<jobId>/core/` 供进程重启后按 jobId 恢复 | 代码和宿主测试通过（含跨进程恢复与登记产物一致性断言，仅宿主验证）；设备上的页面重建、退出与进程重启仍待验 |

A 的会话接入准备始于 `docs/github-integration-readiness@27dce33`，随后正式页面和 B 的 N-API/CoreService 在 GitHub PR #4 合流。审核基线为 `main@fb4be23`，其中 `abcdf56` 修复终态快照保留和进程期 jobId 唯一性；[GitHub Actions #39143702485](https://github.com/xiaotaop/ohos_gsas-ii/actions/runs/39143702485) 成功。这里的“通过”限定为源码、契约和宿主测试，不把桩构建当作应用内真实计算。

后续顺序：B/C 装配真实运行时载荷并完成带 `GSAS_HAS_PYTHON` 的构建 → B/A 按 B03 决议公开失败/取消日志 artifact（增量 PR `core/b03-terminal-artifacts` 已完成宿主级实现并附跨进程快照恢复，待组长复核后进入下一环节）→ A 补核心初始化失败的明确重试入口 → 以同一正式集成包完成本文件第 5 节验收 → C 完成签名、载荷许可/SBOM和上架材料 → 组长冻结发布候选。运行时许可审计和发布材料可并行准备。

### 本分支正式 app 输入准备（2026-10-18）

- `app/entry/src/main/ets/pages/Index.ets` 使用 C 的 `AppServices.files` 和 `FilePickerService`，提供 X 射线数据/仪器参数、中子数据/仪器参数、CIF 相文件五个明确槽位。可选择文件库已有文件或导入并关联；不根据文件名猜测 X 射线/中子用途，显示文件名及 SHA-256 前缀。
- `model/RefinementInputs.ets` 只保存槽位和 fileId，Preferences 持久化页面关联。重选保留旧文件，取消选择保留原关联；删除或重启恢复时移除失效关联，不替代 C 的文件目录与活动任务租约。保存失败明确提示关联尚未持久化。
- “校验五份输入”逐个调用真实 `getFile` 校验存在性与哈希，按冻结请求的 inputs 形状准备两组 histogram 和 phase。该类型是 A 的局部投影，后续替换为 B 的共享类型；`GSAS powder` 是当前准备范围，phase 名称为占位值，不代表解析了 CIF。未解析科学格式，也未决定 cycleCount 默认值；开始精修保持禁用。
- 新增 `tests/input-selection.test.cjs`：5 项通过，覆盖明确关联、重选/删除、持久化记录损坏、文件校验错误及异步校验期间输入固定；已加入现有 CI。使用本机 DevEco Studio 自带 SDK API24 完成 ArkTS 编译及 ARM64 unsigned HAP 构建，开发包内容审计通过（20 个条目）。这是本次增量验证，不替代第 6 节已确认的另一套 CLI/SDK 构建基线。
- HarmonyOS PC 6.1.1/API24 x86_64 模拟器已验证：从文件库选择五份输入，显示“两组粉末数据、仪器参数和一份相文件”完整性校验成功；打开系统选择器后取消，显示原关联保留；强制停止并重启应用后恢复全部五个关联，再次校验成功。模拟器包由忽略目录中的工程副本临时切换 ABI 构建，正式工程 ABI 未改。测试文件来自仓库的五份公开 PbSO4 样例，经临时副本调用真实 FileService 导入沙箱，随后重装无导入钩子的干净包再验证页面；不把这种样例准备记作系统选择器导入成功。

#### CI 与系统选择器补充验证（2026-10-18）

- 提交 `43a0375552e989a0d0a4d8ecd30377343daf870f` 的 [GitHub Actions #39117201329](https://github.com/xiaotaop/ohos_gsas-ii/actions/runs/39117201329) 已完成且结论为 `success`，Repository verification 全部步骤通过，包含新增输入模型测试所在的文件服务步骤及原有 Bridge、打包工具、原生文件、ArkUI mock 检查。
- 在同一 HarmonyOS PC 6.1.1/API24 x86_64 模拟器、干净应用包上完成系统选择器实际导入。包 SHA-256：`263CE42F56E85F1088C51F9F56C48E42278ED6E0A7CCA110AB0428DE03D55870`；本轮未改应用代码或重建包。
- 复现步骤：将文件库中五份公开样例分别通过“导出副本”及系统保存选择器写入“文档”；依次点击五个槽位的“导入并关联”，通过系统打开选择器选入 `PBSO4.XRA`、`INST_XRY.PRM`、`PBSO4.CWN`、`inst_d1a.prm`、`PbSO4-Wyckoff.cif`。粉末数据、仪器参数、相文件筛选均能显示对应样例，包括大写扩展名。导入经过系统返回的 URI 和真实 FileService 复制/登记流程，不使用临时导入钩子。
- 结果：最后一个槽位显示 CIF 关联成功；强制停止并重启后显示“已恢复 10 个文件”（原有五份与本次五份副本），五个输入关联全部恢复；再次点击“校验五份输入”，两组数据/仪器参数和相文件的存在性与完整性检查成功。显示的文件名与哈希前缀对应 [测试样例基准](TEST_PLAN.md)。这同时验证公开输入副本的保存及重新导入，不代表 GPX/JSON/日志等计算产物导出已验收。

证据：[CIF 系统选择器](evidence/a-input-picker-cif-2026-10-18.jpeg)、[重启后五份输入校验成功](evidence/a-input-picker-verified-2026-10-18.jpeg)。截图仅含模拟器画面。

上述记录对应五槽位输入准备版本。后续桌面布局见下一节；M1 的任务状态和 `RefinementSession` 仍待真实核心接入。系统选择器实际导入已通过模拟器验证；真实计算、任务租约调用、计算产物导出、真机 GUI 和签名验收仍待执行。

### 原版完整界面目标：第一批桌面布局（2026-10-18）

用户已确认按完整主窗口、菜单、参数面板及弹窗的目标分批推进，尽量保持原版布局、术语和操作路径。实现以锁定上游 `2b4aba1bc44de63a3da9d4495944c3b99e389399` 的 `GSASIIdataGUI.py` / `GSASIIctrlGUI.py` 为依据。本节记录 A 分支进展，不改变冻结核心接口，也不表示完整 GUI 已完成。

- 正式 `app/entry` 采用 File / Data / Calculate / Import / Export / Help 菜单、Loaded Data 数据树、右侧页面和双区状态栏。使用紧凑控件、白色数据树与灰色参数区；公共根节点及粉末子节点按原版顺序组织。
- 树节点来自真实输入关联；Phases 下暂用 CIF 文件名，PWDR 下显示实际数据文件名。它们尚不是解析完成的科学对象。Refinement Controls 保留参数区组织，但未接通的参数、计算和工程导出均禁用，不填入模拟值。
- Import → Phase → from CIF file 调用真实相文件选择器；Powder Data → from GSAS powder file 先区分 X 射线/中子用途，再调用系统选择器。五槽位关联在 Loaded Data 页集中管理，仪器关联也可从相应 Instrument Parameters 节点进入。File → Imported files 保留真实文件库功能，并增加删除副本前的确认弹窗。
- 修复模拟器发现的三处布局问题：分栏剩余宽度计算导致树被挤压、最大化后参数页不扩展、展开箭头被按钮内边距遮挡。使用普通 Row 分配剩余空间与受限拖动分隔栏，窗口变化时同步约束树宽；不依赖 RowSplit 缓存的子项宽度。

验证：正式 ARM64 和隔离 x86_64 模拟器包均完成 ArkTS/HAP 构建。模拟器保留原数据升级安装，恢复 10 个文件和五份关联，实际文件完整性校验通过；验证常规窗口/最大化重排、分隔栏拖动、粉末树折叠、中子 Instrument Parameters 页面。粉末菜单可进入系统选择器，取消保留原关联；CIF 菜单完成一次实际导入及关联，File → Imported files 显示文件名、大小、哈希与导出/删除入口。文件库导出能力沿用前一节证据，本轮未重新执行导出或删除。

- ARM64 未签名调试包 SHA-256：`FF5FB46F08E12115C8D42B1D1C0B166110068B300E7E072D6B64D669B094C0D0`。
- x86_64 未签名模拟器包 SHA-256：`352C3796774F4A0A8A555A7129866B9EF6D6128EE8B0B029224BB756B606586A`。模拟器专用 ABI 修改仅存在隔离构建目录；正式工程未改 ABI，未加入导入钩子。
- 截图：[Controls 与数据树](evidence/a-desktop-controls-2026-10-18.jpeg)、[正式文件库](evidence/a-desktop-files-2026-10-18.jpeg)，仅含模拟器画面。

后续批次仍需实现：动态/上下文菜单及快捷键、各参数编辑器和科学文件解析、工程打开/保存及对话框、原版独立绘图窗口、真实任务进度与结果。第一批菜单仍有禁用项，About 采用页内展示，粉末用途选择是当前双数据集契约的适配；不宣称逐像素或完整操作等价。当前验证不覆盖完整键盘导航、任意极窄窗口、真机或 API20，也不替代真实计算及发布签名验收。

### 成员 A 开发交接（2026-10-18，跳过设备验证）

本轮按用户授权，以组长冻结的 CORE_API v1.0 五阶段 MVP 和 `RELEASE_ACCEPTANCE.md` 的 A 端责任优先推进。完整原版 GUI 继续作为后续目标；此次不把高级科学编辑器、GPX 工程读写或独立绘图窗口记为已完成，也不把本轮优先级决定写成组长批准的接口变更。

**状态：A 可独立推进的 MVP 页面与会话代码已按阶段性开发增量通过组长审核；真实服务接入、跨成员确认及发布验收未完成，个人任务尚未整体结项。** 审核时 `main=b188667`、`core/python-bridge=a3d197e`，未发现新的应用内 CoreService。

| 本轮交付 | 实现与边界 |
|---|---|
| 正式任务页 | Calculate → Refine 或 Ctrl+R；明确填写相名、0～50 整数 cycles、无路径的 `.gpx` 输出名，无示例默认值。当前 B recipe 只支持已验证 PbSO4 五文件组合。开始前通过真实 FileService 再校验输入，固定请求副本；参数草稿不会自动变成计算请求 |
| 正式会话 | `app/entry/src/main/ets/model/Refinement.ets`：先订阅后启动、取消 ACK 非终态、迟到响应/过期快照保护、页面退订不取消后台任务。快照只恢复摘要，不伪造历史消息；Promise 错误保留已知错误码并使用安全文本 |
| 任务与结果组件 | `components/RefinementPanel.ets`：队列/进度/三种终态、错误、五阶段 Rwp、择优取向、基线校验摘要；结果返回的 artifact.fileId 经 C 的真实保存选择器与文件服务导出，取消明确反馈。页面不捏造产物或日志 ID |
| 生命周期与键鼠 | 在 Index 切换数据树时任务组件保持挂载；输入检查/活动任务期间禁止输入重选、删除和文件自测。File → Exit、返回及系统标题栏关闭回调提示未完成操作。F1 提供版本、快捷键和操作帮助；设备端行为本轮未验 |
| 参数草稿 | Controls、Limits、Background、Instrument Parameters、Sample Parameters 的对话框编辑、校验、保存、取消及恢复。字段/分支依据锁定上游；空白表示未设置，不假装已解析科学文件。CW/TOF 需用户明确选择模板。未接入的高级背景、排除区间等保持说明状态 |
| 草稿可靠性 | 切换模板保留隐藏字段；保存仅含 key/value/refine 与范围身份，不保存描述符。使用 70 字符 SHA-256 键满足 Preferences 的 80 字符限制，紧凑值及长度检查满足 8192 字符上限；记录内仍验证完整 scope。异步读取、保存和组件卸载通过代次检查隔离 |

#### 已接入结果与剩余责任

1. **已接入**：`Index.ets` 通过 AppServices 获取进程期 FileService/CoreService，在核心就绪后向 `RefinementPanel` 注入服务和持久化的活动/最近 jobId；正式组件不会回退到 mock。
2. **已确认**：页面生成 UUID jobId，先订阅再启动；正式共享 Snapshot/CoreError 类型、进程期唯一性和 B06 的 MVP 参数范围均按第 6 节结论执行。
3. **宿主级已完成、待复核**：按 B03 决议给失败/取消终态增加可选 `artifacts`，只返回已经登记且可导出的日志 fileId，并让页面展示/导出。不能从历史消息、文件名或 private traceback 推导日志。该增量（含跨进程终态快照恢复与 JOB_NOT_FOUND 失效降级）已在 PR 分支 `core/b03-terminal-artifacts` 实现并通过宿主测试；未经真机复核前不视为关闭。
4. **待 A 实现**：核心初始化失败时提供独立、可见的重试入口；随后在真实运行时上验证开始、取消、结果和三类终态日志导出。`ui-mock/` 暂保留为测试/演示源码，不进入正式 HAP。
5. **待 B/C/A/组长验收**：装配真实运行时并执行签名、运行时/许可审计、API20/24 兼容、真机窗口/快捷键/关闭提示及同版本真实截图。已有开发图标继续复用，最终显示名与发布素材按发布清单确认。

#### 无设备验证与复现

- 输入关联套件 5 项通过；参数草稿套件 10 项通过；正式模型契约/会话/宿主回放套件 18 项通过（复用原 14 项，含测试专用 mock 服务，再增加正式请求、错误与快照历史检查）。宿主捕获使用 `LocalCoreService + FakeFiveStageRefiner`，不代表真实数值计算。
- 正式 ARM64 工程通过本机 DevEco Studio SDK API24 / 6.1.1.125、Hvigor 6.24.4 的 ArkTS 编译与 unsigned debug HAP 构建；开发内容审计通过（20 个条目）。HAP SHA-256：`a3571197c4cb83d9aa8bf86285238554ea1ca4241fd9de28a08767c6d934dd8f`。构建记录、源码指纹、包内容清单及日志保存在本地忽略目录 `app/build/deliverables/a-ui-20261018/`。SDK 构建告警仍包含原文件服务 API 异常处理提示和未配置签名，未隐藏或削弱检查。
- 本轮不会重用上一版模拟器截图证明新版页面正确；对话框布局、真实 Preferences 写入/重启、快捷键和系统关闭拦截仍待设备验收。云端 CI 与本地检查分开记录。

```powershell
$env:GSAS_TYPESCRIPT_PATH = 'E:\Apps\DevEco\DevEco Studio\sdk\default\openharmony\ets\build-tools\ets-loader\node_modules\typescript'
$env:TEMP = Join-Path (Get-Location) 'app/build'
$env:TMP = $env:TEMP
# 首次复现先编译 ui-mock 的测试服务；不会启动演示应用。
powershell -NoProfile -File scripts/Test-UiMock.ps1 -DevEcoHome 'E:\Apps\DevEco\DevEco Studio'
node --test tests/input-selection.test.cjs tests/parameter-drafts.test.cjs tests/formal-refinement.test.cjs
```

HAP 使用本机 DevEco SDK/Hvigor 构建，产物与构建日志位于忽略的 `app/build/` 和 `app/entry/build/`；当前开发 HAP 无真实 Python/GSAS-II 运行时，不能作为上架候选。提交发布还需按[华为官方发布入口](https://developer.huawei.com/consumer/cn/app/submit)及项目发布清单完成 APP 打包、正式签名和审核，开发 HAP 构建不替代这些步骤。

#### 云端 CI 确认与合并建议（2026-10-18）

- 应用实现提交 `dc54357aad89ffc1482c2931f3bfa511ad8b0d1f` 的 [GitHub Actions #39126417543](https://github.com/xiaotaop/ohos_gsas-ii/actions/runs/39126417543) 已完成，结论为 `success`；Repository verification 于北京时间 **2026-10-18 20:14:12** 完成。核对依据为 Actions 返回的提交 SHA、作业及各步骤状态。
- 全部步骤通过，覆盖 Python 语法、JSON、冻结契约、样例完整性、Python Bridge、运行时装配/HAP 审计工具、原生排他文件创建、宿主 FileService、输入关联与参数草稿，以及 ArkUI mock/正式会话模型。流水线未执行 DevEco HAP 构建、真实科学计算、模拟器或真机验收；本地 HAP 的独立证据见上节。
- 本分支相对 `main@b188667` 的主要行为边界已完成代码审查，未发现阻止作为 **A 端开发增量** 合入的明确代码问题。组长已确认 A01 正式页面接入、本阶段保持真实计算禁用及暂时保留 `ui-mock/`；该结论不关闭尚待确认的跨层事项。
- B 的真实 CoreService、应用初始化与任务 ID 恢复、共享快照/错误类型及产物/日志发现方案仍是 **真实联调与发布的前置条件**，不应把 CI 通过解读为这些依赖已交付。当前不注入服务、开始精修禁用，允许组长将页面准备作为独立增量评审；若按“完整精修功能交付”验收，本分支尚不可据此结项或发布。

#### 等待 B 期间的本地记录与文件管理（2026-10-18）

- 正式数据树的 **Notebook** 和粉末 **Comments** 已接入现有草稿编辑/持久化组件，支持多行记录、保存、取消、恢复及复制文本。Notebook 是应用本地笔记，更换输入仍保留；Comments 按粉末文件 `fileId` 保存，不受仪器参数/CIF 重选影响。同一文件换回后恢复备注，同名的新导入副本使用独立备注。没有粉末关联时不允许写入无主备注。
- 这些是用户手写的本地记录，不冒充已解析的原文件注释，也不写入 GPX 或精修请求。文本最多 4096 字符，序列化记录继续受 Preferences 总长度门禁约束；旧科学参数草稿的 scope 与格式不变。编辑器新增 Clear form，仅清空待保存表单，Cancel 保留原已保存草稿。
- 文件库新增按文件名、fileId 或 SHA-256 的不区分大小写搜索、六种文件角色筛选、匹配数量及空结果提示；清除筛选可恢复完整列表。fileId 和哈希支持复制。筛选只改变显示，导出/删除仍以真实 fileId 调用 C 的服务，并保留活动任务保护。
- 验证：输入关联/记录归属 **6 项**、草稿模型 **12 项**全部通过，包含多行/空白原样恢复、文件身份隔离、原草稿键兼容、长度与非法 Refine 标记拒绝。正式 ARM64 unsigned debug HAP 的 ArkTS 编译、构建和开发内容审计通过（20 条）；未新增模拟器或真机验证，界面交互与设备存储仍待实测。
- 本轮 HAP SHA-256：`4a6abb09831d2207a1c95d5974721a9806f99f40e5945f46eb64ef2c7fe39237`。源码指纹、构建记录、包、清单与日志留存在本地忽略目录 `app/build/deliverables/a-local-notes-20261018/`。使用上一节相同 SDK/Hvigor，保留既有文件服务异常处理及未签名告警。真实核心、日志发现和完整原版 GUI 的依赖不因本增量完成而关闭。

### 本分支 M1 会话接入准备（历史基线）

- `ui-mock/` 中 `Refinement.ts` 的 `RefinementSession` 接收已就绪的 CoreService，负责先订阅再启动、取消等待和页面退订；M1 的 `Index.ets` 已使用它。页面销毁只让会话退订，真实服务由应用持有；演示页面仍单独释放自己创建的 mock。
- `connect(knownJobId)` 先订阅后读取快照，恢复进度和成功/失败/取消摘要。旧快照、旧任务事件、退订后返回的 Promise 不覆盖当前页面；迟到的启动/取消响应不覆盖终态或新任务。`connect()` 用于开始一个空闲页面，`disconnect()` 不取消核心任务。
- 快照恢复支持 B 当前字段、初始 `lastSequence: -1` / `stage: null`。成功终态在 UI 显示 100%，不要求 B 的原始快照也写成 100%；不伪造 eventId、timestamp 或持久化记录。恢复不重建快照未提供的历史日志。
- `tests/capture_bridge_ui.py` 在临时测试沙箱实际运行 B 的 LocalCoreService + FakeFiveStageRefiner，捕获成功、异常、取消事件和快照，再由 `tests/ui-mock.test.cjs` 驱动 A 的状态/会话代码比较结果。捕获前执行已有契约语义校验，结束清理测试产物。它只用于离线测试，不是供页面调用的 Python 通信层。
- B 假核心采用 `TEST_PLAN.md` 的最终 X 射线 Rwp 基线 `13.16483`；原 M1 示例约为 `13.1646`。两者分别按各自来源检查，不改动冻结示例，也不将假核心数字当作新科学计算结果。

正式工程取得服务后，A 的接入顺序为：创建 `RefinementSession(readyCore, refreshUI)` → `connect()` 或 `connect(knownJobId)` → `start(request)` / `cancel()` → 页面离开时 `disconnect()`。服务初始化、已知任务 ID 的来源、进程重启后的任务记录由 B/C 提供，不由页面猜测。

## 1. 已确定的接口边界

以下规则来自冻结契约，可以直接作为各成员实现的共同前提。

| 接口/行为 | 已确定的约定 | 来源 |
|---|---|---|
| `CoreService.initialize(config)` | C 提供沙箱中的运行时、任务和输出根目录；配置不由普通页面构造。初始化幂等，配置变化返回 `CORE_ALREADY_INITIALIZED` | CORE_API §3 |
| `CoreService.startRefinement(request)` | 单任务；请求使用 `fileId`，当前 recipe 为 `powder-five-stage-v1`。返回 `JobAccepted` 只表示进入队列 | CORE_API §3、§5 |
| `CoreService.onEvent(listener)` | 页面先订阅再启动；返回取消订阅函数。事件序号递增，每个任务只有一个终态，终态后不再发事件 | CORE_API §3、§6 |
| `CoreService.cancelJob(jobId)` | 阶段边界协作式取消；`CancelAck` 不是终态，还需等待取消、失败或成功事件 | CORE_API §3、§10 |
| `CoreService.getJobSnapshot(jobId)` | 返回最近状态、序号、进度、阶段和终态摘要；重启后未完成任务标记为 `PROCESS_INTERRUPTED`，不自动恢复精修 | CORE_API §7 |
| `FileService.importFile(sourceUri, role)` | 系统选择后复制到应用沙箱，返回 `AppFile`。UI 只把 `fileId` 交给核心，不传 URI 或绝对路径 | CORE_API §4 |
| `FileService.getFile / deleteFile / exportFile` | 按 `fileId` 管理文件；默认不覆盖同名导出。成功保留 GPX、JSON、日志；失败/取消保留日志 | CORE_API §4、§11 |
| 错误和后台任务 | 用户错误含 `code/message/retryable`，可选 `detail`；不展示 traceback。后台化继续计算，主动退出时有未完成任务需提示 | CORE_API §9、§10 |

完整签名、字段及错误码以 `CORE_API.md`、`contracts/*.schema.json` 为准；本文不复制一套独立类型定义。

## 2. 组长接入审核状态

组长不负责代替成员实现下列功能。以下结论依据 PR #4 合并后的主线作出；“代码级通过”表示归属、时序和冻结契约一致，仍需第 5 节在同一真实集成包上取得正式证据。

| 编号 | 成员提交后由组长审核的结论 | 提交前置/牵头 | 当前状态 |
|---|---|---|---|
| A01 | A 的正式页面是否正确进入 `app/entry`，公共类型和服务导入路径是否唯一；页面迁移稳定后决定保留或移除 `ui-mock/` | A 提交页面迁移 PR，C 仅协助工程问题 | 正式页面已按开发增量审核通过；真实计算保持禁用，`ui-mock/` 暂保留且不进入正式 HAP |
| A02 | 上架显示名、真机验收系统版本、签名流程和 API20/24 兼容证据是否满足发布要求 | C 按原分工提交真机/签名记录 | bundleName 与 Windows 开发构建基线已确认；其余待审核 |
| A03 | 初始化责任、CoreService/FileService 就绪时机及失败重试是否形成单一实现入口 | B/C 提交服务装配实现，A 提交消费方式 | **有条件通过**：单例及初始化顺序已统一；缺真实载荷/设备证据，且核心失败后应增加独立重试入口 |
| A04 | FileRole、JobSnapshot、终态摘要和 Promise 错误结构是否完整，公共类型由谁维护 | B/C 提交类型对照和必要的契约变更 | **代码级通过**：共享 ArkTS 类型和错误映射已接入；契约字段变更仍走 §12 |
| A05 | 选择器归属、取消/失败语义、三个输入角色及允许格式是否一致 | A/B/C 提交五份输入文件的实际调用示例 | **有条件通过**：选择器/角色/取消语义及科学格式检查已实现；真实集成包和真机待验 |
| A06 | jobId 由哪一层生成，Promise 返回与首个事件的时序是否不会丢事件 | B/A 提交时序说明和并发测试 | **代码级通过**：UI 生成 UUID，先订阅后启动，门面/原生层保持进程期唯一性并拒绝并发 |
| A07 | 输入 fileId 解析、GPX/JSON/日志登记及 fileId 回传归属是否明确 | B/C 提交一个真实任务的调用链和产物证据 | **有条件通过**：调用边界和 completed 前登记已实现；真实载荷证据及 B03 尚未关闭 |

M1 临时值仅供比对：`ui-mock/`、`pages/Index`、`com.example.gsas.uimock`、目标 API24/最低 API20。正式工程为 `app/`、`pages/Index`、`com.gsasii.desktop`、相同兼容/目标 API 范围；正式 HAP 不包含 `ui-mock/`。跨层选择以正式 `app/` 类型、冻结契约和第 6 节记录为准。

## 3. 行为差异审核状态

下列事项已完成代码复核；其中标为“代码级通过”的项目还必须经过同一真实集成包的设备验收才能计入发布完成。

| 编号 | 审核结论 | 牵头/协作 | 当前状态 |
|---|---|---|---|
| B01 | 重选保留旧副本；任务请求固定启动时 fileId；租约期间删除返回 BUSY；所有终态/调度失败释放租约，保留日志与输出 | C、B、A | **代码级通过**；真机活动任务删除和异常退出待验 |
| B02 | UI 选择目标 URI；默认不覆盖；用户取消返回 false 并与异常分开反馈；只导出已登记 fileId | C、A | **代码级通过**；真实计算产物待验 |
| B03 | 失败/取消必须先登记脱敏日志；终态载荷应增加可选 `artifacts` 数组并返回登记后的 log artifact/fileId，UI 不得按路径、文件名或历史列表猜测 | B、C、A；组长批准契约方向 | **宿主级增量完成、待组长复核**：PR 分支 `core/b03-terminal-artifacts` 已同步契约/Schema/示例/验证器/ArkTS 类型/门面/UI/测试，并新增跨进程终态快照与登记产物一致性证据；登记未完成时事件不携带 `artifacts`、页面如实提示；真实载荷与真机证据仍未关闭 |
| B04 | AppServices 持有进程期服务；持久化活动/最近 jobId；页面先订阅再取快照并拒绝旧序号；进程重启合成 PROCESS_INTERRUPTED | B、C、A | **代码级通过**；设备页面销毁/重启待验 |
| B05 | 取消 ACK 不是终态；自然完成与取消竞争只接受一个终态；活动任务退出提示；重启不恢复旧计算 | B、A、C | **代码级通过**；设备系统关闭路径和真实竞态待验 |
| B06 | MVP 仅开放相名、0～50 的 cycleCount 和无路径 `.gpx` 项目名；不提供统一默认 cycles；其余参数草稿不进入请求 | A、B；组长确认范围 | **代码级通过**；真实核心输入校验待验 |

`job.log` 是可展示的事件消息，不能自动替代可导出的日志文件。绘图曲线、协方差、晶胞/原子编辑和完整原版 GUI 不属于本轮已冻结接口；如需开放，应另行确认范围及数据结构。

## 4. 各成员剩余交付

| 成员 | 最小交接内容 |
|---|---|
| A | 增加核心失败重试入口；在同一真实集成包复核 B03 失败/取消日志 artifact 的展示与导出（宿主级实现已随增量 PR 完成，待复核）；补齐窗口、键鼠、退出提示、三终态和真实截图证据 |
| B | 提供可分发的 OHOS CPython/GSAS-II 运行时及来源/许可/构建清单；完成 aarch64 `GSAS_HAS_PYTHON` 构建（嵌入 §8 通道已在宿主 x86_64 完成真实解释器加载冒烟并修复其间发现的 emit capsule 缺陷，aarch64 仍待载荷）；B03 契约/Schema/示例/验证器和门面终态 artifact 及跨进程快照恢复已按决议完成宿主级实现（增量 PR，待复核），仍需提供真实计算与竞态证据 |
| C | 装配并审计真实载荷；完成正式签名、API20/24 兼容、真机安装/升级、最终 SBOM/许可及上架申请材料；与 B 核对原生依赖来源 |
| 组长/集成负责人 | 复核 A03/B03 增量，确定 A02 的验收设备/API/显示名，见证数值和生命周期验收，审核发布候选并签署技术放行；不代替 A/B/C 完成各自实现 |

优先关闭“真实运行时装包 → 一个真实 PbSO4 任务 → 登记并导出全部产物”的最小流程。A03/B03 可与运行时装配并行开发；上架提交必须等待同一发布候选完成签名、许可、真机和组长技术放行。

## 5. 集成验收勾选表

以下均为 **待执行的正式集成验收**，不能以已有 mock 通过记录代替。

- [ ] 系统选择器导入数据、仪器参数和相文件，得到真实 AppFile/fileId；取消选择不被当作文件错误。
- [ ] 未就绪、未知 fileId、非法仪器参数及第二个并发任务分别产生可识别反馈，UI 不崩溃、不显示 traceback。
- [ ] 先订阅再启动，首个事件不丢失，序号递增、进度不倒退且只有一个终态。
- [ ] 真机 PbSO4 五阶段结果满足既有 PoC 容差；成功结果和产物与实际文件对应。
- [ ] 取消经过等待后收到终态；再次启动不残留旧结果；自然完成与取消竞争时不产生两个终态。
- [ ] 成功的 GPX、JSON、日志均可导出；失败/取消日志可找到并导出；同名文件不被默认覆盖。
- [ ] 活动任务的文件重选/删除符合确认后的策略；后台、页面重建和重启中断记录按约定处理。
- [ ] 正式工程的真机窗口缩放、鼠标滚动、Tab/快捷键及退出提示通过。

## 6. 确认记录与合并流程

确认后在本表按事项编号补充结论，并附对应提交或合并请求；未填写前保持待确认。若结论涉及契约字段，须按 `CORE_API.md` §12 同步更新相关 Schema、示例和校验脚本，经集成负责人批准后生效。

| 事项编号 | 确认结论 | 确认人/日期 | 实现或契约提交 |
|---|---|---|---|
| C01/C02 交付 PR | 正式工程、FileService、运行时装配和 HAP 审计工具已完成代码审核并合入主线；这不代表真实核心、真机或上架验收通过 | 组长 / 2026-10-17 | `97206f1`、`4be5488` |
| A02（bundleName） | 开发包名统一为 `com.gsasii.desktop`，与个人 GitHub 账号解耦；正式签名及提交上架后原则上不再变更 | 组长 / 2026-10-17 | `85f23b0` |
| A02（Windows 开发构建基线） | 接受 DevEco CLI 1.3.5、Command Line Tools 26.0.0.851、SDK 26.0.0.105 作为当前 Windows 开发构建基线；现有 HAP 内容审计证据有效，但不等同于签名、真机或发布候选批准 | 组长 / 2026-10-17 | `a4c2f8c` |
| A01（正式页面开发增量） | 接受正式 `app/entry` 的输入、参数草稿、任务与会话页面作为阶段性开发增量；B 的真实 CoreService 接入前精修保持禁用；`ui-mock/` 暂保留为演示与测试且不进入正式 HAP。本结论不代表真实联调、设备或发布验收通过 | 组长 / 2026-10-18 | GitHub PR #3 |
| A03（服务初始化） | 接受 AppServices 进程期单例、文件服务先就绪、运行时安装后初始化核心的单一入口；当前仅有桩构建，且核心失败后没有独立重试入口，因此有条件通过而不关闭正式验收 | 组长 / 2026-10-19 | GitHub PR #4、`fb4be23` |
| A04（共享类型） | JobSnapshot、终态摘要、CoreError 和 Promise 错误映射与冻结契约一致，正式 app 使用同一组 ArkTS 类型；后续字段变更须同步 Schema/示例/验证器 | 组长 / 2026-10-19 | GitHub PR #4 |
| A05（选择与格式） | 接受 FilePickerService 的归属、取消/失败语义、三类角色及核心侧五文件格式/组合校验；真实集成包和真机证据仍是关闭条件 | 组长 / 2026-10-19 | GitHub PR #3、#4 |
| A06（jobId 与时序） | jobId 由页面生成 UUID；页面先订阅再启动；门面和原生层拒绝并发并保持进程期 jobId 唯一，终态后仍保留快照 | 组长 / 2026-10-19 | GitHub PR #4、`abcdf56` |
| A07（文件与产物边界） | 接受 acquire → beginJob → native start，以及 completed 前 registerOutput、终态后释放租约的调用边界；真实载荷调用链和 B03 可发现性未验 | 组长 / 2026-10-19 | GitHub PR #4 |
| B01/B02（文件生命周期与导出） | 接受启动时输入快照、活动租约拒绝删除、终态释放、默认不覆盖及取消/失败分开反馈；真实任务和产物仍需设备验收 | 组长 / 2026-10-19 | GitHub PR #4 |
| B03（失败/取消日志） | 批准“先持久化并登记、再发终态”的顺序，但当前实现不能让 UI 获得日志 fileId。失败/取消终态须增加可选 `artifacts` 数组并同步契约、Schema、示例、验证器、ArkTS 类型、UI 和测试；不得从路径或文件名推导 fileId | 组长 / 2026-10-19 | 方向确认；实现待新 PR |
| B04/B05（恢复、取消与唯一终态） | 接受进程期服务、活动/最近 jobId、订阅后快照、序号保护、取消 ACK 非终态、唯一终态及 PROCESS_INTERRUPTED 方案；设备生命周期仍待验 | 组长 / 2026-10-19 | GitHub PR #4、`abcdf56` |
| B06（MVP 参数范围） | 首版请求仅开放相名、0～50 的 cycleCount 和无路径 `.gpx` 项目名，不为 recipe 设置通用默认 cycles；其他参数草稿不提交核心 | 组长 / 2026-10-19 | GitHub PR #3、#4 |

本轮已完成 A03～A07、B01～B06 的代码级审核。B03 仍需新 PR 实现；A03 的明确重试入口也需补齐。A02 的真机系统、签名、API20/24 兼容性和上架显示名仍未确认，所有代码级结论均不能替代第 5 节正式验收。

M1 子集已按声明的 mock 范围完成审核并合入 `main`。当前最先需要关闭的是 B03 契约/UI 增量与真实运行时装包；后续结论涉及契约字段时，仍须按本节流程同步更新并重新审核。
