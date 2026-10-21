# PR #23：晶衍精析 0.1.3 整包技术审查

日期：2026-10-21。应组长委托，Codex 对 C 交付的公开签名 APP、同载荷设备 HAP、真实设备结果和实际包 SBOM 作代理技术审查。本记录不是组长亲笔签名，也不是应用市场批准。

**结论：晶衍精析 0.1.3/versionCode 4 在 HAD-W32/API23 已验证范围内，整包技术门禁通过，可供 C 准备平台提交。**平台账号资料、名称占用核对、包检测及公开分发审核仍按实际结果办理；API20/API24、其他设备和任意样品不在本结论范围。

## 审查依据

1. C 的[签名交付](C_RENAME_0_1_3_SIGNED_HANDOFF.md)绑定精确源码 `8b64bf6ebefa2b4e609f962e926c294e084b6d52`，公开 APP `89e6b3e4…`、独立公开 HAP `cf31a9ff…`、设备 HAP `60fca45b…`、完整 ZIP `f4fe13ff…`。本机取得 Git LFS 实体后独立重算 APP、设备 HAP 和 ZIP 的 SHA-256；C 的签名/原生代码签名、APP 内嵌 HAP 与设备包内容关系见[收据](../packaging/reviews/c-rename-0.1.3/BUILD-RECEIPT.json)、[签名证明](../packaging/reviews/c-rename-0.1.3/signature-native-verification.json)和[设备对应证明](../packaging/reviews/c-rename-0.1.3/device-counterpart-verification.json)。最终审查器再次逐个比较两份独立 HAP 的 ZIP 成员，检查真实 APP 内嵌 HAP 的差异边界。设备 HAP 使用原证书身份成功覆盖旧包。
2. [新包同设备关键复验](PR23_0_1_3_DEVICE_RETEST_2026-10-21.md)确认 0.1.2/3→0.1.3/4 保留数据升级、UID/首次安装时间/签名指纹保持、窗口与本机应用搜索显示“晶衍精析”、55 项旧文件和旧结果保留。新任务真实五阶段、结果页 **12/12** 独立数值比较、GPX/JSON/日志经系统保存且再次可发现、正常退出重启恢复通过；取消、无效 CIF 失败、活动关闭保护和最小窗口也在此包实测。[十张新名称截图](A_RENAME_0_1_3_DEVICE_SCREENSHOTS_2026-10-21.md)固定各场景；旧 A 照片继续按旧 HAP 哈希保留，不充作本包实拍。
3. 对 C 的[实际材料复核](../packaging/reviews/c-rename-0.1.3/material-review.json)与[运行时/许可绑定](../packaging/reviews/c-rename-0.1.3/runtime-sbom-license-binding.json)，用明确逐组件决策重新运行 `Build-StoreFinalReview.py --candidate 0.1.3` 和 `Finalize-HapSbom.py`。工具核对当前 HAP 的每个 ZIP 成员、签名包对应关系、物理验收哈希、219 个 ELF 与 485 条 NEEDED、19 份许可集合和全部审查发现，成功形成两份**最终 CycloneDX SBOM**：[独立公开 HAP](../packaging/reviews/c-rename-0.1.3-final/public-hap-sbom.cdx.json)（2266 文件，SHA-256 `380df78f1532eaa7fa2e51357e9ea45d74ae066e402fd76510ad4465e3f196c3`）与[真实 APP 内嵌 HAP](../packaging/reviews/c-rename-0.1.3-final/store-app-embedded-hap-sbom.cdx.json)（2265 文件，SHA-256 `3465f162ce903a005077505a5968fa19c2f63c6e68f6090ef53d10f10072bb8a`）。两份[逐项决策](../packaging/reviews/c-rename-0.1.3-final/public-hap-review-decisions.json)、[APP 内嵌决策](../packaging/reviews/c-rename-0.1.3-final/store-app-embedded-hap-review-decisions.json)均固定输入/证据哈希，显式保持 `publicDistributionApproved=false`。[结构化总结](../packaging/reviews/c-rename-0.1.3-final/review-summary.json)记录边界。

## 边界与后续

- 页面 12 项数值比较包含五位小数显示的舍入上界；导出文件通过系统选择器保存并重新发现，**未取回原始字节**，不宣称 JSON 全精度或产物哈希通过。取消/失败日志本次确认登记与导出入口，没有逐件做字节级导出复核。
- 0.1.2 当时因设备未联网出现的系统校验提示仍属于该历史包的观察；本次 0.1.3 覆盖升级未观察到相同提示。原本已接受的社区预编译来源精度限制继续如实保留，不虚构上游构建日志。
- 已实测设备包为原 internaltesting Profile；公开 APP 的真实 AppGallery 上传、平台检测、安装和审核均未发生。C 应用实际账号核对“晶衍精析”名称可用性、分类、隐私政策地址、维护者/反馈入口及最终图片规格，再上传哈希为 `89e6b3e4…` 的公开 APP，保存受理编号和平台反馈。只有平台批准后才更新 `platformApproved` / `publicDistributionApproved`。

复核命令：解压固定交付 ZIP，以 `python scripts/Build-StoreFinalReview.py --candidate 0.1.3 --repo . --delivery <解包目录> --output <新审查目录>` 生成两份决策；再以相应 HAP、`runtime-manifest.json`、draft、第三方报告、决策文件及解包目录分别调用 `scripts/Finalize-HapSbom.py`。构建审查时只在本地解包目录加入设备记录副本和 APP 内嵌 HAP，不更改原 ZIP。最终 SBOM 的技术审查状态不自动授予平台公开分发权限。
