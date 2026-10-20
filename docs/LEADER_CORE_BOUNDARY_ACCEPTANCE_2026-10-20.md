# 组长决断：Core 边界专项证据接收

日期：2026-10-20。组长明确接受以下证据组合，作为本轮 Core 边界专项的验收口径：B 的宿主测试验证异常初始化后可重试、Core-only 第二任务 `BUSY` 映射与取消/完成竞争时门面仅交付一个终态；C 按包含 B 修复的精确源码 `ce624cec654e3492697e22792a047ff69e88d4fc` 构建的签名 HAP `791dc53da7f76c56e0f9ce45b40b83d9cb45b9b42990379f59de64989d712788` 在 HAD-W32/API23 完成覆盖安装、五次 UI 级取消/完成临界尝试及显式断网五阶段。本次复核 `tests/core-bridge-host.test.cjs` 为 30/30 通过。

此决断将上述三项从**本轮技术验收的阻断清单**移出，按“宿主专项通过＋签名包 UI 真机观察通过／受限”接收。它**不声称**在该 HAP 内人为触发过初始化失败或 Core-only 第二任务，也不声称取得 native 取消 ACK/完成的事件时序、jobId 或沙箱终态快照；这些仍是未覆盖的设备边界，而非“真机通过”。后续若发现现场故障、改变 Core 实现，或要求更严格的发布门槛，应重新打开相应专项。

证据：[B 的同包测试步骤](B_PR17_DEVICE_RETEST.md)、[组长设备复验与限制](PR17_DEVICE_RETEST_2026-10-20.md)、[C 的签名包和来源绑定](C_PR17_SIGNED_HAP.md)。此决断**仅限 Core 边界专项的证据口径**，不构成 API20/API24 兼容性决策、整包技术放行、公开分发签名或上架批准；`releaseApproved=false`、`publicDistributionApproved=false` 保持不变。
