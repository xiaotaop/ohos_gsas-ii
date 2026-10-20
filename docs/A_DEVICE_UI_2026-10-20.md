# A：真机交互检查与界面修整

日期：2026-10-20。代码基线：`9f3dec2`；工作分支：`ui/device-validation`。

后续更新：PR #14 源码已由 C 打入完整签名包 `59c86f18…`，A 已完成新界面同包验收，见 [新包记录](A_A14_DEVICE_ACCEPTANCE.md)。下文保留修改前版本的历史证据边界。

## 安装版本与证据边界

本次直接使用已安装的 `com.gsasii.desktop`，读取版本为 0.1.1 / versionCode 2，设备为 HAD-W32 / OpenHarmony 6.1.0.115 / API23。没有卸载、清除数据或更换签名。未取得 C 的完整交付包，也未独立读取已安装 HAP 的 SHA-256，因此不将版本号等同于包哈希验证。

下面所有截图均来自**修改前的已安装版本**，仅裁剪应用窗口，未修改界面内容，不含设备标识和用户笔记。它们是验证证据，不是本轮新界面截图或商店发布素材。

## 本轮实际执行

| 检查 | 结果与证据 |
| --- | --- |
| 输入与真实计算 | 使用已有关联的五份 PbSO4 输入，相名 PbSO4、Max cycles 3，输出 A-UI-20261020.gpx；本轮新任务成功，界面耗时 8.94 秒。[成功页面](evidence/a-device-2026-10-20/a-success.png) |
| 产物可发现 | 任务页显示 GPX、JSON、日志三项及 Export 入口；本轮未导出或作独立数值对比，页面明确显示未执行基线校验。[结果与产物](evidence/a-device-2026-10-20/a-result-artifacts.png) |
| 活动任务关闭 | 在 validating 阶段点击窗口关闭，显示“操作尚未结束”，任务没有退出，随后成功。[关闭拦截](evidence/a-device-2026-10-20/active-close.png) |
| 窗口与键盘 | 实测最小窗口 1216 × 912 物理像素（640 × 480 vp）、最大化；Ctrl+R 打开任务页，Tab 从相名进入 cycles。最小窗口的三个输入及操作按钮可见。[最小窗口](evidence/a-device-2026-10-20/minimum-task.png) |
| 结果区滚动 | 通过设备触控滑动查看全部五阶段、择优取向和产物；这不是鼠标滚轮验收。 |
| 列表刷新缺陷 | 本轮任务成功后文件库仍为 22 / 22；正常关闭再打开后恢复 25 份文件及同一成功任务。证实新增产物持久化，但父页面列表未刷新。[重开恢复](evidence/a-device-2026-10-20/a-restored.png) |

没有重复 C 已报告的取消、失败日志导出和升级保留测试；这些报告不算本轮新增实测。后台最小化、BUSY 竞态、鼠标滚轮和修改后新包的同包验收仍未完成。

## 修复与原版界面依据

文件列表沿用既有任务状态回调：活动状态结束时重新读取 FileService，覆盖成功、失败、取消和恢复终态；CancelAck 和进度更新不触发刷新。服务本身串行处理列表与文件操作，页面卸载或更换服务后丢弃旧回调。保留未知近期 jobId 的清理逻辑，增加手动 Refresh 入口以便刷新失败后重试。

界面核对锁定上游 `2b4aba1bc44de63a3da9d4495944c3b99e389399`：

- [GSASIIdataGUI.py](https://github.com/AdvancedPhotonSource/GSAS-II/blob/2b4aba1bc44de63a3da9d4495944c3b99e389399/GSASII/GSASIIdataGUI.py)：菜单组织、Refinement Controls、Max cycles 和 Sequential Settings。
- [GSASIIpwdGUI.py](https://github.com/AdvancedPhotonSource/GSAS-II/blob/2b4aba1bc44de63a3da9d4495944c3b99e389399/GSASII/GSASIIpwdGUI.py)：Limits 的 Data range to be used in fits 标题与范围组织。

移除常驻开发进度、样例限制、草稿说明、冗余引导、内部任务 ID、源码提交号及文件令牌/哈希展示；应用名改为 GSAS-II。参数页和弹窗保留标题与字段，操作文字简化为 Edit、Save。未实现的 Select datasets 和 Add excluded region 保持禁用。精修输入采用持续可见标签，避免填写后丢失字段名称。诊断入口移至帮助页，功能范围在帮助及操作说明中说明。

本轮没有改变参数的存储和提交语义，也没有实现原版工程解析、绘图、完整参数直编或全量 GUI；不能将文字清理称为完整功能复刻。

## 修改后代码验证与交付限制

- 正式会话与参数模型测试：35 / 35 通过。首次运行因沙箱临时目录不可写失败，改用工作区临时目录后通过，没有修改或放宽测试。
- 最终 ArkTS 编译、ARM64 unsigned debug HAP 构建通过。删除 ActionSheet 文案时编译发现 message 为必填项，改为空字符串后最终构建通过。
- development HAP 内容审计：21 个文件通过。存在既有异常处理建议、打包工具弃用提示和未配置签名提示。
- HAP SHA-256：`cd1d5d8e0f56dfe5c3f9d4644683ea8c83bc91237ea88534f2dc818ee8a39a2b`。
- 本地日志及审计保存在忽略目录 `app/build/a-device-20261020/`。

该本机构建不含完整科学运行时且未签名，**未安装到真机**。必须由 C 将本轮源码装入完整运行时并按目标设备签名，随后复验任务结束后无需重启即可显示三份新产物、失败/取消日志刷新、最小窗口与新文案，再生成同包截图。当前证据不构成上架放行。
