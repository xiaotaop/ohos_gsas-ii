# API23 内测候选整包技术审查结论

日期：2026-10-21。应组长要求，Codex 审核并合并 [PR #20](https://github.com/xiaotaop/ohos_gsas-ii/pull/20)，随后对其实际签名 HAP `d65a64a90cba7d029d43b7549c626903ccf1080a6f5b4aa8a70f77148909b25b` 做原设备关键复验和整包材料审查。此处是**代理技术审查记录**，不冒充组长亲笔签名，也不授予商店公开分发权限。

结论：**该精确 HAP 在 HAD-W32/API23 的限定内测范围，整包技术验收通过，可以进入公开分发包准备与上架材料阶段。** 不扩展到 API20/API24、其他机型、任意科学样品或全部 GSAS-II 功能。

## 通过依据

1. PR #20 可快进合并，CI 通过，`git diff --check` 无问题；仓库交付 HAP 与完整 ZIP 的 SHA-256 分别为 `d65a64a9…09b25b`、`144eb5a5…8929`，ZIP 中 22 项 `SHA256SUMS` 全部重算一致。新旧 HAP 对比仅 `module.json` 和 `pack.info` 的最低兼容 API 声明变化，应用字节码、完整运行时和许可文件不变；C 的精确源码、签名、219 ELF/八扩展、许可及来源精度限制审查有独立收据。
2. [本 HAP 的真机记录](PR20_API23_DEVICE_ACCEPTANCE_2026-10-21.md)确认：保留数据同版本覆盖、Core 就绪、五输入保留、新任务真实五阶段 8.78 秒、10 个 Rwp 加 2 个择优取向值相对 Windows 基线 12/12 通过、GPX/JSON/日志三文件经系统选择器保存并重新发现、正常退出后结果及 52 项文件库恢复。原始界面布局只在本机忽略目录，公开记录只存哈希及最小观察。
3. 使用 C 实际 ZIP 中的 HAP、运行时清单、CycloneDX 草稿、第三方观察报告和完整通知材料，结合[同包物理验收记录](../packaging/reviews/c-api23-final/physical-acceptance.json)与[逐项审查决策](../packaging/reviews/c-api23-final/review-decisions.json)，运行 `Finalize-HapSbom.py` 成功。最终 [CycloneDX 1.5 SBOM](../packaging/reviews/c-api23-final/hap-sbom.cdx.json) SHA-256 为 `26a3bf463761136076ed49bbcdd3091f2388626c3721e83e938ad4de6bdbed2c`，2266 个实际文件、31 个非文件组件（其中 4 个明确为未随包分发的平台项），原生依赖无未匹配名称；该工具对应 15 项单测通过。最终化仅关闭**该内测 HAP 的工程审查**，SBOM 内 `releaseApproved=false` 和 `publicDistributionApproved=false` 保持真实。

## 明确保留的边界

- 本次设备上最初出现过系统联网验证提示；关闭提示后独立结束进程并冷启动成功。不能据此承诺所有首次安装/离线环境均无系统提示。公开分发包的安装体验和公开签名须另行验收。
- 三件导出文件由系统选择器保存、再次打开文件夹可见，但 HDC 未取回原始字节；数值结论仅为设备**结果页**独立比较，不是导出 JSON 的全精度字节比对。应用页面本身显示“本次未执行基线校验”。
- A 在旧包的截图和已测场景按组长既定“未变组件佐证”范围沿用；本次不伪称旧截图来自新哈希。Core 三项边界继续按既定限定口径接收，不提升为真机内部专项直接证明。
- 社区预编译来源/版本精度限制如实保留；此审查不凭空恢复 SciPy 静态归档精确版本或不存在的构建日志。
- 这是 `release/internaltesting` 指定设备包，同版本号 `0.1.1` / versionCode `2`。公开上架仍须确定正式版本及递增策略、公开分发签名/包、上架主体与维护者、隐私/描述/截图材料并走平台审核。未提交上架，也未声称平台已批准。

结构化[审查摘要](../packaging/reviews/c-api23-final/review-summary.json)固定上述哈希与状态。重现最终 SBOM：从交付 ZIP 解包，执行 `python -X utf8 scripts/Build-Api23FinalReview.py --repo . --delivery <解包目录> --output <新review-decisions.json>`，再以同目录 HAP/manifest/draft/report、生成决策及解包目录为 `--evidence-dir` 调用 `scripts/Finalize-HapSbom.py`。脚本拒绝覆盖已有输出；它不会将工程审查转成商店发布许可。
