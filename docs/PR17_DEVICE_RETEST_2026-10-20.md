# PR #17 签名包同包真机复验（组长执行）

日期：2026-10-20。设备：HAD-W32，系统报告 `HAD-W24 6.1.0.117(SP68C00E100R13P3)`，API 23。本记录只适用于源码提交 `ce624cec654e3492697e22792a047ff69e88d4fc` 所构建的 0.1.1 / versionCode 2 签名 HAP，不将旧包证据转写为本包结果。原始全屏截图保存在本地测试目录；公开仓库不附带包含设备信息的原图。

| 产物 | 大小 | SHA-256 |
| --- | ---: | --- |
| `GSAS-II-0.1.1-ce624cec-signed.hap` | 135971349 字节 | `791dc53da7f76c56e0f9ce45b40b83d9cb45b9b42990379f59de64989d712788` |
| C 的完整交付 ZIP | 91500152 字节 | `7d26c658021426de1f536cefa5b2962c4d3682741cf777bb16545dfa9384b5c5` |

完整 ZIP 的 `SHA256SUMS` 19/19 通过；SDK `verify-app` 与原生代码签名校验通过，八个 GSAS-II AArch64 扩展均在 HAP 中。与先前 `59c86f18…` HAP 逐成员比较，2266 个条目中仅 `ets/modules.abc` 不同。使用 `hdc install -r` 覆盖安装，没有卸载或清除应用数据；应用 UID、首次安装时间不变，原文件库 37 项可见。

## 实测结果

| 场景 | 观察 | 结论边界 |
| --- | --- | --- |
| 五次取消/完成临界尝试 | 两次点击时任务已经成功（均约 6 秒），三次在 75%/90%/90% 取消；页面每次只显示一个终态。文件库依次由 37 增至 40、41、42、43、46。成功任务 GPX/JSON/日志及取消日志可发现，重启后成功结果恢复。 | 两次点击晚于完成，不构成 ACK/完成竞争；未取得 native 事件序列、jobId、ACK 时间戳或沙箱终态快照，不能证明严格的事件级终态唯一性。 |
| 显式断网五阶段 | 应用启动后开启飞行模式，`ifconfig` 仅 `lo` 有地址；PbSO4、Max cycles 3 完成五阶段，8.71 秒成功，文件库 46→49。GPX/JSON/日志通过系统保存对话框导出，再次打开时三项可见。测试结束后恢复 Wi-Fi。 | 关闭“运行中显式断网”待验项；不等于断网首次安装/启动验证。HDC 无权读取导出目标，未新增导出文件字节哈希。 |

## 尚未关闭

- 初始化失败后重试：此内测包的应用沙箱不可供 `hdc shell` 读写；`hdc shell -b com.gsasii.desktop` 返回 `Invalid bundle name`，应用 `files` 目录返回 `Permission denied`。无法用 `chmod` 注入失败；仍需可恢复的测试入口或同等真机证据。
- Core-only 第二任务 BUSY：页面运行时禁用再次 Refine，未获得 native 第二任务调用入口。宿主用例通过不能替代真机证据。
- 取消 ACK/自然完成的严格竞争：需要可关联 jobId 的 ACK/完成事件时序及终态快照，或测试包的等效诊断。当前仅能证明五次 UI 观察未出现终态跳变。
- API20/API24 兼容性、公开分发签名、上架授权和组长技术放行均未由本次测试取得。

## 2026-10-20 后续入口核查

设备仍连接，`bm dump -n com.gsasii.desktop` 显示已安装包为 0.1.1 / versionCode 2、`release/internaltesting`、`debug=false`。shell 用户为 `uid=2000(shell)`；读取应用 `files` 目录仍返回 `Permission denied`。对 `EntryAbility` 再次执行 `aa start` 后，进程号未改变，mission 列表仍只有一个该应用的 AbilityRecord，未形成可独立提交第二任务的窗口。

为检查是否能在设备上直接执行已有的原生 Core 测试，已用当前 SDK 将 `tests/core-service-native.test.cpp` 与正式 `core_service.cpp` 交叉编译为 AArch64 ELF，并使用 SDK 的开发自签工具签名。上传到 `/data/local/tmp` 后，shell 执行返回 `Operation not permitted`；该临时设备文件已移除。此结果**不是**测试失败或通过的 Core 结论，也不授权绕过设备执行策略。宿主 Core 桥接测试仍为 30/30 通过，但不能替代同包真机验证。

若要关闭上述三项，需由有签名权限的 C 在不清除用户数据的前提下交付可安装的诊断候选：一次性可恢复的初始化失败、在真实首任务活动时触发第二次 Core `acquireJob` 并记录 `BUSY`、逐 jobId 导出取消 ACK/完成事件顺序与唯一终态快照。诊断改动与正式候选的差异须逐项列出；若改动 HAP，按新哈希重新绑定签名、源码、SBOM/许可和设备证据。未取得该包及其设备记录前，本节仍为待验，不得标记通过。

复验步骤见 [B 的同包方案](B_PR17_DEVICE_RETEST.md)，C 的构建和许可绑定见 [签名 HAP 交接](C_PR17_SIGNED_HAP.md)。
