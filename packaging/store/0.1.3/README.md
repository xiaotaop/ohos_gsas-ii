# 晶衍精析 0.1.3 上架材料工作稿

团队采用自有开发者账号路线。当前固定候选为 `JingyanJingxi-0.1.3-app-gallery.app`，SHA-256 `89e6b3e47afba2a17d01696cea6c6b6333a7edeb8a1bab58ab18f1b6ff4ddafd`；源码 `8b64bf6ebefa2b4e609f962e926c294e084b6d52`，0.1.3/versionCode 4，`com.gsasii.desktop`。[同载荷设备包复验](../../../docs/PR23_0_1_3_DEVICE_RETEST_2026-10-21.md)与[限定 API23 技术审查](../../../docs/PR23_0_1_3_TECHNICAL_RELEASE_REVIEW_2026-10-21.md)已通过。公开 APP 尚未经平台检测或批准。

- `listing.zh-CN.json`：新名称、实际候选包和已验证范围绑定的文案草稿；发布者/维护者为朱宇辰、反馈入口为仓库 Issues、仅中国大陆；价格为免费，分类与分级待后台确认。
- `privacy.zh-CN.draft.md`、`permission-data-map.json`：本地数据流程与隐私工作稿；完整政策及 HTML 已准备，公开 URL 的实际可达性和平台隐私检测仍待核对，不以 manifest 无权限推断所有依赖绝不会通信。
- `screenshot-review.json`：三张 0.1.3 新名称真机原图的哈希、尺寸与素材审核起点；[十张原始截图索引](../../../docs/A_RENAME_0_1_3_DEVICE_SCREENSHOTS_2026-10-21.md)保留全部工程证据。旧名称截图仅作历史证据，不作本版主图。
- `reviewer-guide.zh-CN.md`：平台审核人员可复现的已验证流程及证据边界。
- `official-requirements.md`：官方入口与仍需已登录后台确认的字段；不虚构 PC 截图规格。
- `submission-status.json`：技术通过与平台待办分别记录，`readyToSubmit=false`、`platformSubmitted=false`。

账号持有人确认的字段及可直接操作的步骤见 [平台交接](platform-handoff.zh-CN.md)。隐私政策见 [完整文本](../../../docs/PRIVACY.zh-CN.md)。

提交前由 C 用实际账号核对名称占用、所需权利和资质、素材尺寸/张数、隐私政策 URL 与应用内入口要求、维护/反馈方式，并上传上述固定哈希的 **APP**（不是设备 `internaltesting` HAP，也不是 Git LFS 指针）。记录平台检测、受理编号和审核问题。缺项未闭环前，本目录只是草稿，不代表获准公开分发。

图标请使用工程 SVG 原样渲染的 [1024 PNG](../../../docs/assets/app-icon-1024.png) 或 [216 PNG](../../../docs/assets/app-icon-216.png)，符合本次已登录应用信息表单提示的尺寸/格式限制；该尺寸核对不等于平台内容审核批准。
