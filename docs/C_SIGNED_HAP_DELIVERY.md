# C：签名 HAP 交付与剩余阻塞

本记录随 PR #9 合入主线，补充 PR #8 的集成结果。**第 2 项（最终第三方分发审查）仍未完成；指定设备 internaltesting 包不可作为公开商店安装包或许可证放行结论。**

2026-10-20：B 的 PR #10 材料已接收并按实际字节复核，11 份许可已装入新候选包；新候选未替代本记录的真机验收包。剩余缺项及两个包的范围见 [C_THIRD_PARTY_REVIEW](C_THIRD_PARTY_REVIEW.md)。

## 最新指定设备签名结果：安装与真实计算通过

用户已创建 `gsasii-device-release` Profile，类型 release、分发类型 internaltesting，绑定的发布证书与原 gsasii-release 一致，包含 HAD-W32，权限未新增。新的 Release HAP SHA-256 为 `88ea4528b69f40458b0a17acbf0bb70720d9f29af3691b78438059299d2ace9e`（158785370 字节）。SDK 应用签名及 224 个原生签名通过，2246 个实际文件和 2225 个运行时文件通过哈希审计。50 个受版本控制的应用文件与 `609df2c` 一致（本机私有签名配置单独排除）；与之前普通发布签名包的 ZIP 内容完全一致，仅外部签名/Profile 改变，新 SBOM 通过 CycloneDX 1.5 Schema。

覆盖旧调试密钥包曾报 `9568332: install sign info inconsistent`。用户明确同意卸载旧测试版并知悉状态丢失后，已核验应用外 5 输入/3 输出备份，卸载旧版、成功安装并启动新包。该记录是干净安装，不能作为同签名版本升级证明。

在这一份发布证书 + 指定设备 Profile 的 HAP 内，已在 **HAD-W32/API23** 完成：

- Core:ready；通过系统文件选择器导入五个原始输入，重新关联并校验完整性。
- 相名 PbSO4、maxCycles=3、输出 Release.gpx；实际任务 `job_ebcaac7e-895a-40a0-9926-a4e477f15850` 成功，耗时 8.642 秒。
- 从实际系统保存框导出 Release.json/Release.gpx/Release.log，按导出文件比较 Windows 基线：10 个 Rwp（rtol=1e-4）及两个择优取向系数（rtol=1e-3），atol=1e-7，全部通过。与先前调试 Profile 包的数值也一致。应用自身 validation.performed=false 原样保留，以上是独立比较。
- 完成导出后仅重启目标应用进程；同一成功任务、8 个文件索引及 Core:ready 恢复通过。

本地产物和原始证据位于忽略的 `app/build/device-release-1m8uiad2`，含签名日志、安装日志、完整 SBOM/inventory、导出结果、比较记录及应用自身页面截图。没有将私钥、密码、签名配置或系统选择器中借用设备的其他文件信息提交到仓库。该 Profile 为指定设备测试分发，并非应用市场公开发布。

**安装与签名阻塞已经解除；第 2 项仍差第三方预编译运行时的精确源码/版本/许可审查。** 本记录不覆盖 API20/API24、同签名覆盖升级、活动任务取消/中断或上架放行。之前 9568322、9568332 及下表旧包结论保留为历史证据。

## 已复核的交付物（下表为指定设备包之前的历史版本）

下列两包的应用源码均为 `609df2cc79cc24cfdecd791871aa2345cf58023c`，运行时为 `c-native-8-zoifhpdn-v2`。两种 Profile 对应不同 HAP，安装和计算结论不能互换。

| 交付物 | SHA-256 | 结论 |
| --- | --- | --- |
| 发布证书 + 发布 Profile HAP | `16afa6b22cfcc5052e54e321f784944a5789d80cf3a3cf001f3ff3185d10a07a` | Release 构建、SDK verify-app 与 224 个 ELF 代码签名验证通过；HAD-W32 覆盖安装被拒绝 |
| 真机调试 Profile HAP | `1a5705920f2a8c013b8a0b7f211f60a2d1b2b38e7012de2e4508c79d2a17e7e2` | Release 构建；HAD-W32/API23 安装、Core:ready、系统选择器五输入、真实五阶段、独立数值比较、GPX/JSON/日志导出和成功任务重启恢复通过 |
| GSAS/移植源码伴随包 | `92125ab5792865e0b125d0d41c961c622bdb6f71f44e1a6c58963997ad309c57` | 718 个源文件/说明的逐文件清单；端口提交与上述 HAP 一致；不覆盖第三方预编译运行时的全部源码 |

机器可读记录见 [c-delivery-20261019.json](../packaging/reviews/c-delivery-20261019.json)。该记录包含实际 HAP 的清单/SBOM 哈希、原生依赖边及精简的真机证据，不含私钥、密码、Profile 原文、设备唯一标识或借用电脑的其他文件。

此前普通发布 Profile 包执行 `hdc install -r`，设备返回：

```text
9568322: signature verification failed due to not trusted app source
```

此历史结果不能推断为证书损坏；SDK 的离线签名验证通过与设备信任该分发来源是两个检查。之后已取得指定设备 Profile，并在用户明确授权、备份外部数据后解决旧调试密钥不兼容问题，成功安装本页开头所列 HAP。今后遇到签名身份不兼容仍须先保留数据、报告错误，不能自动卸载。

## 实际 HAP 的许可证审查

重新运行合并后版本的 `Build-HapSbom.py`，逐字节核对 **2246 文件、224 ELF、8 个计算扩展及其静态 LLVM FortranRuntime/FortranDecimal 20.1.8 许可**。CycloneDX 草稿有 19 个组件记录，仍全部保留待审，不能只把 JSON 中的 pending 改成 approved。

| 范围 | 实际发现 | 关闭条件 |
| --- | --- | --- |
| LLVM FortranRuntime/FortranDecimal | 8 模块哈希与构建凭据、20.1.8 许可原文匹配，许可为 Apache-2.0 WITH LLVM-exception | 随最终 HAP 保留许可、构建凭据及源码地址，纳入最终复核 |
| CPython 附带 libffi/GDBM | HAP 中确有独立 ELF；GDBM 字符串报告 1.24 | 提供精确构建源码/修改、版本和各自许可；不能套用 PSF 许可 |
| NumPy 附带 OpenBLAS64/GNU Fortran | `libscipy_openblas64_.so` 仅消费 `libgfortran.so.5`，后者仅被它消费；未发现其他 ELF 的 DT_NEEDED 指向该组库 | B 确认是否需要；若排除，还需检查动态加载路径，生成新清单并重新构建/验收，不可把本报告视作删除授权依据 |
| SciPy 实际 BLAS | `libscipy_openblas-80d8b5fa.so` 被 23 个科学扩展消费，字符串报告 OpenBLAS 0.3.29 | 保留并补齐该构建的源码、许可和静态链接范围，不可连同旧帮助库删除 |
| CPython 静态第三方范围 | `_ssl` 中观察到 OpenSSL 1.1.1w；readline 包装器含 EditLine wrapper 标签；后续 ELF 对象核对识别 GNU readline 8.3（见最新 C 记录）。SQLite、bzip2、XZ、ncurses、Expat、libmpdec 等对应模块亦在包中 | B 提供各模块的配置、依赖源码/补丁、版本和许可原文；二进制字符串或 Python 主许可证不能替代这些凭据 |
| GSAS/移植代码及其修改 | 原许可、NOTICE、排除范围和补丁在源码伴随包中 | 随二进制交付该包，并复核修改作者/差异；不能只提供源码 URL |

当前未匹配依赖名仍为 `libc.musl-aarch64.so.1` 与 `libgcc_s.so.1`，来自上述 GNU 帮助库。为保持真机证据与 HAP 哈希一致，本次没有悄悄删除库或改变已验收载荷。静态库候选列表记录的是待核范围，不声称仅凭模块名已确定完整静态物料。

## 复现源码交付

先从 `scripts/ohos/local-cross/sources.lock.json` 的 GSAS URL 下载归档。工具会自行校验锁定 SHA-256，拒绝不匹配的归档、路径穿越、构建源码中的符号链接和已有输出文件；不执行归档内容。

```sh
python3 scripts/Build-SourceCompanion.py \
  --source-commit 609df2cc79cc24cfdecd791871aa2345cf58023c \
  --upstream-archive GSAS-II-2b4aba1b.tar.gz \
  --output gsas-source-companion-609df2c.tar.gz
```

端口源码读取指定提交的 `git archive`，不会混入工作区签名配置修改或未跟踪的私钥。上游源按锁定归档取得，排除 DIFFaX、G2shapes.py 和非构建必需的渲染文档；保留相关 GSAS Python/原生源码、原许可及移植构建补丁。未声称这是整个预编译 CPython/NumPy/SciPy 分发的完整对应源码。

源码伴随包、HAP、完整 SBOM/inventory 和原始验收记录保存在本机忽略的 `app/build` 交付目录，不上传私钥、签名配置或借用设备的其他文件。仓库只提交可复现工具和脱敏核验摘要；未创建公开 Release 或提交应用上架。

后续关闭顺序：补齐 B 的第三方依赖源码/版本/许可凭据；如需精简载荷，冻结改动后重新生成清单、许可、SBOM 和源码伴随包，再签名实际 HAP 并复验安装与科学结果。最终哈希变更时，本记录的旧验收结果仅保留为历史证据。

2026-10-20 后续：C 已完成 13 份许可装配、两库精简签名候选和实际 HAP SBOM，见 [最新复核记录](C_THIRD_PARTY_REVIEW.md)。本文件的 88ea4528… 数值/真机证据仍仅对应原包，不能作为 fcd8d215… 新候选的验收。

2026-10-20 最新补充：16 份许可、两库精简的 `25c9ef74…` 已在同一 HAD-W32/API23 通过同签名覆盖、五阶段 8.641 秒、12 项数值比较、系统导出及成功任务恢复（11 文件）。详见 [最新 C 复核](C_THIRD_PARTY_REVIEW.md) 和对应哈希验收凭据。另一个 CPython 核心重建实验仅通过离线检查，尚未安装。
