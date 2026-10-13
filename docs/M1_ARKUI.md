# 成员 A · GSAS-II UI 源码映射与 M1 ArkUI 演示

基线：`5e486c6477fa4bdc3642ccc7043568f3a777243c`，接口 v1.0。

提交规则：成员 A 使用 `ui/mock-refinement` 独立分支提交，交由组长审核后合并；不直接向 `main` 提交，也不自行合并。

## 原项目源码如何映射到 ArkUI

本实现以锁定上游提交 `2b4aba1bc44de63a3da9d4495944c3b99e389399` 的 [GSASIIdataGUI.py](https://github.com/AdvancedPhotonSource/GSAS-II/blob/2b4aba1bc44de63a3da9d4495944c3b99e389399/GSASII/GSASIIdataGUI.py) 为依据，人工翻译 wxPython 的控件组织、数据树和事件入口；不是自动语法转换，也不是完整 GUI 复刻。

| 上游入口（锁定版本行号） | ArkUI 对应 | 本次范围与差异 |
|---|---|---|
| `FillMainMenu`（3075）及 `_Add_*MenuItems` | `mainMenu` 和各菜单构建函数 | 保留 File / Data / Calculate / Import / Export / Help 的顺序，选取 M1 相关命令；未移植命令禁用 |
| `SplitVertically`（3204）、`G2DataWindow` | `dataTree`、`dataPage`、两个滚动区域 | 宽窗口左树右页；窄窗口上下排列。未实现原生可拖动分隔条 |
| `CheckNotebook`（3561） | 六个公共根节点 | 保留 Notebook、Controls、Covariance、Constraints、Restraints、Rigid bodies 的顺序；后面三项禁用 |
| `OnImportPhase`（1298）、`OnImportPowder`（2014） | Phases / PbSO4、PWDR 及其子节点 | 固定示例关联；可展开、选择。尚不解析晶体、仪器参数或谱线 |
| `UpdateControls`（8081） | `controlsPage` | 保留最小二乘参数页组织；Max cycles 从请求加载为 3，其余契约未提供的参数明确显示不可用 |
| `OnRefine`（5737）及其进度窗口调用 | Calculate → Refine、Ctrl+R、`refinementProgress` | Python 科学计算调用替换为 `CoreService` mock；进度、取消和终态由事件驱动 |

原项目独立的绘图窗口在 M1 中暂用 `Data window / GSASII Plots` 切换表示。绘图页只说明缺少曲线数据，不合成曲线。结果摘要附在 Controls 页；Notebook 暂显示事件消息。这些是适配当前接口的明确差异，不声称与上游编辑器、绘图、日志或结果对话框等价。顶部场景选择条是 M1 验收辅助功能。

译写作者/组织：noth1ng / ohos_gsas-ii（成员 A），2026-10-13。页面源码保留来源及修改注释；根目录 `LICENSE`、`NOTICE` 保留原文，应用 Help → About 包含来源与致谢。

## 已实现范围

`ui-mock/` 是可独立打开的 DevEco 演示工程，用于在成员 C 的正式工程就绪前开发和验收界面。临时 bundleName 为 `com.example.gsas.uimock`，不代表正式应用标识或发布候选。

- 原生 ArkUI 页面：原项目菜单与数据树、Controls、示例文件关联、场景选择、精修进度弹窗和结果。
- 成功：回放已有事件，展示五阶段 X 射线/中子 Rwp、示例耗时、基线校验和 GPX/JSON 产物名称。
- 失败：展示 `INVALID_INSTRUMENT_FILE` 和可读消息；`retryable: false` 时不提供直接重试，返回输入区后可重新选择演示。
- 取消：开始后等待用户点击取消；先显示取消等待，收到 `job.cancelled` 才显示终态。不把 CancelAck 当作取消完成。
- 成功/失败演示运行期间也可取消。取消不会使进度或当前阶段倒退。
- 先订阅再启动；忽略旧任务、重复/过期序号和终态后的事件；演示只允许单任务，重复启动返回 `BUSY`。
- 900 vp 以下改为单栏，上方数据树、下方数据页；宽窗口为双栏，整页及各数据区域可滚动。
- 页面始终标记模拟数据，输入清单只读，导出按钮禁用，不生成真实科学结果或假导出文件。

M1 没有实现系统文件选择、真实 FileService、Python/N-API、运行时部署、真实导出或发布签名。已有成功示例只列 GPX/JSON，没有日志产物；界面的“任务动态”是事件消息，不冒充 Python 日志。

## 文件入口

| 文件 | 用途 |
|---|---|
| `ui-mock/entry/src/main/ets/pages/Index.ets` | 页面及交互 |
| `ui-mock/entry/src/main/ets/model/Refinement.ts` | UI 类型、状态转换、CoreService mock |
| `ui-mock/entry/src/main/resources/rawfile/` | 原样打包的四份契约示例 |
| `scripts/Sync-UiMockFixtures.ps1` | 同步资源，`-Check` 只比较哈希 |
| `scripts/Test-UiMock.ps1` | 类型检查、六项行为测试及示例一致性检查 |

示例以 `contracts/examples/` 为唯一数据来源。资源复制是 ArkUI 打包需要，不独立编辑；契约变化后运行同步脚本。

## 打开与演示

在 DevEco Studio 打开 `ui-mock` 目录。当前演示使用 HarmonyOS 6.1.1 / API 24 SDK，兼容版本设为 HarmonyOS 6.0 / API 20；正式产品版本由 C 确定。

1. 运行入口页，选择“成功”，通过 Calculate → Refine、Controls 页 Refine 或 Ctrl+R 启动；约三秒后点击 View results，滚动查看结果和禁用的导出按钮。14.305 s 是示例的计算耗时，不是此次回放计时。
2. 选择“失败”，启动精修；应显示仪器参数错误，不出现直接重试按钮或 traceback。点击“返回并检查输入”回到 X 射线 Instrument Parameters 页。
3. 选择“取消”，启动精修；点击 Cancel，应经历等待状态，约两秒后显示“任务已取消”。关闭后可再次启动，不能残留旧结果。
4. 调整窗口宽度，检查数据树/数据页分栏与滚动；用 Tab、Enter 操作菜单，用 Ctrl+R 启动任务。

本次 DevEco PC 模拟器允许安装未签名调试 HAP。真机调试仍需本地调试签名或 C 提供的签名配置；不要提交证书、密钥或签名后的包。模拟器安装成功不代表具备真机安装或发布条件。

## 本地验证

在仓库根目录执行，`$devEco` 使用本机实际安装目录：

```powershell
$devEco = 'C:\Path\To\DevEco Studio' # 替换为本机安装目录
.\scripts\Test-UiMock.ps1 -DevEcoHome $devEco
```

编译演示 HAP：

```powershell
Set-Location .\ui-mock
$env:DEVECO_SDK_HOME = Join-Path $devEco 'sdk'
$env:JAVA_HOME = Join-Path $devEco 'jbr'
$env:HVIGOR_USER_HOME = Join-Path (Get-Location) '.hvigor-user'
$env:npm_config_cache = Join-Path (Get-Location) 'build\npm-cache'
& "$devEco\tools\node\node.exe" "$devEco\tools\hvigor\bin\hvigorw.js" --mode module -p product=default -p module=entry@default assembleHap --no-daemon
```

产物位于 `ui-mock/entry/build/default/outputs/default/entry-default-unsigned.hap`，已被 Git 忽略。缓存仅配置到项目内，不更改全局工具设置。

验证记录（2026-10-13）：

- ArkUI/ArkTS 编译与未签名 HAP 打包通过。运行检查发现并修正滚动区居中、异步参数未刷新的问题，最终安装包中 Max cycles 正确显示为 3。
- 六项事件/状态行为测试通过；四份打包资源与契约示例 SHA-256 一致。此次界面翻译未更改已验证的状态模型或原始契约示例。
- HarmonyOS 6.1.1 / API 24、DevEco MateBook Pro x86-64 PC 模拟器实际安装并运行通过。不是 Previewer 截图；Previewer 的 TextDecoder mock 不足以完成本应用数据加载验收。
- 成功：菜单和 Ctrl+R 启动，完成弹窗、五阶段 Rwp、基线校验及 GPX/JSON 名称显示；结果区鼠标滚动可达，导出禁用。
- 失败：`INVALID_INSTRUMENT_FILE`、不可直接重试、返回 Instrument Parameters 均通过；切换场景后旧成功结果清除。
- 取消：已观察“正在取消”及禁用的等待按钮，随后进入“任务已取消”，无结果；关闭后再次启动通过。
- 宽窗口左右分栏、缩窄后上下分栏通过；Tab 焦点可见，Enter 打开 File 菜单，Escape 关闭菜单，Ctrl+R 启动任务通过。未做全控件可访问性审计。

截图：[`01-controls.jpeg`](evidence/m1-arkui/01-controls.jpeg)、[`02-success-results.jpeg`](evidence/m1-arkui/02-success-results.jpeg)、[`03-failed.jpeg`](evidence/m1-arkui/03-failed.jpeg)、[`04-cancelling.png`](evidence/m1-arkui/04-cancelling.png)、[`05-cancelled.jpeg`](evidence/m1-arkui/05-cancelled.jpeg)、[`06-narrow.jpeg`](evidence/m1-arkui/06-narrow.jpeg)。JPEG 来自模拟器显示截图；取消等待 PNG 来自模拟器窗口抓帧，仅裁去右侧宿主桌面。均为模拟数据。

未执行 HarmonyOS PC 真机 GUI 验收、真实核心/文件服务联调或签名发布。工具链 Java 废弃 API 提示不属于应用编译错误；缺少 signingConfig 符合本演示的未签名范围。

## 正式工程接入

与 B/C 需要确认的接口、文件生命周期、初始化、日志产物和验收事项统一维护在 [接入对齐清单](INTEGRATION_ALIGNMENT.md)。其中区分冻结约定与待确认选择，并提供负责人、交接内容和确认记录；M1 临时类型不作为正式契约。

本次未修改冻结契约、Schema、原始示例、计算 PoC 或 C 的发布职责；分支供组长审核，尚未合并；没有向团队发送消息。

This product includes software produced by UChicago Argonne, LLC under Contract No. DE-AC02-06CH11357 with the Department of Energy.
