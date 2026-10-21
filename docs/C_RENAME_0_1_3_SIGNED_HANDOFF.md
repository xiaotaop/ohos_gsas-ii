# C：晶衍精析 0.1.3 签名交付与签名后真机复验

2026-10-21。按[组长改名交接](RENAME_0_1_3_HANDOFF_2026-10-21.md)的精确源码 `8b64bf6ebefa2b4e609f962e926c294e084b6d52`，C 已重建/签名完整 `release/app_gallery` APP 与原 HAD-W32 `release/internaltesting` 设备 HAP。**签名交付完成后，组长还需在原真机安装一次新包，验证升级与“晶衍精析”名称。**当前没有执行本哈希的真机安装或平台上架。

## 固定产物

显示名 **晶衍精析**，版本 **0.1.3 / versionCode 4**，`bundleName=com.gsasii.desktop` 不变，最低 API23、目标 API24。C 沿用组长源码，不改写其业务实现；本 PR 同时携带改名分支的既有源码/交接与 C 的签名材料，以便一并审核。

| 文件 | SHA-256 | 字节 | 用途 |
| --- | --- | --- | --- |
| JingyanJingxi-0.1.3-app-gallery.app | `89e6b3e47afba2a17d01696cea6c6b6333a7edeb8a1bab58ab18f1b6ff4ddafd` | 45423701 | app_gallery 平台上传候选 |
| JingyanJingxi-0.1.3-app-gallery.hap | `cf31a9ff88ba8a7fe26c7fbf03de9b5ddfd2356f6d49f76d2328542c68f1c726` | 135971244 | 公开 Profile 独立模块，ZIP 内 |
| JingyanJingxi-0.1.3-device-internaltesting.hap | `60fca45be125e825169b7fef90669cf76a0ef490adeeed1acd28f8ee1a9b94a7` | 135971296 | 原真机保留数据覆盖安装，ZIP 内 |
| 完整签名交付 ZIP | `f4fe13ff7b8a22db37d625b5db2cdeb54e84ce1351fe106ccfec799bc6b81858` | 178851210 | 三个包、源码/SBOM/许可和复验步骤 |

[公开签名 APP](../deliveries/JingyanJingxi-0.1.3-app-gallery.app) · [完整签名交付 ZIP](../deliveries/c-jingyanjingxi-0.1.3-8b64bf6e.zip) · [下载大小/哈希](../packaging/reviews/c-rename-0.1.3/download.json)

文件经 Git LFS 保存，GitHub 文件页使用 **Download raw file** 下载实体，不把文本指针当安装包。ZIP 中 `给组长-0.1.3安装复验.md` 与 README.md 提供命令和检查项。

## 本次已核验

- DevEco Release 构建成功；公开 APP 外层签名、公开 HAP/原生 codesign 和设备 HAP 验证通过。原发布证书链一致；公开 Profile 仍为 app_gallery，设备 Profile 是此前已使用的原 internaltesting。未更换应用身份；私钥、密码、独立证书/Profile 不公开。
- 50 个实际 app 源文件与精确提交及源码伴随相同，build-profile 除本地签名配置外与源码一致；全部939个源码伴随成员哈希通过。源码 Python94/94、Bridge26通过/2跳过、Core宿主30/30，JSON/契约/fixture校验通过。
- 对 C 的实际0.1.2/0.1.3签名HAP逐项比较，只有 **module.json、pack.info、resources.index** 改变，具体路径/大小/前后哈希见[差异记录](../packaging/reviews/c-rename-0.1.3/rename-byte-diff.json)。2245运行时文件、219 ELF、应用字节码及许可条目全部不变。名称资源实际含UTF-8“晶衍精析”。该比较不改写组长另一份未签名构建记录。
- 两份独立HAP所有ZIP成员字节相同，仅签名信封/Profile不同。公开APP内嵌HAP为2265文件、独立HAP2266：打包器省去.pages.info并等价重排pack.info JSON，其余共有内容相同；两份实际SBOM分别绑定。
- 实际APP及独立HAP各自生成SBOM草稿、完整索引与原生图，均219 ELF、485 NEEDED、无unmatched，CycloneDX1.5 schema通过。19份许可集合/40许可文件、115 SciPy库/14 LLVM静态消费者和两个源码伴随已重绑；来源精度限制沿用既有接受口径，不虚构未知社区构建日志。
- ZIP 含三包、两份源码伴随、完整通知/许可、运行时清单、两份实际SBOM、签名/差异/同内容证明、五输入和Windows基线；全部归档成员重新核对SHA-256。

[构建收据](../packaging/reviews/c-rename-0.1.3/BUILD-RECEIPT.json) · [APP 容器核验](../packaging/reviews/c-rename-0.1.3/store-app-verification.json) · [同内容设备包证明](../packaging/reviews/c-rename-0.1.3/device-counterpart-verification.json) · [签名证明](../packaging/reviews/c-rename-0.1.3/signature-native-verification.json) · [实际SBOM/许可绑定](../packaging/reviews/c-rename-0.1.3/runtime-sbom-license-binding.json) · [材料审查](../packaging/reviews/c-rename-0.1.3/material-review.json) · [测试](../packaging/reviews/c-rename-0.1.3/exact-source-validation.json)

## 组长必须在本次签名后完成

原HAD-W32/API23留存当前0.1.2/3和旧文件/任务/输入/笔记基线后，核对新设备HAP哈希并执行保留数据覆盖安装：

```text
hdc -t <原设备当前目标> install -r JingyanJingxi-0.1.3-device-internaltesting.hap
hdc -t <原设备当前目标> shell aa start -a EntryAbility -b com.gsasii.desktop
```

不卸载、不清数据。确认版本0.1.3/4、原证书/包名、旧数据保留，系统应用列表/桌面入口及启动后任务栏显示 **晶衍精析**，Core ready与关键五阶段正常；按实际差异复核数值、导出和退出重启恢复。应用内许可、日志及上游介绍中的GSAS-II是保留的来源标记，不是桌面改名失败。失败时记录错误，不绕过签名或来源校验。

回传实际安装HAP哈希、设备/API、时间、桌面/任务栏名称、版本/升级和工作流证据后，再形成该精确包的最终SBOM/设备审查。旧0.1.2结果只能作旧哈希或未变组件佐证，不能直接赋给新包。公开APP供平台上传，设备包实测不等于公开APP已通过平台分发/安装审核。

当前 `signedPackageReady=true`、`deviceUpgradeAndDisplayVerified=false`、`newHapPhysicalAcceptancePending=true`、`platformSubmitted=false`、`publicDistributionApproved=false`。名称后台可用性及上架账号资料仍须在正式提交前按实际结果核对；产品说明保留“基于GSAS-II的非官方HarmonyOS PC移植”，不暗示上游背书。功能图按既定决定沿用旧图并标注来源。
