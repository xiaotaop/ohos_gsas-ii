# C：API23 完整运行时签名 HAP 交付

后续状态（2026-10-21）：本页是 C 提交时的交付快照，其中“待组长复验/技术放行”不再代表现状。该包已完成[同包设备关键复验](PR20_API23_DEVICE_ACCEPTANCE_2026-10-21.md)及[限定内测范围技术审查](PR20_API23_TECHNICAL_RELEASE_REVIEW_2026-10-21.md)；公开分发/上架仍未批准。以下 C 原始收据中的 pending 布尔值保留其提交时语义，不修改历史证明。

交付时状态（2026-10-21）：按组长 [API23 收窄决断](API23_SUPPORT_SCOPE_2026-10-20.md)，以精确源码 `c47b6105fdb31ac0536c6d058f5ffb54cb51c5b6` 重建并签名完整 HAP。**C 当时已完成构建、签名及离线材料审查；新包 API23 真机关键复验、技术放行和公开分发尚待。** 不改指定源码或版本号，不把旧包设备证据转写为本包通过。后续结果以上方链接为准。

| 标识 | 值 |
| --- | --- |
| 应用/版本 | com.gsasii.desktop / 0.1.1 / versionCode 2 |
| 精确源码 | `c47b6105fdb31ac0536c6d058f5ffb54cb51c5b6` |
| 最低/目标 API | 23 / 24（实际 module.json：60100023 / 60101024） |
| HAP | `GSAS-II-0.1.1-c47b610-api23-signed.hap` |
| HAP SHA-256 | `d65a64a90cba7d029d43b7549c626903ccf1080a6f5b4aa8a70f77148909b25b` |
| HAP 大小 | 135971385 字节 |
| 完整 ZIP SHA-256 | `144eb5a5e8d298f662373059330368d4f1dbb277be663f8b162610e87c1a8929` |
| ZIP 大小 | 91548243 字节 |
| 签名身份 | 原发布证书 + 原 HAD-W32 指定设备 release/internaltesting Profile，字节一致 |

## 下载和核验

[签名 HAP](../deliveries/GSAS-II-0.1.1-c47b610-api23-signed.hap) · [完整材料 ZIP](../deliveries/c-api23-c47b610-d65a64a9.zip) · [大小/哈希清单](../packaging/reviews/c-api23-c47b610/download.json)

二者使用 Git LFS。在 GitHub 文件页点击 **Download raw file** 下载实际内容，不要把 LFS 文本指针当 HAP。完整 ZIP 包含同一 HAP、两个源码伴随、版权全文、运行时清单、实际 SBOM 草稿/文件索引/原生关系、签名/API/源码/材料审查收据、SHA256SUMS 和给组长的复验步骤。须完整保留源码和版权材料。

## 已完成的核验

- DevEco CLI Release 构建成功；SDK verify-app 与原生 codesign 校验成功；证书链和 Profile 与已安装参考包完全一致。签名记录只公开指纹与校验结果，不上传独立 Profile、证书、私钥或密码。
- 50 个实际 app 文件与指定提交及源码伴随逐项一致；build-profile 另行剥除本地 signingConfigs/signingConfig 后与指定源码结构一致。源码伴随的全部 896 个文件哈希核验通过。
- 相比旧 HAP `791dc53d…`，仅 module.json 的 minAPIVersion 从 60000020 变成 60100023、pack.info 的 compatible 从 20 变成 23。其余 HAP 文件（含 ets/modules.abc）逐字节不变。版本仍是 0.1.1 / 2，不把同版本覆盖写成递增版本升级；目标 API24 也不代表 API24 已实测。
- 2245 运行时文件、实际 HAP 2266 文件 / 219 ELF、全部八个扩展均齐全并核验哈希。219 原生库及 40 个许可文件还直接核对至已审查的 70588bde 参考包，逐字节一致。
- 实际 SBOM 草稿、完整索引和 485 条 NEEDED 关系重新生成，无 unmatched；CycloneDX 1.5 schema 通过。19 份许可集合、115 个 SciPy 库和 14 个 LLVM 静态消费者重新绑定。
- 指定提交干净源码：仓库 Python 92/92；Bridge 28 项中 26 通过/2 跳过；Core 宿主 30/30；JSON、契约与 fixture 校验通过。

[构建收据](../packaging/reviews/c-api23-c47b610/BUILD-RECEIPT.json) · [API/文件差异](../packaging/reviews/c-api23-c47b610/hap-config-diff.json) · [build-profile 源码核对](../packaging/reviews/c-api23-c47b610/build-profile-source-match.json) · [签名核验](../packaging/reviews/c-api23-c47b610/signature-native-verification.json) · [运行时/SBOM/许可绑定](../packaging/reviews/c-api23-c47b610/runtime-sbom-license-binding.json) · [材料审查处置](../packaging/reviews/c-api23-c47b610/material-review.json) · [测试结果](../packaging/reviews/c-api23-c47b610/exact-source-validation.json)

组件/排除范围及社区来源精度限制沿用不变字节的已接受工程审查；自动观察报告中的历史 pending 不构成新的 B 交付要求。新包材料审查与真实文件哈希已绑定，但新包尚无物理复验记录，因此保留实际 SBOM 草稿，不伪造 Finalize-HapSbom.py 所需的同包设备验收。没有声称未知 SciPy 静态归档版本或社区补丁集已恢复。

## 组长下一步：原设备保留数据复验

在原 HAD-W32/API23 安装前记录应用版本、五输入关联、旧文件/任务/笔记及可复核哈希，用 `hdc -t <原设备当前目标> install -r <上述HAP>` 同签名覆盖，**不卸载、不清数据**。版本号相同，按源码和 HAP 哈希确认安装目标。

依次核验：安装/启动与 Core ready；旧数据和五输入保留；PbSO4 真实五阶段；10 个 Rwp + 2 个择优取向系数与 Windows 基线比较；GPX/JSON/日志可发现且经系统选择器实际导出；正常退出重启后同一任务、结果、输入与文件索引恢复。优先取回原始 JSON/导出文件并固定哈希，而非仅记录界面可见。完整步骤在 ZIP 的 README.md 与给组长.txt。

回传本 HAP 哈希、设备/API、执行时间、安装方式、jobId、数值比较与导出/恢复证据后再更新同包结论。原先组长已限定接收的 Core 边界范围保留；如有新异常按实际差异追加回归。旧包断网记录不作为本包直接证据。

C 本轮没有操作真机，`deviceAcceptancePending=true`、`releaseApproved=false`、`publicDistributionApproved=false`。这份指定设备 internaltesting HAP 是验收候选，不能直接当作商店公开分发包。
