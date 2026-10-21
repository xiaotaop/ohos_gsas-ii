# 晶衍精析 0.1.3 审核说明草稿

本应用是基于 GSAS-II 的**非官方 HarmonyOS PC 移植**，不代表上游机构发布或背书。提交候选为签名 APP `JingyanJingxi-0.1.3-app-gallery.app`（SHA-256 `89e6b3e47afba2a17d01696cea6c6b6333a7edeb8a1bab58ab18f1b6ff4ddafd`），包名 `com.gsasii.desktop`，versionCode 4。原 HAD-W32/API23 使用同载荷 `internaltesting` HAP 完成保留数据升级、名称显示和关键工作流复验；公开 APP 仍须通过平台包检测和审核。技术证据见 `docs/PR23_0_1_3_DEVICE_RETEST_2026-10-21.md` 与 `docs/PR23_0_1_3_TECHNICAL_RELEASE_REVIEW_2026-10-21.md`。

已验证的演示路径：准备 `PBSO4.XRA`、`INST_XRY.PRM`、`PBSO4.CWN`、`inst_d1a.prm`、`PbSO4-Wyckoff.cif`，通过系统文件选择器分别导入并关联；相名设为 `PbSO4`、Max cycles 设为 `3`、填写新的 `.gpx` 输出名，执行五阶段精修；结果页查看 Rwp 和择优取向，并通过系统选择器保存 GPX、JSON、日志。只声明 HAD-W32/API23 上此样例路径的验证，不声称任意样品、原版全部功能、API20/API24 或其他机型已验证。导出文件的原始字节未从设备读回，证据限于保存与重新发现。

产品页主图应从 `docs/evidence/a-rename-013-60fca45b/` 的 0.1.3 新名称原图中按平台要求选择、导出，不把旧 0.1.2 或更早截图描述为当前包实拍。具体尺寸、张数、格式及隐私/素材规则以已登录平台当时提示为准，当前尚未取得平台接受结果。

发布者、维护者、有效反馈方式、隐私政策 URL、分类/地区及必要资质由实际账号持有人填写和核对。隐私工作稿并非正式政策，当前应用源码未发现专用隐私政策入口；若平台要求补入口而需改包，应重新构建签名并复验新哈希。提交后记录平台检测、受理编号及审核反馈；在这些步骤完成前，本文件不能写成公开分发批准。
