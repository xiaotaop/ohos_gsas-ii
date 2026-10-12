# 发布交接与远端状态

2026-10-12 已在当前登录账户 `2401_86708491` 下创建个人公开 GitCode 暂存仓库：<https://gitcode.com/2401_86708491/ohos_gsas-ii>。该仓库不是 `OpenHarmonyPCDeveloper` 社区组织仓库，也不代表应用已上架。

本地 `origin` 已切换为 SSH 地址，并为本仓库指定 GitCode 专用 ED25519 密钥。首次 HTTPS 推送因密码式认证被禁用而失败；添加 SSH 公钥后已解决。

后续在本目录运行：

```powershell
git push -u origin main
git ls-remote origin refs/heads/main
git rev-parse HEAD
```

后两条的提交 SHA 应一致。首次推送已执行一致性检查；后续发布仍应复查，并在浏览器确认 `README.md`、`README.OpenSource`、`LICENSE`、`docs/` 和 `tests/fixtures/` 均可见。

接着根据 `GITCODE_APPLICATION.md` 在社区 `community` 仓库提出 NewRepository 申请。申请前复查重名仓库和许可问题，社区批准后再按其流程向组织仓库贡献。应用上架另走应用市场审核；第一阶段没有提交任何上架申请。

