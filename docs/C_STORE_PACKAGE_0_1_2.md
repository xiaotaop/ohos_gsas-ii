# C：第一项新包审核交接（0.1.2 / 3）

2026-10-21。用户确认正式候选名 **GSAS-II**、版本 **0.1.2 / versionCode 3**，按自有华为开发者账号路线准备。此交付仅覆盖第一项：公开分发签名候选与组长新包审核；C 的构建/签名/材料准备完成，**组长新版本设备复验及平台检测仍待**。不把旧 `d65a64a9…` 内测验收结果赋给新哈希。

## 固定产物

精确构建源码：`01e38b56a437e8a8d27cb5ae1f3c821d5aad3fad`。相比已验收 API23 主线，应用源码仅将 app.json5 的 versionName/versionCode 从 0.1.1/2 递增到 0.1.2/3；名称 GSAS-II、包名 com.gsasii.desktop、最低 API23/目标 API24 均保持。目标 API24 不代表 API24 实机通过。

| 产物 | SHA-256 | 字节 | 用途 |
| --- | --- | --- | --- |
| GSAS-II-0.1.2-app-gallery.app | `dd173f669b3b037726ce64b148d44fe7b4de5881ef7ac923ebe6c3704d917959` | 45423561 | release/app_gallery 平台上传候选 |
| GSAS-II-0.1.2-app-gallery.hap | `4ac884840e8940e12641d07e0e5ca8e66f7c5222e356fa3ef1aef6925d5d3519` | 135971288 | 公开 Profile 独立模块留档，在 ZIP 内 |
| GSAS-II-0.1.2-device-internaltesting.hap | `78efbb58ee3a7d970c4d432cffe376d6256546952449d656da59f7f6ba1fd33f` | 135971346 | 原 HAD-W32 的保留数据新版本复验，在 ZIP 内 |
| 完整审核 ZIP | `faa3ae829998941901e336fe8f57a1e91ce8feb7bc4cbebc40b9414e6a5aa9fc` | 178496964 | 三个包、源码/SBOM/许可及复验步骤 |

[公开签名 APP](../deliveries/GSAS-II-0.1.2-app-gallery.app) · [第一项完整审核 ZIP](../deliveries/c-store-package-0.1.2-01e38b56.zip) · [下载大小/哈希](../packaging/reviews/c-store-0.1.2/download.json)

通过 Git LFS 保存；GitHub 文件页点击 Download raw file 下载实际文件，不要把 LFS 指针当包。ZIP 中 README.md / 给组长-新包审核.md 提供可执行的审核步骤。未包含上架文案、隐私或账号填写材料；已起草部分另留本地。

## C 的审核准备结果

- DevEco Release 产品级 assembleApp 和模块级 HAP 构建成功，公开 APP 外层签名、公开 HAP 与设备 HAP 的 SDK 验证通过。使用原发布证书，公开候选采用本机已有 `release/app_gallery` Profile、设备复验包采用原 HAD-W32 `release/internaltesting` Profile，证书链一致。只发布指纹与结果，不上传私钥、密码、独立证书/Profile。
- 50 个实际 app 文件与精确提交和源码伴随匹配；build-profile 剥除本地签名配置后与源码一致，源码伴随全部 916 个成员哈希通过。干净源码仓库 Python 92/92，Bridge 26 通过/2 跳过，Core 宿主 30/30；JSON、契约和 fixture 校验通过。
- 两份独立 HAP 的全部 ZIP 条目字节相同，仅 HAP 签名信封和 Profile 不同。公开 APP 内 entry-default.hap 为 **2265 文件**，独立 HAP 为 **2266 文件**：打包器移除 `.pages.info` 并等价重排 pack.info JSON 格式；其余共享条目完全一致。按实际容器分别生成 SBOM，不混用哈希或文件数。
- 完整运行时 2245 文件、219 ELF、八个扩展、485 NEEDED 关系齐全，无未匹配名称。219 ELF 和40个许可文件与已审查 d65a64a9 参考包逐字节一致；19 份许可集合、115 个 SciPy 原始库和14个LLVM静态消费者重新绑定。社区来源精度限制保持已接受口径，不要求 B 重交不存在的日志。
- ZIP 完整包含公开 APP、两个独立 HAP、实际两份 SBOM 草稿/文件索引/原生图、运行时清单、两个源码伴随、版权通知全文、签名/同内容证明、公开 PbSO4 五输入及 Windows 基线。归档成员逐项核对 SHA-256。

[构建收据](../packaging/reviews/c-store-0.1.2/BUILD-RECEIPT.json) · [公开 APP 容器核验](../packaging/reviews/c-store-0.1.2/store-app-verification.json) · [同内容设备包证明](../packaging/reviews/c-store-0.1.2/device-counterpart-verification.json) · [签名证明](../packaging/reviews/c-store-0.1.2/signature-native-verification.json) · [实际 SBOM/许可绑定](../packaging/reviews/c-store-0.1.2/runtime-sbom-license-binding.json) · [材料审查](../packaging/reviews/c-store-0.1.2/material-review.json) · [测试](../packaging/reviews/c-store-0.1.2/exact-source-validation.json)

## 组长下一步审核

核对 ZIP 的 SHA256SUMS。在原 HAD-W32/API23 记录旧版本、五输入、文件/任务/笔记基线，用 `hdc -t <原设备当前目标> install -r GSAS-II-0.1.2-device-internaltesting.hap` 同证书覆盖安装，**不卸载、不清数据**。依次核对 0.1.1/2→0.1.2/3 升级、启动/Core ready、旧数据和五输入、PbSO4真实五阶段及12项独立数值、GPX/JSON/日志实际导出、正常退出重启恢复。优先读回原始JSON及导出文件哈希。完整命令、样例和容差在 ZIP 交接说明中。

组长回传实际安装 HAP 哈希、设备/API、时间、jobId、数值及导出/恢复证据后，再更新该哈希的设备结论。APP供平台上传；设备复验包证明同有效载荷的设备流程，不等于公开APP已取得平台检测/分发审核通过。正式商店分发的安装体验仍以平台流程和实际结果为准，不绕过系统签名/来源校验。

此新版本未由 C 操作真机；两份实际 SBOM 保持草稿并附材料审查，不能伪造物理验收来最终化。`leaderDeviceAcceptancePending=true`、`platformSubmitted=false`、`publicDistributionApproved=false`。本 PR 不是平台上架申请。

官方[提交 HarmonyOS 应用](https://developer.huawei.com/consumer/cn/app/submit)说明 APP 上架容器；[工程级 build-profile](https://developer.huawei.com/consumer/cn/doc/doccenter-deveco-studio/ide-hmos-hvigor-build-profile-app)说明产品包和模块签名选项，实际生成内容以本交付的容器收据为准。
