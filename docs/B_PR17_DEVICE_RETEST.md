# PR #17 同包真机复验步骤（成员 B 提供给组长）

适用对象：C 已交付的 PR #17 签名包（源码提交
`ce624cec654e3492697e22792a047ff69e88d4fc`，原发布证书 + HAD-W32
internaltesting Profile，未改源码或版本）：

| 标识 | 值 |
|---|---|
| HAP | `GSAS-II-0.1.1-ce624cec-signed.hap` |
| HAP SHA-256 | `791dc53da7f76c56e0f9ce45b40b83d9cb45b9b42990379f59de64989d712788` |
| HAP 大小 | 135,971,349 字节 |
| 应用/版本 | `com.gsasii.desktop` / 0.1.1 / versionCode 2 |
| 源码提交 | `ce624cec654e3492697e22792a047ff69e88d4fc` |
| 交付记录 | `origin/codex/c-pr17-signed-hap`：`docs/C_PR17_SIGNED_HAP.md`、`packaging/reviews/c-pr17-ce624cec/` |

**必须用上面的 HAP SHA-256 识别本包**：版本号与旧包相同，旧 `59c86f18…` /
`70588bde…` 不含 PR #17 修复。

下载：包通过 Git LFS 保存。在 GitHub 文件页点 **Download raw file**（不要把文本指针
当安装包），或克隆后执行 `git lfs pull`。

本文只描述**怎么在该签名 HAP 上触发与核对**，不重复 C 的构建/签名工作。所有步骤
以“不卸载、不清除应用数据”为前提。

## 0. 开始前记录

| 项 | 记录方式 |
|---|---|
| HAP | 已安装包的 SHA-256 必须等于 `791dc53d…12788`；记录安装时间、版本 0.1.1/2 |
| 源码提交 | `ce624cec654e3492697e22792a047ff69e88d4fc` |
| 设备 | HAD-W32、系统/API、时间 |
| 数据基线 | 文件库条目数、笔记、历史任务列表；若沙箱可读，记录 `files/imports`、`files/jobs`、`files/outputs` 下除被测 job 外的文件哈希清单 |

## 1. 通用核对：每个 jobId 恰好一个终态

对每个场景、每个 jobId，按顺序核对：

1. **页面**：只出现一个终态（“精修完成”/“任务失败”/“任务已取消”），不会从完成跳到取消或反之。
2. **任务消息**：`job.completed`、`job.failed`、`job.cancelled` 中只有一条；序号递增、percent 不倒退。
3. **重启恢复**：退出并重新打开应用，同一 jobId 应恢复为同一终态；运行中被 force-stop 的任务应为 `PROCESS_INTERRUPTED`。
4. **快照（沙箱可读时）**：`files/outputs/<jobId>/core/terminal-snapshot.json` 只有一个终态，`payload` 与页面一致；失败/取消另有 `job-log.txt`。
5. **数据保留**：文件库、笔记、历史任务与第 0 节基线一致（除本次新增的 job 外）。

若任一步出现两个终态或状态跳变：截图 + 时间 + jobId + hilog，作为 PR #17 的失败证据。

## 2. 场景 C：取消 ACK 与自然完成竞争（可直接执行）

现有 UI 支持，无需额外权限。

1. 使用 PbSO4 五份输入，`Max cycles = 1`，输出名唯一（例如 `pr17-race-01`）。
2. 点“Refine”；任务约 8–9 秒完成（验收记录 8.735/8.857 秒）。
3. 在进度约 80–95%（最后一个阶段附近）点“Cancel refinement”。
4. 等待终态；重复 5 次，至少覆盖两种结果：
   - 取消先到 → 终态“任务已取消”；
   - 完成先到 → 终态“精修完成”。
5. 每次按第 1 节核对；成功任务导出 GPX/JSON/日志，取消任务导出用户日志。
6. 再重复一次“在进度 50% 左右取消”，确认常规取消路径不受影响。

判定：每次只有**一个**终态；取消后不会再出现“完成”，完成后再不会出现“取消”。

## 3. 场景 A：初始化失败后重试（需要一次性可恢复的失败注入）

标准签名包在正常设备上不会初始化失败，**UI 没有“制造失败”的入口**。以下三种方式
任选其一；前两种需要 C/组长配合，第三种只能保留宿主证据。

### A1. 沙箱可写时（需确认 internaltesting 包允许 hdc 写应用目录）

1. 记录 `files` 目录及用户数据基线（第 0 节）。
2. 让运行时安装无法创建影子目录：
   ```sh
   hdc shell ls -ld /data/app/el2/100/base/com.gsasii.desktop/files
   hdc shell chmod 500 /data/app/el2/100/base/com.gsasii.desktop/files
   ```
3. 冷启动应用（不要卸载）。预期：初始化失败，页面显示“Retry initialization”。
4. 恢复权限：
   ```sh
   hdc shell chmod 700 /data/app/el2/100/base/com.gsasii.desktop/files
   ```
5. 点“Retry initialization”。预期：核心就绪，原文件库/笔记/历史任务保留。
6. 按第 1 节核对数据保留。

> 注意：`files` 根不可写也会影响 `outputs` 写入；测试期间不要运行任务，恢复权限后再跑。
> 若设备实际沙箱路径不同，以 `bm dump`/C 的记录为准。

### A2. 由 C 提供带“注入一次初始化失败”开关的测试包（不进入发布包）

开关语义建议：首次 `initialize` 返回 `CORE_NOT_READY` 一次，重试时清除标记并正常启动。
B 可按该语义在宿主复现（已有用例），真机由 C 的测试包触发。

### A3. 都不具备

记录为“宿主证据已有、真机入口受限”，**不能**计为真机通过。

## 4. 场景 B：Core-only 第二任务 BUSY（现有 UI 无入口）

页面在任务进行中禁用“Refine”（`submitting`/`isActive`），且 `start()` 在任何 await
前就设置 `submitting`，因此**双击也无法产生第二个任务**。可选入口：

### B1. 同一应用分屏/多窗口（若设备支持）

两个窗口各自选择输入并提交，第二个应在原生 `acquireJob` 得到 `BUSY`。核对：
第二个窗口提示“已有任务在运行”，第一个任务正常完成，只有一个终态。

> 该方式依赖系统是否允许同一应用双窗口；若设备不允许，视为不可用。

### B2. A 的非发布测试包开放“第二次启动”入口

按钮只在测试包出现，直接调用 `startRefinement`，预期 `BUSY` 且不创建文件租约。

### B3. 都不具备

以 `tests/core-bridge-host.test.cjs` 的 “Core-side BUSY” 用例作为宿主证据；
真机记录写“入口受限”，**不能**用文件服务的 BUSY 冒充。

## 5. 显式断网（行 4）

B 只提供静态证据（`tests/test_core_no_network.py`：在指定 bridge、C++、ETS 源码中扫描所列网络 API；不覆盖打包运行时与动态调用），
**不替代**设备断网五阶段记录。断网步骤由组长按 C 的流程执行：关闭 Wi-Fi/移动数据后，
完成一次 PbSO4 五阶段并导出结果。

## 6. 证据清单（每次场景）

- HAP SHA-256/大小/version、源码提交、设备/API、时间；
- 截图：启动、失败提示/重试、终态、导出结果；
- jobId、`job-log.txt`/结果 JSON 的 SHA-256（导出后计算）；
- hilog：`hdc shell hilog -x`（或按 `GSASPC` Tag 过滤）；
- 沙箱快照（可读时）；
- 数据保留前后对比。

## 7. 边界

- 本文的“稳定触发”只对场景 C 成立；A 需要一次可控失败注入，B 需要第二个启动入口。
  这是当前 UI 与签名包的真实限制，不以宿主测试冒充真机。
- PR #17 修复的是门面层“终态唯一性”；native 层仍应保证唯一终态，本复验只验证
  页面侧不会因竞争看到两个终态。
- 私钥、口令与 Profile 不需要提供给 B。
