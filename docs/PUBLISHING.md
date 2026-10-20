# 发布交接与远端状态

后续状态（2026-10-20）：最近完整签名内测 HAP `791dc53d…` 的工程/SBOM/许可和 API23 显式断网五阶段、UI 临界、[结果页 12 项数值复核](PR17_NUMERIC_UI_ACCEPTANCE_2026-10-20.md)已归档；[Core 三项边界按限定口径接收](LEADER_CORE_BOUNDARY_ACCEPTANCE_2026-10-20.md)，A 旧包已测场景保留为未变组件佐证。组长随后[决定只声明 API23 已验证](API23_SUPPORT_SCOPE_2026-10-20.md)，源码最低兼容版本已改为 API23。旧签名包仍写 API20，须重新构建/签名及 API23 同包关键复验；整包技术放行、公开分发/上架仍待。以下旧 `70588bde…` 和 PR #13/14 叙述是当时快照，见[验收矩阵](RELEASE_ACCEPTANCE.md)。

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

核心移植和旧 0.1.1 内测包工程审查已完成；当前先按[API23 收窄决断](API23_SUPPORT_SCOPE_2026-10-20.md)重建完整签名包、在 API23 同包关键复验，再由组长按[验收矩阵](RELEASE_ACCEPTANCE.md)决定技术放行。放行后，若团队选择 OpenHarmonyPCDeveloper 社区组织路线，由 C 复核[社区申请草稿](GITCODE_APPLICATION.md)并申请建仓；若以自有开发者账号上架，则如实使用实际源码仓库与发布主体，社区建仓不是 AGC 的硬性前置。两条路线均须完成公开分发包和上架审核；迁移到 GitHub 不代表任何申请已经提交。

