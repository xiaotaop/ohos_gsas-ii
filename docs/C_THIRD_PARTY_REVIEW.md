# C：第三方依赖与实际 HAP 复核

2026-10-20，已接收 B 的依赖处置确认，完成 16 份许可候选包的 API23 真机验收，并新增科学库静态范围审查。另补齐上游内嵌版权文本、试建不含 libintl 的 CPython 核心；实验候选尚未通过设备验收。**第 2 项仍未完成，分发审查保留 pending。**

## 已核实与更正

- B 的 11 份许可大小/SHA-256 与 SOURCES.json 一致。锁定的 CPython/NumPy/SciPy 原始归档正确；6 个声明库的原始哈希均匹配。首轮 HAP 的 6 库装载节（除 .codesign）与原始库一致，见保留的 [首轮报告](../packaging/reviews/c-third-party-20261020.json)。
- libpython 确实定义 6 个 libintl 函数。不能按没有 DT_NEEDED libintl 排除静态实现。
- **撤回首轮仅凭 EditLine wrapper 推断 libedit 的依据。** CPython 包装器含两套实现标签。实际 ELF 的 `rl_library_version` 相对重定位指向 `8.3`，`rl_readline_version=0x803`、`rl_gnu_readline_p=1`，并定义 `_rl_dispatch_subseq`。当前证据识别为 **GNU readline 8.3**，不把 libedit 计作已证实分发组件。审查工具只读 ELF，不执行库。
- 已从 GNU 官方归档补入 readline 8.3 COPYING 与 gettext 0.26 的 intl/COPYING.LIB 原文；共 13 份文本保留原始字节及源归档哈希。GNU readline 上游声明 GPL-3.0-or-later，libintl 0.26 上游声明 LGPL-2.1-or-later；精确预编译源码/补丁与静态链接分发义务仍待核，**许可文本入包不是分发批准**。
- SciPy 实际 `__config__.py` 声明 clang 15.0.4、llvm-flang 22.1.8、OpenBLAS 0.3.33；随包 BLAS 的字面标记为 0.3.29。已记录配置/二进制版本差异，不能自行解释为 ABI 错误或静态 Fortran 版本。8 个 GSAS 扩展的 LLVM 20.1.8 构建凭据与此是两个范围。

## 社区源码追查

[来源追查记录](../packaging/reviews/community-source-trace-20261020.json) 固定了公开仓库提交与文件哈希：

- [distro 配方](https://gitcode.com/OpenHarmonyPCDeveloper/distro/blob/f9fca0d7dee23113b09b7f8ca10784ccbf81b593/packages/python.json) 声明的 CPython 归档 SHA-256 与本机锁定输入 `767b7ef4…163576` 完全相同。
- [CPython 补丁仓库](https://gitcode.com/OpenHarmonyPCDeveloper/cpython/tree/135d712079ae8881b73aa94c4c01c7469ab11e8d) 提供构建指南和 `3.12.9@k1.13` 系列。指南称 80 个补丁，当前系列实际列出 82 个；在官方原始源码上按发行方 git apply 参数试用，81 个成功，0125 的 venv 补丁失败。与归档内可对应的 684 份 Python 文件比较，683 份相同，差异为 Lib/venv/__init__.py。
- 发行方提及的 build-meta.json 下载返回 HTTP 404，尚不能绑定准确 patches_commit。公开补丁线索和 Python 文件比较不能证明所有原生代码、依赖补丁与当前预编译包完全对应。
- 科学 wheel 的公开仓库 Git 入口读取返回 HTTP 400；已保留 wheel 自带配置观察，未取得原始配方/日志。

## 两库精简候选（历史快照）

Prune-RuntimeOrphans.py 先检查组外 DT_NEEDED、ELF 文件名常量及 Python/JSON 引用，再复制到新目录，仅删除 `libgfortran.so.5` 与 `libscipy_openblas64_.so`。原载荷、许可文本及旧验收 HAP 保留；NumPy RECORD 的原始声明也保留，不能把它用作精简后完整性清单。实际完整性以重新生成的运行时清单和 HAP 清单为准。

| 项目 | 新候选结果 |
| --- | --- |
| runtimeId | `c-native-8-pruned-review-20261020` |
| HAP SHA-256 | `fcd8d21523d323f8472fe11b59818cb392a9b8681971ff823e75877449c7be09` |
| 大小 | 135838100 字节；比首轮许可候选 429b4d8c… 少 23079999 字节 |
| 内容 | 2260 文件、222 ELF；2239 个运行时文件与清单一致 |
| 精简 | 移除库的未压缩体积共 22944768 字节；实际 HAP 两库均不存在 |
| 原生门禁 | 8 个 GSAS 模块 AArch64 门禁通过；实际 ELF 图 unmatchedNames 为空；在用 SciPy OpenBLAS 保留 |
| 签名 | 发布证书 + 原指定设备 Profile，SDK verify-app/codesign 全部通过 |
| 许可与 SBOM | 13 份许可原文实际入包；新包 SBOM 引入逐哈希绑定的待审第三方声明，通过官方 CycloneDX 1.5 schema 与引用校验 |
| 真机 | **新包尚未安装/验收。** 检查时仅模拟器连接；旧已验收 88ea4528… 的 API23 数值/导出证据不移用 |

实际审查见 [新包报告](../packaging/reviews/c-third-party-pruned-20261020.json) 与 [精简凭据](../packaging/reviews/c-orphan-removal-20261020.json)。本机完整 HAP、清单、SBOM、签名结果及已取得的源码归档保存在忽略的 `app/build/licensed-pruned-20261020`。首轮 429b4d8c… 候选及其报告保留为历史记录。

## 还需要确认的内容

C 继续负责社区来源核对、实际字节/许可装配、静态依赖范围、候选包和真机验收。[PR #12](https://github.com/xiaotaop/ohos_gsas-ii/pull/12) 已确认 B 未自行编译、修改或替换社区二进制；必要事实确认已接收，不再索要不存在的自有构建日志。B 不知道的社区构建记录由 C 追查或评估自构建。该 PR 的 gettext/readline 两处旧判断与实际 ELF 证据不符，已在 [对接记录](C_B_HANDOFF.md) 标明更正；不影响 B 的处置声明，也不改变当前 HAP。已收到的 11 份文本、归档哈希和逐库清单不要求重做。

## 已完成的最新设备验收

[16 份许可包的验收凭据](../packaging/reviews/c-scope-acceptance-20261020.json) 绑定同一实际 HAP：

- SHA-256 `25c9ef7456af6fe34feed6be5bb746b82b7a92a298f9b4ab5baac64676208514`，135854818 字节；2263 文件、222 ELF、2242 个运行时文件。
- 发布证书 + 指定设备 internaltesting Profile；SDK 签名验证通过。HAD-W32/API23 同签名覆盖安装，无卸载；UID 和首次安装时间保留，五个旧输入及其关联保留。
- Core ready、真实五阶段 8.641 秒、12 项独立 Windows 数值比较、GPX/JSON/日志系统选择器导出均通过；实际重启应用进程后同一成功任务和 11 个文件索引恢复。
- 这次 versionCode 仍为 1，不能称为递增版本升级验收；未覆盖 API20/API24 或运行中取消、并发、中断。应用自身 validation.performed 仍为 false，数值比较由独立脚本完成。
- 完整 HAP、签名、SBOM 和脱敏设备证据留在忽略的 app/build/license-scope-20261020。旧候选的“尚未验收”仅描述各自历史哈希，不代表 25c9ef74… 当前状态。

## 科学库静态范围与版权补齐

Audit-ScientificRuntime.py 从锁定的 SciPy wheel 只读原始 ELF，验证实际 HAP 除准确 DT_NEEDED 归一化及签名以外的装载节一致，绑定 **115 个 SciPy 原生库**。其中 **14 个消费者实际定义 LLVM FortranRuntime 函数**，编译注释包含 flang 22.1.8；[绑定快照](../packaging/reviews/c-scientific-elf-20261020.json) 保留了消费路径及实际哈希。这是符号/编译器观察，不能冒充运行时静态归档的精确哈希。

在用 OpenBLAS 的原始 FILE 符号含 dgeev.c、dgesdd.c 等 C 版 LAPACK 文件名。补入 LLVM 22.1.8、Netlib LAPACK 与 LAPACKE 原文，16 份文本已进入上述实际验收包。不得用只有 OpenBLAS 根许可证替代 Netlib/Intel 的版权条件。

随后从 SHA-256 固定的 NumPy 2.2.6、SciPy 1.16.3 官方 sdist 补齐内嵌版权文本与含许可证的源文件，共 20/37 个上游文件，包含 Qhull、HiGHS、SuperLU、ARPACK、xsf 等。收集范围是保守上游集合，不声称每项都进入实际二进制；原文/逐文件哈希见 packaging/licenses/third-party/BUNDLED-SOURCES.json。它们是新增候选材料，**不声称已经位于 25c9ef74… 验收包中**。Collect-BundledNotices.py 可从固定归档重新生成相同字节，不执行归档代码。

## C 自行构建的 CPython 实验

见 [实验配方](../scripts/ohos/controlled-cpython/README.md) 及 [编译凭据](../packaging/reviews/c-controlled-core-prototype-20261020.json)。官方源码 + 固定社区补丁 + C 的 configure 增量已成功编译不含 libintl 的核心；218 个保留消费者的 Python 符号依赖得到满足，关键 ABI 宏一致。派生载荷排除了未使用的 GNU readline、_gdbm 与 libgdbm；保留的其他社区标准库扩展不冒称已重建。

补齐 19 份许可/内嵌版权集合的实验 HAP 为 `1190b1d5be7fa4520ed519f316db8f4035bb555aaaf8864295bd415aa23ce4e5`（135975415 字节、2266 文件、219 ELF）。实际 115 个 SciPy 库装载节绑定、19 份许可集合、无 unmatched NEEDED、官方 CycloneDX 1.5 schema 均通过；对 219 个 ELF 的已定义函数扫描未发现 libintl_/gdbm_/rl_/_rl_/_gfortran_ 标记。这只描述所检标记，不能声称识别了所有第三方代码。完整候选保存在忽略的 app/build/controlled-notices-prototype-20261020，原 25c9ef74… 包保留。

实验 HAP 通过离线签名及内容校验，但安装前无线端口断开且 TCP 超时，尚未安装/验收。等待网络恢复后运行相同五阶段、数值、系统导出及重启检查；在此之前不能以符号覆盖替代真机结果，也不替换已验收载荷。另补入 SDK compiler-rt 15.0.4 的上游许可，明确只适用于实验核心输入。

剩余工作是验证并冻结实际最终载荷、更新最终 SBOM/源码伴随包和许可范围。原已验收包仍有 GNU 静态分发闭环待核；新核心方案旨在排除此范围，尚待实际兼容性验证。宽松许可组件保留上游版权与条件，不把“每个组件必须提供维护者联系方式或完整编译日志”当作通用要求。所有 distributionReview 仍 pending，第 2 项及上架未放行。

## 复现

```sh
python3 scripts/Stage-ThirdPartyLicenses.py --payload ORIGINAL_PAYLOAD --output LICENSED_PAYLOAD
python3 scripts/Prune-RuntimeOrphans.py --payload LICENSED_PAYLOAD --output NEW_PAYLOAD --receipt NEW_RECEIPT.json
# 使用现有 Write-RuntimeManifest / Prepare-Runtime / Build-App 生成新包后：
python3.13 scripts/Audit-ScientificRuntime.py --hap ACTUAL.hap --manifest MANIFEST.json \
  --prebuilt-dir LOCKED_ARCHIVES --output SCIENTIFIC.json
python3.13 scripts/Audit-ThirdParty.py --hap ACTUAL.hap --manifest MANIFEST.json \
  --prebuilt-dir LOCKED_ARCHIVES --scientific-receipt SCIENTIFIC.json --output NEW_REVIEW
python3.13 scripts/Build-HapSbom.py --hap ACTUAL.hap --manifest MANIFEST.json \
  --native-build-receipt native-modules.json --third-party-review NEW_REVIEW/third-party-review.json --output NEW_SBOM
```

工具仅生成候选与待审证据。源码/许可问题关闭后还需冻结实际最终包，并按新哈希完成设备复验。
