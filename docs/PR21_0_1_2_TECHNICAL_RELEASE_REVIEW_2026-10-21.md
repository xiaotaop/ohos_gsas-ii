# PR #21：0.1.2 公开候选整包技术审查

日期：2026-10-21。应组长要求，Codex 对 C 的公开签名候选及同载荷设备复验结果作代理技术审查。本记录不是组长亲笔签名，也不是应用商店批准。

**结论：GSAS-II 0.1.2 / versionCode 3 在 HAD-W32/API23 已验证范围内，整包技术门禁通过，可以合并 PR #21 并由 C 准备上架材料。**正式平台提交、包检测与公开分发仍未发生；API20/API24、其他设备和任意样品不在通过范围。

## 审查依据

1. 精确构建源码 `01e38b56a437e8a8d27cb5ae1f3c821d5aad3fad` 对比已验收 API23 内测源码仅递增版本名/码。实际公开 APP `dd173f66…`、独立公开 HAP `4ac88484…`、设备 HAP `78efbb58…`、交付 ZIP `faa3ae82…` 固定；ZIP 的 `SHA256SUMS` 39/39 重算一致，Git LFS 实体可取得。C 的 SDK 签名/原生代码签名收据通过，设备包在原设备同证书保留数据升级成功。以上只证明当前包签名与交付完整性，不等于平台已接受公开 APP。
2. [同载荷设备关键复验](PR21_0_1_2_DEVICE_RETEST_2026-10-21.md)在 HAD-W32/API23 确认 0.1.1/2→0.1.2/3 升级、UID/首次安装时间及旧文件/结果保留、Core 就绪、真实 PbSO4 五阶段、结果页 12/12 独立数值比较、三类系统选择器导出可发现及正常退出重启恢复。旧 A 包截图仅按已接受的未变组件边界沿用，不称其为新哈希实拍。
3. `Finalize-HapSbom.py` 按明确审查决策重新审计两份实际内容：独立公开 HAP 的 [最终 CycloneDX SBOM](../packaging/reviews/c-store-0.1.2-final/public-hap-sbom.cdx.json)（2266 文件，SHA-256 `ab5558166ecaf3d5e93d9d56c7e5b9a1a080c359146f13277164f8ad1aa069cc`）和真正上传 APP 内嵌 HAP 的 [最终 SBOM](../packaging/reviews/c-store-0.1.2-final/store-app-embedded-hap-sbom.cdx.json)（2265 文件，SHA-256 `7f2a4b07c200c021ffa2be6b167e0de54f3feae2383438a457c2bceb04614699`）。工具逐条验证实际成员、原生依赖、许可哈希、完整通知、材料审查及设备包对应关系：两份独立 HAP 的全部 ZIP 成员字节相同；APP 内嵌 HAP 仅省去 `.pages.info`、`pack.info` 发生等价 JSON 格式重排。31 个最终非文件组件、219 个 ELF、485 条 NEEDED 关系及 C 已说明的社区来源精度限制按新哈希保留。最终 SBOM 均显式保持 `publicDistributionApproved=false`。
4. [结构化审查摘要](../packaging/reviews/c-store-0.1.2-final/review-summary.json)及两份[独立 HAP 决策](../packaging/reviews/c-store-0.1.2-final/public-hap-review-decisions.json)、[APP 内嵌 HAP 决策](../packaging/reviews/c-store-0.1.2-final/store-app-embedded-hap-review-decisions.json)记录哈希和审查范围。新增对应关系校验负例与既有最终 SBOM 测试通过；仓库 JSON 校验通过。

## 已接受的边界与未完成的外部流程

- 首次系统联网验证提示如实保留在[真机原始观察](PR21_0_1_2_DEVICE_RETEST_2026-10-21.md)。设备当时没有默认路由，组长明确认定为其设备未联网，并决定**不将其列为本次技术放行阻断、不追加复测**。本决断不改写为“从未出现提示”或“公开 APP 平台安装已通过”。
- 三件导出在系统选择器保存并重新发现，但未取回原始字节；页面 12 项数值独立比较通过，不能扩写为导出 JSON 全精度字节比对。沿用此前限定验收口径，继续如实标注。
- 仅声明 API23 已验证。无需 API20/API24 真机补测来扩大本次范围；后者也不能因目标 API24 元数据而自动视为通过。社区预编译来源精度限制沿用既定接受结论，不凭空补造上游构建日志。
- C 仍须更新 0.1.2 的上架文案、隐私和维护者/反馈资料，按选定账号路线提交真实公开 APP，保存平台检测、受理与审核结果。**技术门禁通过 ≠ 平台提交或公开分发批准。**

复现工程审查：解压固定交付 ZIP，运行 `python -X utf8 scripts/Build-StoreFinalReview.py --repo . --delivery <解包目录> --output <新审查目录>`，再分别用该目录的两个决策文件及原 ZIP 中对应的 HAP/manifest/draft/third-party 报告调用 `scripts/Finalize-HapSbom.py`。构建审查脚本会在解包目录生成用于审查的设备证据副本和 APP 内嵌 HAP；这些中间文件不回写原交付 ZIP。最终工具始终不自动授予平台公开分发权限。
