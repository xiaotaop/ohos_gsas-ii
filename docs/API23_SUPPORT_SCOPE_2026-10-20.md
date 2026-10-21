# 组长决断：支持范围收窄至 API23 已验证基线

后续状态（2026-10-21）：0.1.2 `release/app_gallery` 公开签名候选已完成[API23 设备复验](PR21_0_1_2_DEVICE_RETEST_2026-10-21.md)和[限定整包技术审查](PR21_0_1_2_TECHNICAL_RELEASE_REVIEW_2026-10-21.md)。下方当时关于“尚待重建/复验”的文字为历史决断过程，不代表当前阻塞；API20/API24 未实测的收窄声明保持。

日期：2026-10-20。此前[API20/API24 环境核查](API20_API24_RETEST_2026-10-20.md)发现仅连接 HAD-W32/API23，且本机无可运行的 API20/API24 ARM64 镜像。组长随后决定**不再等待两端补测，收窄声明**。

当前对外可陈述：本项目的完整 GSAS-II 科学计算流程**已在 HarmonyOS PC API23 的 HAD-W32 上验证**。不声称 API20、API24 或更高版本已实机通过，也不声称只可能在 API23 运行。上架功能描述须继续限定已验证的 PbSO4 五阶段工作流，不能扩大为任意样品或原版 GSAS-II 全功能。

工程 `app/build-profile.json5` 的最低兼容版本从 `6.0.0(20)` 调至 `6.1.0(23)`，`targetSdkVersion` 保持 `6.1.1(24)`。最低兼容版本决定低于该 API 的设备能否安装；目标 SDK 是行为/构建配置，**不能**将它当作 API24 真机测试证据。此变更使源代码和实际待分发包声明一致地不再覆盖 API20，但并不能阻止安装在更高 API 的设备；对更高版本的实测仍不得虚构。

本机执行 `python scripts/Build-App.py --check`：ArkTS 检查 14 个文件无错误，开发构建成功。生成的**未签名、未装配完整运行时** HAP SHA-256 为 `5c612c048f0abc2708e2cf7e410f4735aae00e0fd3465677e4b162ef37feffca`；其 `module.json` 显示 `minAPIVersion=60100023`、`targetAPIVersion=60101024`。这仅证明新配置可构建并进入开发包，**不能安装替代正式签名包，也不是科学计算或分发验收**。工具输出明确为 `No signingConfig found for product default`。

此前完整签名内测 HAP `791dc53d…` 来自旧源码 `ce624cec…`，其内嵌最低兼容版本仍是 API20。它的 API23 五阶段、结果页 12 项数值、Core UI 观察与 C 的许可审查均保留为**该哈希的历史证据**，不能直接改写为尚未构建的新包证据。A 在 `59c86f18…` 旧包的已测场景继续按[组长限定的未变组件佐证](PR17_A14_EVIDENCE_BINDING_2026-10-20.md)保留。

2026-10-21 更新：C 已以精确提交 `c47b610…` 完成完整运行时重建/签名，实际包最低 API23，HAP `d65a64a9…` 的源码、签名、SBOM 与许可材料已重新绑定，见 [新包下载及收据](C_API23_SIGNED_HAP.md)。构建材料交付已完成；要关闭新范围发布门禁，仍须在 HAD-W32/API23 **覆盖安装且不清数据**，重新核对启动、五输入、真实五阶段、12 项结果数值、产物可发现/导出和重启恢复。新包若有其他改动，按实际差异增加回归范围。未取得这份新包和同包复验前，`releaseApproved=false`、`publicDistributionApproved=false`，不得提交上架。

同日后续：上述新包已完成[同包关键复验](PR20_API23_DEVICE_ACCEPTANCE_2026-10-21.md)，API23 内测候选的[整包技术审查](PR20_API23_TECHNICAL_RELEASE_REVIEW_2026-10-21.md)通过；未将 API20/API24 改写为已测试，公开分发及上架批准仍为 false。
