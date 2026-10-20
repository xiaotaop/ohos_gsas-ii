# C：第三方依赖与实际 HAP 复核

2026-10-20，已接收 PR #10 的 11 份许可及依赖声明，并补做社区来源追查、GNU readline 实现识别、两库精简实验和实际包 SBOM。**第 2 项仍未完成，分发审查保留 pending。**

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

## 新签名候选包与精简实验

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

剩余阻塞：预编译原生代码到精确源码/补丁/依赖构建的对应、GNU readline/gettext 的静态链接分发义务、SciPy 配置/BLAS 版本差异及 Fortran 静态范围；精简后新包的真机导入与五阶段验证。所有 distributionReview 仍 pending，第 2 项及上架未放行。

## 复现

```sh
python3 scripts/Stage-ThirdPartyLicenses.py --payload ORIGINAL_PAYLOAD --output LICENSED_PAYLOAD
python3 scripts/Prune-RuntimeOrphans.py --payload LICENSED_PAYLOAD --output NEW_PAYLOAD --receipt NEW_RECEIPT.json
# 使用现有 Write-RuntimeManifest / Prepare-Runtime / Build-App 生成新包后：
python3.13 scripts/Audit-ThirdParty.py --hap ACTUAL.hap --manifest MANIFEST.json \
  --prebuilt-dir LOCKED_ARCHIVES --output NEW_REVIEW
python3.13 scripts/Build-HapSbom.py --hap ACTUAL.hap --manifest MANIFEST.json \
  --native-build-receipt native-modules.json --third-party-review NEW_REVIEW/third-party-review.json --output NEW_SBOM
```

工具仅生成候选与待审证据。源码/许可问题关闭后还需冻结实际最终包，并按新哈希完成设备复验。
