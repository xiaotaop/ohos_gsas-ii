# 发布交接与远端状态

## 当前协作仓库

2026-10-14 核对：主仓库已迁移至 <https://github.com/xiaotaop/ohos_gsas-ii>，默认分支为 `main`。后续开发使用成员分支，通过 GitHub Pull Request 交由组长审核合并，不直接推送 `main`。

- 核对时 `main` 为 `12db7e78cf689ef032438139d6819d76fd1a7c99`。
- A 的 `6605e13`、`de5165c` 已由 `f494f61` 合入；B 的 `a3d197e` 已由 `55f79de` 合入；后续集成修正为 `fce47af`。
- 原 GitCode PR #1 是历史审核入口。GitHub 当前没有迁移后的 PR 记录，但上述提交均在 `main` 历史中；不需要重新为已合入的 M1 代码开 PR。
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

当前仍先完成核心移植、真机集成和可分发物审查。开发完成后复核 [社区申请草稿](GITCODE_APPLICATION.md)、重名仓库及许可问题，再按社区流程申请组织仓库并进入上架审核。迁移到 GitHub 不代表已经提交或通过社区建仓、应用上架申请。

