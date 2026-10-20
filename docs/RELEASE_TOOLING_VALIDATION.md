# 发布工具验证记录

状态提示（2026-10-20）：以下 2026-10-17 的小型开发 HAP 验证是历史快照。后续已审计 2246 文件/224 ELF 的指定设备签名 HAP，并在 HAD-W32/API23 完成应用内成功路径；见[C 交付](C_SIGNED_HAP_DELIVERY.md)。最终第三方分发审查未关闭。

验证日期：2026-10-17（北京时间）。范围为构建留档、宿主运行时装配和 HAP 内容门禁；应用 ArkTS/C++ 业务及冻结核心契约未修改。

| 验证 | 结果 |
|---|---|
| 宿主工具测试 | 21 项通过；含 Windows npm CLI 参数隔离测试，合成载荷不含真实 Python/科学计算二进制 |
| C01/C02 原开发 HAP 实际审计 | development 模式通过，19 个包内文件，HAP 哈希与既有记录一致 |
| 新构建脚本的真实 DevEco 构建、留档与 smoke | PASS：7 个 ArkTS 文件 0 错误，Release 构建、实际包审计、自动留档、覆盖安装、启动及 Smoke PASS |
| 覆盖安装后文件恢复 | PASS：界面显示已恢复 1 个文件，PBSO4.XRA / 49,445 字节 |
| 空模板与无运行时 release 审计 | 预期失败，退出码 1；分别明确提示等待 B 载荷、要求 ready 清单，未写成功报告 |
| 真实 B 运行时、设备激活、离线精修、最终 SBOM/正式签名 | 未执行；等待 B、A、组长的相关交付 |
| Linux SDK 构建 | 未执行；Linux 路径/CLI 分支仍需接收方验证 |
| Windows 新 bundleName 构建 | PASS：DevEco CLI 1.3.5、Command Line Tools 26.0.0.851、SDK 26.0.0.105；7 个 ArkTS 文件 0 错误，Release 构建成功，实际 HAP 内容审计通过 |

实际产物留在 `app/build/deliverables/` 的忽略目录，测试记录不作为正式发布候选批准。CI 使用公开 Runner 验证宿主门禁，不提供签名或设备验收。

## 真实构建的追溯信息

- 构建源码提交：`dfbdc6474e3d135db6d286adb8a8e9502d2fd257`，构建时工作区干净；后续提交仅补本文及证据。
- app 源码指纹：`d90889c476aa3a59c717d8e98256d1509cbb28aaad86894ab29dec735350689c`，与 C01/C02 相同，业务源码未变。
- HAP：`app/build/deliverables/gsaspc-k_l6cu70/entry-default-unsigned.hap`，1,642,148 字节。
- HAP SHA-256：`98959e835c1ab9debbe71cc1b784af14c830cd9174e3a48359d22727ceca6a03`。
- [构建记录](evidence/release-tooling/build-record.json)及[逐文件清单](evidence/release-tooling/entry-default-unsigned.hap.inventory.json)保存原始留档副本，仅 JSON 入 Git，HAP 仍留本地。
- 环境：DevEco CLI 1.3.5、Node 24.14.1、Python 3.11.3；HAP 记录编译 SDK 26.0.0.105，PC 模拟器 MateBook Pro 1。SDK 仍有既有异常传播/原生声明验证等警告及未签名提示，本次不声称零警告或签名已验收。

构建记录和内容清单哈希已用独立脚本从归档字节重算并一致；`runtimeId: null`、`signingVerified: false`、`releaseCandidateApproved: false`。未重复 C01/C02 的完整设备文件测试，未声称应用已可执行 Python 精修。HAP 的字节哈希可能因构建路径/工具输出而变化，留档用于追溯，不声称跨机器二进制逐字节可重现。

> 历史证据说明（2026-10-17）：组长确认开发 bundleName 由 `com.xiaotaop.gsaspc` 改为 `com.gsasii.desktop`。上文“真实构建的追溯信息”及原 `build-record.json`、`entry-default-unsigned.hap.inventory.json` 均来自改名前构建，仅用于历史追溯，不得作为新 bundleName 的验收证据。新包名的 Windows 重建及内容审计证据见下节；设备安装和数据隔离仍待具备设备或模拟器后执行。

## Windows 新 bundleName 重建（2026-10-17）

- 工具安装：[安装证据](evidence/release-tooling/windows-toolchain-installation.json)。DevEco CLI 1.3.5 通过 npm 安装；华为 Command Line Tools 26.0.0.851 以并行目录安装，保留原 6.0.2.670。安装包 SHA-256 为 `ac8d0563f47f95ca78799ea4aa494fa260bc3f7c8f2a569ac629af1794b5d71c`；压缩包 109,379 个条目，未发现越界路径或符号链接。安装包由组长从[华为下载中心](https://developer.huawei.com/consumer/cn/download/command-line-tools-for-hmos)下载并提供；本记录未用单独发布的厂商校验值交叉核验。
- 构建输入：`main@85f23b0571cff9daed8c868b2523787d5e84f113`，构建时工作区干净；源码指纹与临时英文构建目录的输入指纹均为 `43cbb5926d4f7f2619705cfc063eba99e4244844f85cddf715c0dd193a401fa1`。
- 检查与构建：7 个 ArkTS 文件 0 错误、36 条既有异常传播/N-API 声明警告；Hvigor Release 构建 33 个任务成功。工具链内部安装 pnpm 时报告 1 个 high severity npm 审计项，未执行可能改变锁定工具链的 `npm audit fix --force`；该提示不等同于应用 HAP 已发现同一依赖漏洞。
- HAP：`entry-default-unsigned.hap`，1,642,271 字节，SHA-256 `d0a5511becc02cfd6c5325693e6f6d9a673b986b5fd54d6772b03b663c15c48a`。包内元数据为 `com.gsasii.desktop`、0.1.0、最低 API20、目标 API24、编译 SDK 26.0.0.105、`debug: false`、`buildMode: release`。
- 内容审计：development 模式通过，19 个文件；独立复跑与构建时清单逐字节相同，清单 SHA-256 `12b646ce6073e53a30a394715606357ec4cfd5c266f56f52ae93dfa015e2bdf1`。证据为[构建记录](evidence/release-tooling/bundle-rename-build-record.json)和[逐文件清单](evidence/release-tooling/bundle-rename-entry-default-unsigned.hap.inventory.json)。
- 限制：HAP 未签名，`runtimeId: null`、`signingVerified: false`、`releaseCandidateApproved: false`。检查时没有连接设备，26.0.0.851 工具目录也没有模拟器实例，因此没有执行安装、覆盖升级、旧包沙箱隔离或真实核心验证；不得将本记录解释为上架候选批准。
