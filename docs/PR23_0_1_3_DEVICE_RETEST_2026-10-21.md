# PR #23：晶衍精析 0.1.3 签名包真机复验

日期：2026-10-21。应组长要求，Codex 在原 HarmonyOS PC 真机上对 C 的**指定设备复验 HAP**执行保留数据覆盖安装。设备包为 `JingyanJingxi-0.1.3-device-internaltesting.hap`，135971296 字节，SHA-256 `60fca45be125e825169b7fef90669cf76a0ef490adeeed1acd28f8ee1a9b94a7`；精确构建源码 `8b64bf6ebefa2b4e609f962e926c294e084b6d52`。公开 APP `89e6b3e4…` 未在设备安装；其与设备 HAP 的有效载荷等同性由[签名交付](C_RENAME_0_1_3_SIGNED_HANDOFF.md)和[最终审查](PR23_0_1_3_TECHNICAL_RELEASE_REVIEW_2026-10-21.md)分别固定。

## 设备、升级和显示名

- `hdc list targets -v`：`3QC0124C20000901`，USB Connected；型号 `HAD-W32`，系统报告 `HAD-W24 6.1.0.117(SP68C00E100R13P3)`，API 23。型号与软件前缀不同，照设备原值记录。
- 安装前 `bm dump` 为 0.1.2/versionCode 3；窗口标题 `GSAS-II`，应用就绪，文件库 55 项、旧成功结果和五份 PbSO4 输入可见。核对交付 ZIP `f4fe13ff7b8a22db37d625b5db2cdeb54e84ce1351fe106ccfec799bc6b81858` 与设备 HAP 哈希后，执行 `hdc install -r`，返回 `install bundle successfully`。未卸载、未清数据。
- 安装后为 0.1.3/versionCode 4；`bundleName=com.gsasii.desktop`、UID `20020149`、首次安装时间 `1792412214316`、签名指纹 `2CEBD21FF93976CAB5F09EFB30002ACDADC42526052D326B3DE3787E1DABAC9E` 均保持。启动后 Core 就绪、旧文件库仍为 55 项，旧成功结果和五输入保留。本次升级未观察到系统联网验证提示；旧 0.1.2 测试曾有该提示的事实保留在其历史记录。
- 新窗口标题及系统本机应用搜索“最佳匹配”均为**晶衍精析**，任务栏中应用图标可见。未取得任务栏文字悬浮提示图，不将图标本身充作文字证据。见 [Controls](evidence/a-rename-013-60fca45b/controls.jpeg) 和 [本机搜索](evidence/a-rename-013-60fca45b/launcher-name.jpeg)。

## 真实任务、数值与导出

使用原有五输入关联，相名 `PbSO4`、Max cycles `3`、输出 `rename013-api23-20261021.gpx`。新任务 8.76 秒完成五阶段，页面显示“100% · 五阶段精修已完成”，文件库 55→58。结果页五阶段 X 射线/中子 Rwp 依次为 `96.68110/99.74899`、`45.81200/17.86463`、`32.47622/15.02425`、`13.40589/6.36130`、`13.16477/6.38231`；`C(2,0)=0.12738142465744678`、`C(2,2)=0.09406617903303072`。

以 SHA-256 `8f471ac79ccf228205be85b15e42ad0074b0e1a22383d8b9ccfe6a333a34f70f` 的 [Windows 独立基线](../poc/results/windows-x86_64.json)复核：Rwp 对页面五位小数计入 `0.000005` 舍入上界，要求 `|页面值−基线值|+0.000005 ≤ 1e-7+1e-4×|基线值|`；取向要求 `|页面值−基线值| ≤ 1e-7+1e-3×|基线值|`。**12/12 通过**，最大差值/容差比 `0.110864213498246`。页面自身写“本次未执行基线校验”；这里是独立的页面数值复核，不声称已读取导出 JSON 全精度值。

GPX、JSON、日志三件产物在应用内有导出入口；分别通过系统保存对话框保存 `rename013-api23-20261021.gpx/.json/.log`，再次打开系统选择器时三件均可见。设备文件位置未由 HDC 读回原始字节，故结论限于**保存与可发现**，不写成导出字节哈希或内容一致性通过。[成功](evidence/a-rename-013-60fca45b/success.jpeg)、[产物](evidence/a-rename-013-60fca45b/result-artifacts.jpeg)。

## A 场景与重启

- 50 cycles 的独立任务在 35% 取消后，页面只有“任务已取消”终态并出现可导出的取消日志，文件库 58→59。[取消截图](evidence/a-rename-013-60fca45b/cancelled.jpeg)。未额外读取该日志的导出字节。
- 使用文件库中此前专为测试导入的 `A15-invalid.cif` 临时关联相输入，独立任务返回 `INVALID_PHASE_FILE`，失败日志可见，文件库 59→60。[失败截图](evidence/a-rename-013-60fca45b/failed.jpeg)。随后恢复 `PbSO4-Wyckoff.cif` 原关联，五输入存在性与完整性检查通过；没有改动原科研输入文件。
- 恢复后另一任务活动期间点击关闭，弹出“操作尚未结束”，当时页面仍显示 55% 精修中；返回应用后任务继续完成，文件库为 63。[关闭保护](evidence/a-rename-013-60fca45b/close-guard.jpeg)。将窗口缩至约 1220×914 物理像素，三个输入标签及 Refine/Cancel/Reconnect 仍可见；随后恢复原窗口尺寸。[最小窗口](evidence/a-rename-013-60fca45b/minimum.jpeg)。
- 用 `File → Exit` 正常退出，进程结束后重新启动；Core 就绪、原五输入与 63 项文件库保留，上一成功结果和产物入口恢复。[重启画面](evidence/a-rename-013-60fca45b/restarted.jpeg)。表单草稿是否持久化未列为通过。

本次重新取得的十张原始全屏照片及各自 SHA-256 见 [A 新名称截图索引](A_RENAME_0_1_3_DEVICE_SCREENSHOTS_2026-10-21.md)。原始 UI 布局、完整系统选择器和安装中间材料留在 Git 忽略的 `app/build/acceptance-rename-013-20261021/`。结构化结果见[physical-acceptance.json](../packaging/reviews/c-rename-0.1.3/physical-acceptance.json)。

**结论：**该精确设备 HAP 在 HAD-W32/API23 完成同签名递增版本的保留数据升级、系统本机名称显示、真实五阶段及 12 项数值复核、三类导出可发现、A 三种终态与关闭保护、最小窗口和正常退出重启恢复。API20/API24、其他设备、导出原始字节、长时后台及应用商店公开 APP 的平台检测与安装不在本次实测范围。
