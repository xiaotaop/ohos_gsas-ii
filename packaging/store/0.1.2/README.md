# 上架材料工作稿（等待最终改名与重签）

已选自有华为开发者账号路线，候选版本0.1.2/3。最终显示名由组长修改，当前主线4225cba仍是旧名称。本目录不含新的签名包，不表示平台已提交或批准。

- listing.zh-CN.json：可用功能文案；最终应用名与待填字段保持null，避免误用旧名。
- privacy.zh-CN.draft.md、permission-data-map.json：本地数据流程与隐私工作稿；主体/联系方式/URL按用户要求暂空。最终候选的完整动态隐私检测与应用内入口仍需确认，不以无manifest权限推断所有依赖绝不通信。
- screenshot-review.json：3张既有功能图的原始哈希、尺寸和内容审核；来源为A的59c86f18包。Controls、成功结果、重启恢复原图保持不变，用户明确决定沿用；旧名称与平台实际规格仍需按最终提交核对。不是最终改名包实拍。
- reviewer-guide.zh-CN.md：改名、重签及新包复验/平台操作说明。
- official-requirements.md：核对过的官方入口及未能确认的素材规格边界。
- submission-status.json：基线已通过的技术审核和最终改名包待办分别记录。

旧图位置见清单的path，均相对于仓库根目录；512图标与源SVG见 docs/assets/icon-manifest.json。完整运行时/源码/许可固定交付及最终SBOM仍在既有PR21记录中，不能把其哈希直接赋给未来改名包。

执行顺序：组长提供改名提交 → C核对差异并重建/签名 → 固定新包/源码/SBOM/许可哈希 → 组长复验受影响项 → 补全上架信息与平台检测 → 明确提交审核并记录结果。当前readyToSubmit=false。
