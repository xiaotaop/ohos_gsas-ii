# 发布工具验证记录

验证日期：2026-10-17（北京时间）。范围为构建留档、宿主运行时装配和 HAP 内容门禁；应用 ArkTS/C++ 业务及冻结核心契约未修改。

| 验证 | 结果 |
|---|---|
| 宿主工具测试 | 21 项通过；含 Windows npm CLI 参数隔离测试，合成载荷不含真实 Python/科学计算二进制 |
| C01/C02 原开发 HAP 实际审计 | development 模式通过，19 个包内文件，HAP 哈希与既有记录一致 |
| 新构建脚本的真实 DevEco 构建、留档与 smoke | PASS：7 个 ArkTS 文件 0 错误，Release 构建、实际包审计、自动留档、覆盖安装、启动及 Smoke PASS |
| 覆盖安装后文件恢复 | PASS：界面显示已恢复 1 个文件，PBSO4.XRA / 49,445 字节 |
| 空模板与无运行时 release 审计 | 预期失败，退出码 1；分别明确提示等待 B 载荷、要求 ready 清单，未写成功报告 |
| 真实 B 运行时、设备激活、离线精修、最终 SBOM/正式签名 | 未执行；等待 B、A、组长的相关交付 |
| Windows/Linux SDK 构建 | 未执行；跨平台路径/CLI 分支需接收方验证 |

实际产物留在 `app/build/deliverables/` 的忽略目录，测试记录不作为正式发布候选批准。CI 使用公开 Runner 验证宿主门禁，不提供签名或设备验收。

## 真实构建的追溯信息

- 构建源码提交：`dfbdc6474e3d135db6d286adb8a8e9502d2fd257`，构建时工作区干净；后续提交仅补本文及证据。
- app 源码指纹：`d90889c476aa3a59c717d8e98256d1509cbb28aaad86894ab29dec735350689c`，与 C01/C02 相同，业务源码未变。
- HAP：`app/build/deliverables/gsaspc-k_l6cu70/entry-default-unsigned.hap`，1,642,148 字节。
- HAP SHA-256：`98959e835c1ab9debbe71cc1b784af14c830cd9174e3a48359d22727ceca6a03`。
- [构建记录](evidence/release-tooling/build-record.json)及[逐文件清单](evidence/release-tooling/entry-default-unsigned.hap.inventory.json)保存原始留档副本，仅 JSON 入 Git，HAP 仍留本地。
- 环境：DevEco CLI 1.3.5、Node 24.14.1、Python 3.11.3；HAP 记录编译 SDK 26.0.0.105，PC 模拟器 MateBook Pro 1。SDK 仍有既有异常传播/原生声明验证等警告及未签名提示，本次不声称零警告或签名已验收。

构建记录和内容清单哈希已用独立脚本从归档字节重算并一致；`runtimeId: null`、`signingVerified: false`、`releaseCandidateApproved: false`。未重复 C01/C02 的完整设备文件测试，未声称应用已可执行 Python 精修。HAP 的字节哈希可能因构建路径/工具输出而变化，留档用于追溯，不声称跨机器二进制逐字节可重现。

> 历史证据说明（2026-10-17）：组长确认开发 bundleName 由 `com.xiaotaop.gsaspc` 改为 `com.gsasii.desktop`。本页引用的 HAP、构建记录和逐文件清单均来自改名前的真实构建，保留原始字节、哈希和元数据仅用于历史追溯，不得作为新 bundleName 的构建验收证据。新包名的 DevEco 构建、HAP 审计、安装和数据隔离验证需重新执行并另行留档。
