# 成员 A：正式页面与素材交付

日期：2026-10-19；分支 `ui/core-integration-finish`，PR #5。按 TEAM_ASSIGNMENT §4 和 PHASE3_HANDOFF §8 的五阶段 MVP 范围交付，不扩大到完整 GSAS-II GUI。

组长复核更新：B 的 PR #6 和本 A 端 PR #5 已依次代码级审核并合入主线，另有 [HAD-W32 设备验证记录](B_DEVICE_VALIDATION_2026-10-19.md)。8 个扩展在设备 HiShell 可导入，本地完整载荷门禁通过；签名 HAP 未在设备安装，以下 A 端旧记录仍不构成应用内精修、导出或发布验收。正式签名及发布审计由 C 负责。

## 交付入口

- 正式页面：`app/entry/src/main/ets/pages/Index.ets`。
- [UI 操作说明](UI_USER_GUIDE.md)：五文件关联、任务参数、取消／错误／导出、本地草稿、文件管理和快捷键；计算相关步骤明确标注依赖完整运行时。
- 图标唯一可编辑源文件：[app_icon.svg](../app/AppScope/resources/base/media/app_icon.svg)。128 × 128 viewBox，深绿底、浅绿折线和白色圆点；现有资源随 C 的正式工程引入（`3d6957d`），本次复用，不声称新创作或重新授权。
- 图标交付预览：[128px](assets/app-icon-128.png)、[512px](assets/app-icon-512.png)。由上述 SVG 等比例栅格化，未改设计；512px 为交付预览，不代表已满足商店最终规格。
- [图标文件清单](assets/icon-manifest.json) 记录唯一源文件、预览文件的大小和 SHA-256，便于 C 核对素材。
- 图标许可沿用仓库许可与 NOTICE；正式素材来源／使用范围由 C 在发布审查中确认。最终显示名、商店尺寸与格式由 C 确认后再导出，不把当前资源标为已获上架批准。

复现 PNG（需要 Node.js 的 sharp 包）：

```js
const sharp = require('sharp');
const source = 'app/AppScope/resources/base/media/app_icon.svg';
Promise.all([128, 512].map(size => sharp(source, { density: 384 })
  .resize(size, size).png().toFile(`docs/assets/app-icon-${size}.png`)));
```

## B PR #6 整合与 A 端代码验证（2026-10-19）

在 `ui/core-integration-finish` 上合入 B 的 PR #6 提交 `665c0013a4fc7d9e43a4c904ae1fdc2e5335915a`，保留双方提交历史；此操作没有合并主线，也不代替组长对 PR #6 契约与核心实现的审核。A 的整合前提交为 `7eac2766ef1cbb95973fcfe43137855b5711364c`。

- 解决共享模型与核心说明两处冲突；失败／取消日志仅保留一套展示和导出入口。
- 协议的 `artifacts` 仍为可选字段，正式页面统一映射为数组；缺字段显示未提供可导出日志，不猜测 fileId，也不把启动拒绝一律归因为日志登记失败。
- 保留 A 的独立初始化重试、父页面表单、最小窗口与输入宽度约束；保留 B 的失效近期 ID 清理。`JOB_NOT_FOUND` 仅在没有收到新事件时释放恢复状态，迟到错误不清空进度或终态。
- B 的终态日志返回和持久化快照已与 A 会话整合；新增四项组合测试覆盖失败／取消、登记成功／失败、登记返回令牌、重建服务后的快照以及新任务清除旧日志。

验证：正式会话 **23 项** + 核心门面／A 会话组合 **27 项**，共 **50 项通过、0 跳过**；独立 mock 模型 **14 项通过**。包含真实 Python 宿主桥接事件与页面状态比对，但科学计算和原生模块使用测试替身。契约语义检查及四份 mock 资源同步检查通过；本机未安装 jsonschema，JSON Schema 扩展校验未运行。命令：

```powershell
$env:GSAS_TYPESCRIPT_PATH = '<DevEco>/sdk/default/openharmony/ets/build-tools/ets-loader/node_modules/typescript'
$env:TEMP = Join-Path (Get-Location) 'app/build'
$env:TMP = $env:TEMP
# 先按 scripts/Test-UiMock.ps1 的 tsc 命令编译 ui-mock/build/test-model。
node --test tests/formal-refinement.test.cjs tests/core-bridge-host.test.cjs
python scripts/Validate-CoreContracts.py
pwsh -NoProfile -File scripts/Sync-UiMockFixtures.ps1 -Check
```

正式 ARM64 unsigned debug HAP 的 ArkTS 编译和构建通过（SDK API24 / 6.1.1.125、Hvigor 6.24.4），development 内容审计 **21 条目通过**；SHA-256：`164125e00008724b1eb30b68cdf0459a27905499d522e4c047671aa7c4c4b511`。测试日志、构建日志与审计分别留在本地忽略目录 `app/build/a-b6-host-tests.log`、`app/build/a-b6-hap-build.log`、`app/build/a-b6-hap-audit.json`。仍有既有类别的异常处理建议和未配置签名提示。

本轮未安装或运行新版 HAP，未新增模拟器／真机 UI 证据；以下截图与窗口检查仅对应整合前的 `7eac276`，不能作为本轮日志界面的运行证据。A 当前已完成代码整合与上述验证，个人剩余项是完整运行时下的真实 UI 验证和同版本正式功能截图，具体依赖见文末。宿主验证不证明设备导出或科学数值正确。

## 正式页面交互检查（整合前 `7eac276`）

本轮正式 `app/` 的 ARM64 与隔离 x86_64 工程均通过 ArkTS/HAP 构建（SDK API24 / 6.1.1.125、Hvigor 6.24.4）；ARM64 development 内容审计 21 条目通过。仍为未签名 debug 包，既有异常处理类告警未清除。模拟器以保留数据的升级安装运行最终 x86_64 包。

| 实测项目 | 结果 |
|---|---|
| 最小尺寸和最大化 | MateBook Pro / HarmonyOS 6.1.1 API24，浮动窗口缩小到 1216 × 912 px 后无法继续缩小，对应 640 × 480 vp；最大化后正常重排 |
| 分隔栏和输入控件 | 在最小窗口拖宽数据树，输入下拉框右缘仍在内容区内；右侧触控滑动后 CIF、Import 和 Check input files 可达 |
| 草稿弹窗与键盘 | 最小窗口下按钮均可见；Tab 聚焦 Select，Enter 展开选项，Esc 关闭选项；Shift+Tab 反向聚焦保存按钮，有可见焦点框 |
| 草稿取消 | Clear form 显示仅保存后生效的提示；Cancel 后原空草稿保持不变。本轮没有写入或覆盖既有草稿 |
| 文件筛选与滚动 | 搜索 `zzz` 显示 0/11，无匹配提示明确；清除后恢复 11/11；滚动可达文件操作按钮 |
| 删除确认取消 | 显示删除应用副本的说明，点击取消后保留文件；未执行实际删除 |
| 快捷键与状态 | F1 显示新版帮助，Ctrl+R 打开任务页；缺运行时提示明确且 Refine 禁用 |
| 鼠标滚轮 | 通过 Windows 模拟器窗口注入真实鼠标滚轮事件，数据树向下滚动，右侧 Controls 保持原位置；与触控滑动分开验证 |
| 空闲退出与恢复 | 系统关闭按钮关闭应用窗口；重新打开后恢复 11 个文件。此项不覆盖活动计算的退出提示 |

修正了过窄窗口导致输入下拉框右侧被裁的问题：设置主 Ability 最小尺寸并约束输入 Select 最大宽度。最小尺寸字段单位按 [OpenHarmony module 配置说明](https://gitcode.com/openharmony/docs/blob/OpenHarmony-4.0-Beta1/en/application-dev/quick-start/module-configuration-file.md)，并通过当前 SDK 配置校验和模拟器实测。帮助页同时改为以任务页初始化状态判断计算可用性，明确草稿不自动提交。

证据：[最小窗口输入区](evidence/a-ui-delivery-2026-10-19/minimum-inputs.png)、[草稿弹窗与键盘焦点](evidence/a-ui-delivery-2026-10-19/minimum-dialog.png)、[新版帮助](evidence/a-ui-delivery-2026-10-19/help.png)、[运行时缺失状态](evidence/a-ui-delivery-2026-10-19/runtime-unavailable.png)。均为最终包的模拟器原始 PNG，不包含宿主桌面，不是商店发布截图。

[验证记录](evidence/a-ui-delivery-2026-10-19/verification.json) 保存构建基线、源码文件指纹、HAP 与截图哈希和验证边界。ARM64 HAP SHA-256 为 `ed757b26521940411c48f55f82a28bbfb8220ad28962a76e13a44cacff874a0f`，x86_64 为 `d684c768152a15744d40ddff3d842c01413eb479d2bf5d5273d8e3f509d9b5d3`。本地包、原始布局与构建日志留在忽略目录 `app/build/deliverables/a-ui-delivery-20261019/`；二进制 HAP 不提交 Git。

未改动的会话／门面模型继续沿用 `b0e61a0` 的 40 项宿主测试证据，本轮没有把它们重复计为新实测。未执行真机、真实精修及产物导出、活动任务退出提示、签名与发布验收；不同 API、显示缩放和真机窗口行为需在正式集成包补验。

## 截图交接

- [正式 Controls 与数据树](evidence/a-desktop-controls-2026-10-18.jpeg)、[正式文件库](evidence/a-desktop-files-2026-10-18.jpeg)：既有模拟器开发证据，非本轮最终截图。
- `evidence/m1-arkui/` 是 mock 演示，不能用于宣称真实计算。
- 发布用成功结果、失败／取消日志导出和真机功能截图须在同一正式候选 HAP 上重新采集；C 汇总前核对源码提交、HAP 哈希、设备／系统和截图对应关系。

## 依赖与关闭条件

| 主责 | 尚缺交付 | A 后续动作 / 关闭条件 |
|---|---|---|
| B，C 配合部署 | B 已提供载荷配方、真实 Python 交叉编译支持；8 个扩展在 HAD-W32 HiShell 与本地组装物中通过，仍缺冻结的可重建分发载荷和可安装、可运行的集成包 | A 在同一包上验证五文件 → 五阶段任务 UI → GPX/JSON/日志导出入口和长任务响应；科学数值判定由 B/组长负责 |
| B，组长审核 | B03 契约／Schema／示例／验证器、终态日志返回及持久化快照已随 PR #6 审核合入；HiShell 证据已有，但无 HAP 应用内证据 | A 宿主组合验证已通过；在完整包验证日志 fileId 真实可查可导出、缺字段反馈和三种终态展示 |
| B/C，组长组织 | 可运行真实任务的设备与集成包；宿主快照恢复已有实现和测试 | A 验证取消等待、退出提示、后台／页面重建及进程重启后的恢复展示；不恢复旧计算 |
| C | 正式签名集成包、商店素材规格与最终显示名 | A 补同版本真机交互和正式截图；按规格提供图标导出物 |
| 组长 | PR 审核合并、目标设备/API与发布候选确认 | A 修复 UI 审核问题并配合验收，不自行合并或签署放行 |

当前材料可供 A 端开发交接；不代表个人整体结项、真实计算验收或发布批准。无需等待运行时即可整理说明和图标、检查非计算交互；最终真机 UI 与科学计算验收仍需补齐。
