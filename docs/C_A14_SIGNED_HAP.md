# PR #14 完整运行时签名 HAP 交接

C 已按 A 指定的合并提交重新构建，交给 A 在原 HAD-W32 上安装并完成新界面同包验收。

| 项目 | 值 |
| --- | --- |
| 源码提交 | `57c661db55020e5c200947da203ea449c536c1fe` |
| 应用 | `com.gsasii.desktop` |
| 版本 | `0.1.1` / versionCode `2`，保留指定提交原值 |
| HAP | `GSAS-II-0.1.1-57c661db-signed.hap` |
| HAP SHA-256 | `59c86f189dd89a22e2e009f4637a58756193cbeececd2ec3f8bde0e85c3e176b` |
| HAP 大小 | 135971610 字节 |
| 签名 | Release 证书 + 原 HAD-W32 的指定设备 internaltesting Profile，与前包相同 |

## 下载与校验

[下载完整交付 ZIP](../deliveries/a-pr14-57c661db-59c86f18.zip)（90,032,752 字节，通过 Git LFS 存储）。GitHub 文件页点击 **Download raw file**；若用 Git 克隆，需安装 Git LFS 并运行 `git lfs pull` 获取实际 ZIP，而非文本指针。

ZIP SHA-256：`e9957809c00c4e9049331f7ff80a425fe016cbb9f1d3abc3fa8e1a91711451d6`。其中包含完整签名 HAP、精确提交源码伴随包、受控 CPython 核心源码伴随包、版权全文、逐文件 SBOM 草稿与原生依赖、验证记录、SHA256SUMS 和可直接转交说明。所有归档成员已逐字节核验。

没有附独立私钥、密码或独立 Profile。两份源码与许可伴随材料须随 HAP 保留，不只转发一个安装文件。

## 已通过的本地验证

- Release 构建、SDK verify-app 以及全部原生代码签名检查。
- 50 个实际构建 app 源文件逐项匹配指定提交和新源码伴随包。
- 2245 个运行时文件、219 ELF、2266 个 HAP 文件；全部八个计算扩展存在。逐模块哈希见 [构建收据](../packaging/reviews/a-pr14-57c661db/BUILD-RECEIPT.json)。
- 与前包 70588bde 比较，运行时/全部原生库/许可字节完全一致，只有 `ets/modules.abc`、`.pages.info`、`resources.index` 改变。
- 本次实际 HAP SBOM 无未匹配 NEEDED，CycloneDX 1.5 schema 验证通过；19 份许可收据、115 个 SciPy 原始库和 14 个 LLVM 静态消费者重新核对。
- 在指定提交的干净源码上运行：91 项工具测试通过；bridge 28 项中 26 通过、2 平台跳过；JSON、协议与 fixture 校验通过。

## A 的后续验收

版本号与旧包相同，必须用上面的**提交号和 HAP 哈希**标识本包。A 使用已连接的原 HAD-W32，执行同签名覆盖安装并保留数据，再记录：

1. 新包安装、启动、真实五阶段及导出。
2. 任务结束后无需重启即可发现新增三个产物；手动 Refresh；失败/取消日志刷新。
3. 新界面、最小窗口、后台/退出交互和对应同包截图。

反馈安装输出、型号/API、任务结果、截图和上述包标识。C 本轮没有重新操作真机；旧 70588bde 的设备证据和 A 修改前截图不替代此包验收。新 SBOM 的同包最终设备绑定等待 A 的新记录；未宣称新包已真机通过或取得组长/上架放行。原冻结记录不改写。
