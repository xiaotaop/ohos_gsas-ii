# 0.1.3 桌面显示名变更与 C 签名交接

日期：2026-10-21。用户要求将已安装时显示的“GSAS-II”改为具有区分度的新名称，并在 C 用原签名身份交付后，才在原 HAD-W32 上保留数据覆盖安装、复核桌面名称。**目前只完成源码改名及完整运行时未签名构建；尚无 0.1.3 正式签名 APP/HAP、覆盖安装或新包技术放行。**

## 名称及范围

- 新显示名：**晶衍精析**，意指晶体衍射图谱的精修分析。公开网页以及 GitHub/GitCode 的精确名称初筛未见同名软件；搜索结果不等于应用市场占名、商标或全网唯一性保证。C 在上架账号后台提交前仍须核对名称可用性，并完成必要的权利核查。上架说明应写明“基于 GSAS-II 的非官方 HarmonyOS PC 移植”，不得暗示上游机构背书。
- [应用资源](../app/AppScope/resources/base/element/string.json)中的 `app_name` 改为“晶衍精析”。[应用元数据](../app/AppScope/app.json5)递增为 `versionName=0.1.3`、`versionCode=4`，`bundleName=com.gsasii.desktop` 不变，以保留原应用的覆盖升级路径。入口 Ability 的标签和应用标签均引用同一 `app_name`；许可证、日志和应用内“GSAS-II”字样保留用于标明上游来源，不是桌面显示名。
- 0.1.2/3 的已签名 APP `dd173f66…` 和设备 HAP `78efbb58…` 仍是此前已审查的**历史字节**。版本、资源和重编译产物变化后，不能复用它们的签名、哈希、SBOM 或“已真机安装”的陈述。

## 未签名构建（非上架产物）

从 0.1.2 已审查公开 HAP 和 `runtime-manifest.json` 按 2245 项目标路径、大小及 SHA-256 还原运行时；`scripts/Extract-RuntimePayloadFromHap.py` 不提取或复制包签名。基于该载荷执行 DevEco CLI 1.3.5 的 Release 构建及 ArkTS 检查：14 个 ArkTS 文件无错误，构建成功；输出为**未签名** HAP，内容审计使用 development 模式，不能安装或上传代替 C 的正式包。编译器原有警告仍存在，未将其误报为零警告。

精确应用源码提交：`8b64bf6ebefa2b4e609f962e926c294e084b6d52`，该次构建记录 `workingTreeDirty=false`。本机被 Git 忽略的构建记录及 HAP：`app/build/rename-013/unsigned-build-clean/`。未签名 `entry-default-unsigned.hap` 为 133552737 字节、SHA-256 `950fea152c718d364130a8f67657d0c46e70256115e94d194519e1d036eabf54`；[精简收据](../packaging/reviews/rename-0.1.3/unsigned-build-status.json)保留构建记录与清单哈希。构建记录含源码/输入文件指纹、工具版本和逐文件 HAP 清单；不提交大二进制、设备画面或签名凭据。新 HAP 的 `module.json` 含 0.1.3/4、原包名、最低 API23/目标 API24；`resources.index` 含 UTF-8 新名称。与 0.1.2 公开 HAP 比对，2245 个运行时文件一致；重编译的原生库、ArkTS 字节码、资源及元数据**不作逐字节相同声明**。

本机复现命令（C 可用其可信环境的对应 DevEco CLI 和原有载荷）：

```text
python scripts/Extract-RuntimePayloadFromHap.py --hap <已审查的0.1.2公开HAP> --manifest <交付中的runtime-manifest.json> --output <新的本地载荷目录>
python scripts/Build-App.py --check --build-mode release --runtime-manifest <同一manifest> --runtime-payload <上一步目录> --audit-mode development --output-dir <新的未签名输出目录> --cli <devecocli.cmd>
```

第二条仅是内容构建预检；正式 APP 与设备 HAP 必须由 C 的私有签名配置重建，不能从这份未签名 HAP 推断签名有效或商店可提交。

## C 必须完成后回传

1. 从本次改名源码提交及相同完整运行时重建，不直接修改旧已签名 HAP。使用**原发布证书身份**分别生成 `release/app_gallery` 公开 APP 及原 HAD-W32 可安装的 `release/internaltesting` 设备 HAP；不公开私钥、密码或独立 Profile。两个包须为同一源码/载荷/显示名、版本 0.1.3/4、原 `bundleName`。如实际签名资料不允许旧设备 Profile，明确报告，不更换应用身份冒充覆盖升级。
2. 回传签名 APP/HAP 的文件路径或可下载地址、SHA-256、字节大小、精确源码提交、构建/签名验证收据、APP 内嵌 HAP 与设备 HAP 的内容对照、运行时/原生依赖/许可及实际包 SBOM。明确列出相对 0.1.2 的所有变化及所沿用的证据边界。
3. 本组取得签名包后，再在原 HAD-W32/API23 **不卸载、不清数据**执行 `hdc install -r`，记录旧数据保留、启动、桌面/任务栏显示“晶衍精析”、版本 0.1.3/4；必要时按变化范围补测基本工作流。安装前先核对证书身份及包哈希，失败时保留原状态和错误。
4. 重新审核该**精确签名包**后，更新上架包哈希、最终 SBOM、验收矩阵及平台材料。C 在 AppGallery 后台核对名称占用和账号字段，提交及审核通过须另行记录；本交接不等于平台授权。

0.1.2 的 [整包技术审查](PR21_0_1_2_TECHNICAL_RELEASE_REVIEW_2026-10-21.md)保留为旧哈希历史基线。对 0.1.3 的当前状态：`signedPackageReady=false`、`deviceUpgradeAndDisplayVerified=false`、`platformSubmitted=false`、`publicDistributionApproved=false`。
