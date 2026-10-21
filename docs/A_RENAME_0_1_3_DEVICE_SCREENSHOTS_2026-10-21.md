# A 页面：0.1.3 新名称真机截图

日期：2026-10-21。原 HAD-W32 / API23 上安装的 `JingyanJingxi-0.1.3-device-internaltesting.hap` SHA-256 为 `60fca45be125e825169b7fef90669cf76a0ef490adeeed1acd28f8ee1a9b94a7`，源码为 `8b64bf6ebefa2b4e609f962e926c294e084b6d52`。以下均为设备 `snapshot_display` 取得的 **3120 × 2080 原始全屏 JPEG**，未裁剪、重绘或拼接；应用标题和系统搜索结果显示“晶衍精析”。这是新包实拍，旧 [A 验收](A_A14_DEVICE_ACCEPTANCE.md)及其七张旧名称截图保留为原哈希的历史证据。

| 新包场景 | 真机截图 | SHA-256 |
| --- | --- | --- |
| 系统本机应用搜索结果 | [launcher-name.jpeg](evidence/a-rename-013-60fca45b/launcher-name.jpeg) | `cda425719f0f13de5b7927b557aa5cab97d51421489fd56e92df5e748f1aeed5` |
| Controls 与新窗口标题 | [controls.jpeg](evidence/a-rename-013-60fca45b/controls.jpeg) | `d6fbad20ecee63ed6ee5de6e7902043363d4c5e9214adca5b132c21b52ac09b0` |
| 旧五输入和文件库保留 | [files.jpeg](evidence/a-rename-013-60fca45b/files.jpeg) | `30a7dea07e4ce0f409b6ef2fc2ea7d0edc3aafca1d0d14f93be7cb2e925b1a3f` |
| 新五阶段任务完成 | [success.jpeg](evidence/a-rename-013-60fca45b/success.jpeg) | `7284202ea3ea053db34b3a448d5069eb5a11c1e846c133499e449b69705053d8` |
| 结果、两项取向值和三件产物导出入口 | [result-artifacts.jpeg](evidence/a-rename-013-60fca45b/result-artifacts.jpeg) | `bdbb944512e528ee500cfdb06ff2678464bd908185bc9ad4f988e3748b87074d` |
| 用户取消及取消日志 | [cancelled.jpeg](evidence/a-rename-013-60fca45b/cancelled.jpeg) | `265df9a07fa66605f3cd8d5498368ac869f52196afd61e6776350ffcb5822870` |
| 无效 CIF 失败及失败日志 | [failed.jpeg](evidence/a-rename-013-60fca45b/failed.jpeg) | `c63b177e579ecebe47918156880850616a0dfbcbfd9797bdb99c24bafa89fd16` |
| 活动任务关闭保护 | [close-guard.jpeg](evidence/a-rename-013-60fca45b/close-guard.jpeg) | `5cd025796d62951800f3a6f4dd95254cc68740f397975e39d32097c30f420b46` |
| 约 1220 × 914 物理像素窗口，输入和按钮可见 | [minimum.jpeg](evidence/a-rename-013-60fca45b/minimum.jpeg) | `0c2d9a73943446b83f346760d6d652e5d884028f01534fa3cc13e11a1282f5d6` |
| 正常退出重启后旧结果恢复 | [restarted.jpeg](evidence/a-rename-013-60fca45b/restarted.jpeg) | `644ca4fa3ad9798de0fe40101a676c515a19638f67d5aeb178593ab0284738ee` |

成功图对应本次新任务 `rename013-api23-20261021.gpx`、3 cycles、结果 8.76 秒；文件库 55→58。随后取消和失败各登记一份日志，恢复原 CIF 关联并通过五输入完整性检查；关闭保护任务继续完成后，文件库为 63，正常退出重启后仍为 63。完整过程、数值及导出边界见[本包复验](PR23_0_1_3_DEVICE_RETEST_2026-10-21.md)。

这些照片是工程真机证据。C 提交应用市场素材时仍须按平台尺寸、隐私和内容规则选图；市场素材采用这些新名称画面，不再把旧名称截图描述为当前 0.1.3 实拍。系统搜索的“在应用市场中搜索”只是通用搜索建议，不表示应用已经上架。
