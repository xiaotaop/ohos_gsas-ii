# 发布交接与远端状态

当前改名候选（2026-10-21）：**晶衍精析 0.1.3/versionCode 4** 的完整运行时未签名 HAP 已构建；[C 签名交接](RENAME_0_1_3_HANDOFF_2026-10-21.md)明确公开 APP、原设备 HAP、覆盖安装和真机名称显示仍待。上架材料草稿已切到新名称，旧 0.1.2 APP 不应当作新候选上传。平台未提交，公开分发未批准。

0.1.2 旧哈希结论（2026-10-21）：**GSAS-II 0.1.2 / versionCode 3** 的 `release/app_gallery` 公开 APP `dd173f66…` 及同内容设备复验 HAP `78efbb58…` 已[交付](C_STORE_PACKAGE_0_1_2.md)。后者在原 HAD-W32/API23 完成[保留数据升级与关键真机复验](PR21_0_1_2_DEVICE_RETEST_2026-10-21.md)，[限定范围整包技术审查](PR21_0_1_2_TECHNICAL_RELEASE_REVIEW_2026-10-21.md)通过；这些结论不自动转移至 0.1.3。下方更早内测结论均保留作历史。

历史状态（2026-10-20）：内测 HAP `791dc53d…` 的工程/SBOM/许可和 API23 显式断网五阶段、UI 临界、[结果页 12 项数值复核](PR17_NUMERIC_UI_ACCEPTANCE_2026-10-20.md)已归档；[Core 三项边界按限定口径接收](LEADER_CORE_BOUNDARY_ACCEPTANCE_2026-10-20.md)，A 旧包已测场景保留为未变组件佐证。组长随后[决定只声明 API23 已验证](API23_SUPPORT_SCOPE_2026-10-20.md)，源码最低兼容版本已改为 API23。该包仍写 API20，当时尚须重建及 API23 同包复验；这些工作后来已完成，0.1.2 公开签名候选亦已交付。平台审核仍待。以下旧 `70588bde…` 和 PR #13/14 叙述均为当时快照，见[验收矩阵](RELEASE_ACCEPTANCE.md)。

## 当前协作仓库

2026-10-20 核对：主仓库为 <https://github.com/xiaotaop/ohos_gsas-ii>，默认分支 `main`。PR #13 提交 0.1.1 指定设备内测 HAP 的同包验收与最终工程审查；PR #14 的 A 页面修复在其后合入，但**不在该 HAP 中**。后续开发仍建议成员分支、CI、组长审核后合并；源码合并不改变发布门禁。

PR #13/14 阶段的指定设备 `release/internaltesting` HAP `70588bde…` 已有 C 阶段三真机与 SBOM/许可工程证据；当时仍需 A 页面修复、B 专项和新包复验。当前新包进度以上方状态与[发布验收矩阵](RELEASE_ACCEPTANCE.md)为准，旧包结论**不是公开应用商店分发签名或上架批准**。建仓是否需要取决于团队选择社区组织还是自有开发者账号路线；GitCode 个人仓库不是自动镜像，当前主线状态应以 GitHub 为准。

以下为 2026-10-14 迁移时的历史记录：

- 核对时 `main` 为 `12db7e78cf689ef032438139d6819d76fd1a7c99`。
- A 的 `6605e13`、`de5165c` 已由 `f494f61` 合入；B 的 `a3d197e` 已由 `55f79de` 合入；后续集成修正为 `fce47af`。
- 原 GitCode PR #1 是历史审核入口；当时 GitHub 尚无迁移后的 PR 记录。后来已通过 GitHub PR 协作，不需要重新为已合入的 M1 代码开 PR。
- 该主线的 [Repository verification](https://github.com/xiaotaop/ohos_gsas-ii/actions/runs/38397057616) 已通过。CI 范围见 [持续集成说明](CI.md)，不包含真机 GUI、N-API/嵌入式运行时或签名发布验收。

本次本地 checkout 已将 `origin` 更新为 GitHub HTTPS 地址，并把旧远端保留为 `gitcode-archive`。这只描述本 checkout 的配置；其他成员需核对各自配置，不能沿用旧文档中的 SSH 密钥或直推主线步骤。

```powershell
git remote -v
git fetch origin
# 在自己的开发分支完成提交后：
git push -u origin HEAD
git rev-parse HEAD
git ls-remote origin "refs/heads/$(git branch --show-current)"
```

后两条的提交 SHA 应一致。随后在 GitHub 发起成员分支到 `main` 的 PR。若存在同一分支的 PR，后续提交更新该 PR，不重复创建。推送成功、CI 通过与组长审核通过分别记录。

## GitCode 与社区申请历史

2026-10-12 创建的个人公开 GitCode 暂存仓库为 <https://gitcode.com/2401_86708491/ohos_gsas-ii>。它不是 `OpenHarmonyPCDeveloper` 社区组织仓库；保留地址用于追溯，不假定两端会自动同步。本次没有修改旧仓库设置或关闭旧 PR。

核心移植、旧 0.1.1 内测包及 0.1.2 公开签名候选在[API23 收窄范围](API23_SUPPORT_SCOPE_2026-10-20.md)内的工程审查已完成；0.1.2 结论以[旧哈希审查记录](PR21_0_1_2_TECHNICAL_RELEASE_REVIEW_2026-10-21.md)为准。当前 0.1.3 改名候选仍待 C 签名和新包核验；团队既定采用自有开发者账号路线，C 可按[新上架材料草稿](C_LISTING_DRAFT.md)准备账号、描述、隐私和素材，并如实填写当前源码仓库；社区建仓不是该路线的前置。若日后另选 OpenHarmonyPCDeveloper 社区组织路线，再由 C 更新[社区申请草稿](GITCODE_APPLICATION.md)并申请建仓。两条路线均须完成平台检测和上架审核；GitHub PR 的合并不代表已提交申请。

