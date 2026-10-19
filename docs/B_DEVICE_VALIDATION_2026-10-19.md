# B 侧真机补充验证记录（2026-10-19）

## 结论和适用范围

本次在 **HAD-W32 / HarmonyOS 6.1.0.115 / aarch64** 上验证了 GSAS-II 原生扩展、五阶段数值计算及 Python Bridge。设备序列号末四位为 `0901`。既定验收目标是 HAD-W24 / 6.1.0.117，因此这是开发阶段的补充证据，**不是**发布候选技术放行。测试基于 PR #6 的 `214033c` 代码；之后 `59dc488`、`665c001` 为门禁、签名辅助脚本和文档调整，未在本次设备执行中覆盖。本文随 PR 入库，记录原始产物的摘要和可复核输出；二进制、私钥和调试签名包不入库。

## 原生模块与载荷

- 从该设备上既有的、与 GSAS-II 上游提交 `2b4aba1bc44de63a3da9d4495944c3b99e389399` 对齐的环境导出 8 个已签名 OHOS aarch64 扩展：`pyspg`、`pypowder`、`pytexture`、`fmask`、`histogram2d`、`pack_f`、`unpack_cbf`、`kvec_general`。导出归档 SHA-256：`f03d81c6bc1935cfe3c802e4f6aff2b7b658b875e47963b0a6cfe79d7f3de2c8`。未纳入 `pydiffax`。
- 用本地组装的 2230 文件载荷执行 `check_gsas_native.py`（**不带** `--allow-missing`）：8 项存在、ELF64/AArch64 校验通过，`failures=[]`、`warnings=[]`、`releaseReady=true`。这仅证明该次本地组装物满足原生模块存在性门禁，不代表仓库已有可重建、可分发的最终载荷，也不代表许可证和签名审核完成。
- 先用 SDK `llvm-strip` 处理顶层 `libpython3.12.so`，再生成逐文件清单；清单 SHA-256：`27b9b4be61f1a744fa8a2b7aacac51e7970b5b133b6d59dcacfda54f5a023f8a`。`Prepare-Runtime.py` 哈希门禁通过，状态为 `prepared-not-device-validated`。如果以 strip 前字节生成清单，Hvigor 打包后 HAP 审计会报 `packaged runtime mismatch`；最终 strip/重签与清单冻结需在 C 的发布流程中闭环。
- 生成 release 构建模式、但**未签名**的 HAP（179,635,371 字节，SHA-256 `0e59a7089a1786dd344e297e492d43e57ea6653c4f2690fd5e57c9ebc6d54a57`）。开发内容审计：`contentChecksPassed=true`，`releaseCandidateApproved=false`，包名 `com.gsasii.desktop`，版本 `0.1.0`。审计前发现 `release_tools.py` 未给 `libgsas_core.so` 分配组件归属，已在本 PR 补上 `app-core` 并更新测试。

## 设备上实际执行

| 场景 | 可核对结果 | 边界 |
|---|---|---|
| 原生导入 | HiShell 的 CPython 3.12.9 中 8 个模块逐个导入，`GSASII.GSASIIscriptable` 导入成功 | HiShell 用户目录，不是应用沙箱 |
| PbSO4 五阶段 PoC | 五份 fixture 哈希匹配；`before_fitting`、`scale_and_background`、`cells`、`microstrain_displacement_atoms`、`preferred_orientation` 均通过既定容差；择优取向 C(2,0)=`0.1273832642588459`、C(2,2)=`0.0940648194451078`；耗时 12.214 秒 | 终端计算，非 ArkUI/N-API |
| PR #6 Python Bridge | `BridgeRealGsasTest.test_real_five_stage_flow` 通过：收到 `job.completed`，GPX/JSON/日志断言通过；完整 `python3 -m unittest bridge.tests.test_python_bridge -v`：23 项，22 通过、1 项因设备未装 `jsonschema` 跳过 | B03 失败/取消日志用例使用 fake core；不是应用内导出测试 |

PoC JSON 的 SHA-256 为 `755763bb3a97f06d1c69b45cfa39db132f5c27a205d4121746075e8dd914a24d`；完整 Bridge 测试日志的 SHA-256 为 `f5095080931d26c9881d6753ec4af8b9bd408fb8cee7f2e293106cd6f6560f93`。原始记录与 HAP 留存在组长本地 `D:\codex\2026-10-12\qin\device-build-evidence`，本 PR 不分发这些产物。上述哈希用于后续与 C 的交付物比对，**不能**把不同 HAP 的证据混用。

## 安装阻断与未完成的验收

仅为安装实验制作的 OpenHarmony 调试签名 HAP 通过主机端 `hap-sign-tool verify-app` 和四个顶层原生库 code-sign 检查，但在该设备执行 `hdc install -r` 返回 `code:9568257 error: fail to verify pkcs7 file`，应用**未安装**。DevEco CLI 自动签名服务另返回 `Users without real-name verification are not supported`。这不是正式签名；正式签名、strip 后重签、SBOM/许可审核、发布审计由 C 负责。

因此尚无以下应用沙箱真机证据：`libgsas_core.so` → `libpython3.12.so` 加载与 `Py_Initialize`、rawfile 解包及权限、应用内五阶段和 `job.completed` 产物登记及 GPX/JSON/日志导出、B03 失败/取消产物的页面可发现性与导出、进程重启/页面重建/`PROCESS_INTERRUPTED`、取消 ACK 竞态、后台和退出提示。`RELEASE_ACCEPTANCE.md` 第 4–8 项保持待验。下一轮需由 C 提供目标设备接受的签名 HAP，并在 HAD-W24 / 6.1.0.117 或经批准的同版本目标设备上完成同一构建的应用内验收。
