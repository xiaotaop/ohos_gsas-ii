# 组长决断：支持范围收窄至 API23 已验证基线

日期：2026-10-20。此前[API20/API24 环境核查](API20_API24_RETEST_2026-10-20.md)发现仅连接 HAD-W32/API23，且本机无可运行的 API20/API24 ARM64 镜像。组长随后决定**不再等待两端补测，收窄声明**。

当前对外可陈述：本项目的完整 GSAS-II 科学计算流程**已在 HarmonyOS PC API23 的 HAD-W32 上验证**。不声称 API20、API24 或更高版本已实机通过，也不声称只可能在 API23 运行。上架功能描述须继续限定已验证的 PbSO4 五阶段工作流，不能扩大为任意样品或原版 GSAS-II 全功能。

工程 `app/build-profile.json5` 的最低兼容版本从 `6.0.0(20)` 调至 `6.1.0(23)`，`targetSdkVersion` 保持 `6.1.1(24)`。最低兼容版本决定低于该 API 的设备能否安装；目标 SDK 是行为/构建配置，**不能**将它当作 API24 真机测试证据。此变更使源代码和实际待分发包声明一致地不再覆盖 API20，但并不能阻止安装在更高 API 的设备；对更高版本的实测仍不得虚构。

本机执行 `python scripts/Build-App.py --check`：ArkTS 检查 14 个文件无错误，开发构建成功。生成的**未签名、未装配完整运行时** HAP SHA-256 为 `5c612c048f0abc2708e2cf7e410f4735aae00e0fd3465677e4b162ef37feffca`；其 `module.json` 显示 `minAPIVersion=60100023`、`targetAPIVersion=60101024`。这仅证明新配置可构建并进入开发包，**不能安装替代正式签名包，也不是科学计算或分发验收**。工具输出明确为 `No signingConfig found for product default`。

此前完整签名内测 HAP `791dc53d…` 来自旧源码 `ce624cec…`，其内嵌最低兼容版本仍是 API20。它的 API23 五阶段、结果页 12 项数值、Core UI 观察与 C 的许可审查均保留为**该哈希的历史证据**，不能直接改写为尚未构建的新包证据。A 在 `59c86f18…` 旧包的已测场景继续按[组长限定的未变组件佐证](PR17_A14_EVIDENCE_BINDING_2026-10-20.md)保留。

要关闭新范围的发布门禁，仍需由正式签名负责人用上述修改后的精确源码和完整运行时重新构建/签名，固定新 HAP SHA-256、签名身份、Profile、实际 SBOM/许可及源码伴随；在 HAD-W32/API23 **覆盖安装且不清数据**，重新核对启动、五输入、真实五阶段、12 项结果数值、产物可发现/导出和重启恢复。新包若有其他改动，按实际差异增加回归范围。未取得这份新包和同包复验前，`releaseApproved=false`、`publicDistributionApproved=false`，不得提交上架。
