# 发布交接与远端状态

## 当前协作仓库

2026-10-20 核对：主仓库为 <https://github.com/xiaotaop/ohos_gsas-ii>，默认分支 `main`；PR #9（指定设备签名 HAP 与源码伴随包）已合入，合并提交 `7f17cb25842fedef889c4a9c64a8ea3b963b47d4`，[对应 GitHub CI](https://github.com/xiaotaop/ohos_gsas-ii/actions/runs/39358497372) 通过。后续开发仍建议成员分支、CI、组长审核后合并。本次文档统一更新不改变发布门禁。

当前拥有的是指定设备 `release/internaltesting` 签名 HAP 的安装和成功路径证据，**不是公开应用商店分发签名或上架批准**。C 负责最终 SBOM/许可、公开分发包、社区建仓与上架申请；A 补正式同包 UI 边界及截图；B 协助核实预编译第三方依赖；组长决定 API 覆盖和技术放行。具体门禁见[发布验收矩阵](RELEASE_ACCEPTANCE.md)。GitCode 个人仓库不是自动镜像，当前主线状态应以 GitHub 为准。

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

核心移植和指定设备成功路径已完成；当前先关闭[验收矩阵](RELEASE_ACCEPTANCE.md)的第三方分发审查及剩余同包测试。技术放行后由 C 复核[社区申请草稿](GITCODE_APPLICATION.md)、重名仓库与许可证，再按社区流程申请组织仓库并提交上架。迁移到 GitHub 不代表已提交或通过社区建仓、应用上架申请。

