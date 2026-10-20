# C：B 依赖交接材料与实际 HAP 复核

2026-10-20，接收已合并 PR #10 的依赖清单与 11 份许可证文本（原交付提交 `4ddaa8c`，主线 `a797b86`）。**材料接收不等于许可批准，第 2 项仍未完成。**

## 已核实的材料

- 11 份许可证文本逐文件大小、SHA-256 与 SOURCES.json 一致，保留原始换行字节。
- 锁定的 CPython/NumPy/SciPy 原始预编译归档哈希均正确。B 清单中的 6 个库文件哈希与归档内容匹配；CPython 的 libpython3.12.so 软链接在归档内部解析到其正规目标，不向文件系统解压链接。
- 将原始库与实际 HAP 对比：6 个库除 .codesign 外的 SHF_ALLOC 节名称、类型、标志、长度和内容一致。非装载的调试数据或签名变化不会被误判为科学代码改变；同时保留前后完整哈希。该结论不证明源代码补丁一致、重定位语义、签名有效或许可证已批准。
- 在实际包中观察到 OpenSSL、SQLite、bzip2、XZ、ncurses、Expat、libmpdec 的声明版本字面标记。这是二进制观察，不代替精确源码和构建物料。

## 对清单的更正与未决项

1. **gettext/libintl 确有实现代码随包。** 实际 libpython3.12.so 的动态符号表定义了 libintl_dcgettext、libintl_dgettext、libintl_gettext、libintl_textdomain、libintl_bindtextdomain、libintl_bind_textdomain_codeset；它们是非 UND 的 FUNC，不能按“没有 DT_NEEDED libintl”排除。已修正文档/NOTICE，并在机器清单增加待审项；准确版本、源码/补丁、许可仍缺。
2. **libedit 尚缺准确物料。** 实际 readline 扩展含 EditLine wrapper 标识。机器清单新增待审项，不能当成 GNU readline 或直接继承 Python 主许可。
3. **社区预编译包补丁/配置未取得。** B 已明确如实记录此缺口。上游发布版 URL 或版本字符串不能证明预编译包与该源码完全相同。
4. **SciPy OpenBLAS 的静态 Fortran 范围未被证明。** NEEDED 只有 libc 不足以确定它静态包含了哪种 Fortran 运行时、版本及许可；需构建配方或其他直接构建物料。此项不同于已有哈希匹配凭据的 8 个 GSAS 扩展 LLVM FortranRuntime 20.1.8。

本次不修改 distributionReview 为 approved。具体待补的是上述剩余项，已接收的 11 份文本及 6 个原始库的哈希不要求 B 重做。

## C 已完成的许可装配

新增 Stage-ThirdPartyLicenses.py，把核验后的 11 份原文及 3 份归属索引复制到新载荷。显式指定 cpython/numpy/scipy 的目录归属只是打包定位，不是许可继承。拒绝覆盖源载荷、已有输出、未定义归属和损坏文本。

新载荷 `c-native-8-license-review-20261020` 共 2239 文件，Write-RuntimeManifest/Prepare-Runtime 已通过；9 个原组件仍 pending。已使用原发布证书和指定设备 Profile 在私有副本构建 Release 候选包：

| 项目 | 结果 |
| --- | --- |
| 候选 HAP SHA-256 | `429b4d8cf066ec1a1754427110f72f8d54a01031a9c2e90c4b566c0485cdc2e6` |
| 包大小 | 158918099 字节 |
| 实际内容 | 2260 文件、224 ELF；2239 个运行时文件与新清单一致 |
| 应用签名和原生签名 | SDK verify-app/codesign 通过；嵌入 Profile 与原指定设备 Profile 一致 |
| 许可实际入包 | 11 份原文均按实际 HAP 字节匹配 SOURCES.json，已不是仅存在于源码仓库 |
| SBOM | 已为这一实际 HAP 重新生成草稿；待审状态保留 |
| 真机状态 | **未安装、未验收此新候选包**；旧 HAP 88ea4528… 的真机证据不移用 |

实际报告见 [c-third-party-20261020.json](../packaging/reviews/c-third-party-20261020.json)。完整候选包、清单和报告保存本机忽略的 app/build/third-party-review-20261020；旧已验收 HAP 与真机环境保留。

两个旧 GNU 帮助库仍在候选包中。实际图中未发现组外 DT_NEEDED 消费者，Python/JSON 中也未见两库全名引用；这支持后续在副本上的移除实验，**本轮未删除、未重签删除后的包，也未声称已安全移除**。SciPy 在用的 OpenBLAS 必须保留。

## 复现

```sh
python3.13 scripts/Audit-ThirdParty.py \
  --hap ACTUAL.hap --manifest RUNTIME_MANIFEST.json \
  --prebuilt-dir LOCKED_ARCHIVE_DIRECTORY --output NEW_REVIEW_DIRECTORY

python3 scripts/Stage-ThirdPartyLicenses.py \
  --payload ACCEPTED_PAYLOAD --output NEW_PAYLOAD
# 再用现有 Write-RuntimeManifest / Prepare-Runtime / Build-App 流程生成新包。
```

审查工具不执行 ELF，不改变签名或文件；不存在原始归档时可以省略 prebuilt-dir，但不能声称完成归档到实际包的对应复核。源代码与许可缺项补齐后再冻结最终载荷、重签并进行实际最终包的真机验证。
