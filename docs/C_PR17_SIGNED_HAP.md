# C：PR #17 同包验收签名 HAP 交接

按组长要求使用精确源码 `ce624cec654e3492697e22792a047ff69e88d4fc` 与完整运行时，在原发布证书及原 HAD-W32 指定设备 internaltesting Profile 下重建/签名，未改源码或版本。PR #17 构建时仍待合并，本交付分支只增加包和收据，不重复合入 B 的实现。

| 标识 | 值 |
| --- | --- |
| 应用/版本 | com.gsasii.desktop / 0.1.1 / versionCode 2 |
| 源码提交 | `ce624cec654e3492697e22792a047ff69e88d4fc` |
| HAP | `GSAS-II-0.1.1-ce624cec-signed.hap` |
| HAP SHA-256 | `791dc53da7f76c56e0f9ce45b40b83d9cb45b9b42990379f59de64989d712788` |
| HAP 大小 | 135971349 字节 |
| 完整 ZIP SHA-256 | `7d26c658021426de1f536cefa5b2962c4d3682741cf777bb16545dfa9384b5c5` |
| ZIP 大小 | 91500152 字节 |

## 直接下载

- [签名 HAP](../deliveries/GSAS-II-0.1.1-ce624cec-signed.hap)：可单独下载供原设备覆盖安装。
- [完整交付 ZIP](../deliveries/c-pr17-ce624cec-791dc53d.zip)：包含同一 HAP、两个源码伴随、第三方版权全文、实际 SBOM 草稿/完整索引/原生图、签名与绑定收据及 SHA256SUMS。

二者通过 Git LFS 保存。在 GitHub 文件页点击 **Download raw file**，不要把文本指针当作安装包。克隆用户安装 Git LFS 后运行 `git lfs pull`。版本号仍与旧包相同，必须用本提交和 HAP SHA-256 识别；旧 59c86f18/70588bde 不含 PR #17 修复。

## C 已完成的核验

1. Release 编译与签名成功；SDK verify-app 和全部原生代码签名通过。提取的证书链及 Profile 字节与此前已安装参考包完全一致，类型为 release/internaltesting、bundleName 匹配。仅发布指纹和布尔证明，不上传独立 Profile、证书、密码或私钥。
2. 50 个实际构建 app 源文件与指定提交及新源码伴随逐项一致；源码伴随全部成员哈希核验。2245 运行时文件 / 219 ELF / 2266 HAP 文件及全部八扩展齐全。
3. 新 HAP 相比 59c86f18 仅 `ets/modules.abc` 变化；全部运行时、219 原生库与 40 个许可文件还直接核对至已审查 70588bde 参考包，均逐字节相同。
4. SBOM 从本 HAP 重新生成，2266 文件、219 ELF、485 NEEDED、无未匹配名称，CycloneDX 1.5 schema 通过；19 份许可集合、115 个原始 SciPy 库、14 个 LLVM 静态消费者重新核对。完整的离线绑定记录在下方。
5. 指定提交的干净源码：Python 工具 92/92；Bridge 28 项中 26 通过/2 跳过；Core 宿主 30/30；JSON、契约与 fixture 校验通过。静态无网络 API 检查明确不是断网设备证据。

[构建收据](../packaging/reviews/c-pr17-ce624cec/BUILD-RECEIPT.json) · [签名/原生证明](../packaging/reviews/c-pr17-ce624cec/signature-native-verification.json) · [运行时/SBOM/许可逐哈希绑定](../packaging/reviews/c-pr17-ce624cec/runtime-sbom-license-binding.json) · [测试结果](../packaging/reviews/c-pr17-ce624cec/exact-source-validation.json) · [下载大小/哈希](../packaging/reviews/c-pr17-ce624cec/download.json)

## 组长/B 接下来执行

原设备用相同签名覆盖安装保留用户数据，随后按 B 提供的稳定步骤验证：初始化失败后重试、Core-only 第二任务 BUSY、取消 ACK/自然完成竞争；逐 jobId 对照恰好一个终态及持久化快照。显式断网五阶段独立留证。此处不引入清数据步骤、不伪造触发入口，也不修改 PR17 源码。

C 本轮没有操作真机；新包终态唯一性/显式断网设备记录仍待组长/B 返回。运行时、SBOM 和许可的离线材料绑定已完成，最终同包设备/数值审查需绑定新记录；原未知来源精度限制继续保留，旧包设备报告不套用。未宣称组长技术放行或上架批准。
