# C：签名 HAP 交付与剩余阻塞

本记录补充 PR #8 的集成结果。**第 2 项仍未完成，不可用本 PR 作为正式安装包或许可证放行结论。**

## 最新指定设备签名结果

用户已创建并下载 `gsasii-device-release` Profile。验证其类型为 release、分发类型为 internaltesting，绑定的发布证书与原 gsasii-release 一致，包含 HAD-W32，权限未新增。新的 Release HAP SHA-256 为 `88ea4528b69f40458b0a17acbf0bb70720d9f29af3691b78438059299d2ace9e`（158785370 字节）；SDK 应用签名及 224 个原生签名通过，2246 个实际文件和 2225 个运行时文件通过哈希审计。50 个受版本控制的应用文件与 `609df2c` 一致（本机私有签名配置单独排除）。与之前普通发布签名包的 ZIP 内容逐成员比对也完全一致，仅外部签名/Profile 改变；新 SBOM 通过 CycloneDX 1.5 Schema。

新包覆盖安装不再报旧的来源错误，但报 `9568332: install sign info inconsistent`，与之前调试密钥安装的包签名身份不一致。旧应用仍可启动，未卸载。应用外 5 个原始输入和 3 个导出结果均经设备侧 SHA-256 核对；这不构成应用内文件索引、历史任务、设置的完整备份。卸载清理旧签名包须先取得用户明确同意，再以新签名包重新安装和复验；不能把 SDK 验证或一次失败安装算作真机通过。

本地产物位于忽略的 `app/build/device-release-1m8uiad2`。之前普通发布 Profile 的 9568322 记录保留为历史证据，下面的旧包哈希和旧验收结果也只适用于各自的实际包。第三方许可/源码审查仍未关闭。

## 已复核的交付物

下列两包的应用源码均为 `609df2cc79cc24cfdecd791871aa2345cf58023c`，运行时为 `c-native-8-zoifhpdn-v2`。两种 Profile 对应不同 HAP，安装和计算结论不能互换。

| 交付物 | SHA-256 | 结论 |
| --- | --- | --- |
| 发布证书 + 发布 Profile HAP | `16afa6b22cfcc5052e54e321f784944a5789d80cf3a3cf001f3ff3185d10a07a` | Release 构建、SDK verify-app 与 224 个 ELF 代码签名验证通过；HAD-W32 覆盖安装被拒绝 |
| 真机调试 Profile HAP | `1a5705920f2a8c013b8a0b7f211f60a2d1b2b38e7012de2e4508c79d2a17e7e2` | Release 构建；HAD-W32/API23 安装、Core:ready、系统选择器五输入、真实五阶段、独立数值比较、GPX/JSON/日志导出和成功任务重启恢复通过 |
| GSAS/移植源码伴随包 | `92125ab5792865e0b125d0d41c961c622bdb6f71f44e1a6c58963997ad309c57` | 718 个源文件/说明的逐文件清单；端口提交与上述 HAP 一致；不覆盖第三方预编译运行时的全部源码 |

机器可读记录见 [c-delivery-20261019.json](../packaging/reviews/c-delivery-20261019.json)。该记录包含实际 HAP 的清单/SBOM 哈希、原生依赖边及精简的真机证据，不含私钥、密码、Profile 原文、设备唯一标识或借用电脑的其他文件。

正式包这次执行 `hdc install -r`，设备返回：

```text
9568322: signature verification failed due to not trusted app source
```

此结果不能推断为证书损坏；SDK 的离线签名验证通过与设备信任该分发来源是两个检查。未卸载原应用、清除数据、绕过验证或改动设备安全设置。下一步准备设备支持的指定设备发布/测试分发 Profile，重新签名并验证实际安装的那个 HAP；若遇到签名身份不兼容，应先保留数据、报告错误，不能自动卸载。

## 实际 HAP 的许可证审查

重新运行合并后版本的 `Build-HapSbom.py`，逐字节核对 **2246 文件、224 ELF、8 个计算扩展及其静态 LLVM FortranRuntime/FortranDecimal 20.1.8 许可**。CycloneDX 草稿有 19 个组件记录，仍全部保留待审，不能只把 JSON 中的 pending 改成 approved。

| 范围 | 实际发现 | 关闭条件 |
| --- | --- | --- |
| LLVM FortranRuntime/FortranDecimal | 8 模块哈希与构建凭据、20.1.8 许可原文匹配，许可为 Apache-2.0 WITH LLVM-exception | 随最终 HAP 保留许可、构建凭据及源码地址，纳入最终复核 |
| CPython 附带 libffi/GDBM | HAP 中确有独立 ELF；GDBM 字符串报告 1.24 | 提供精确构建源码/修改、版本和各自许可；不能套用 PSF 许可 |
| NumPy 附带 OpenBLAS64/GNU Fortran | `libscipy_openblas64_.so` 仅消费 `libgfortran.so.5`，后者仅被它消费；未发现其他 ELF 的 DT_NEEDED 指向该组库 | B 确认是否需要；若排除，还需检查动态加载路径，生成新清单并重新构建/验收，不可把本报告视作删除授权依据 |
| SciPy 实际 BLAS | `libscipy_openblas-80d8b5fa.so` 被 23 个科学扩展消费，字符串报告 OpenBLAS 0.3.29 | 保留并补齐该构建的源码、许可和静态链接范围，不可连同旧帮助库删除 |
| CPython 静态第三方范围 | `_ssl` 中观察到 OpenSSL 1.1.1w；readline 模块为 EditLine wrapper。SQLite、bzip2、XZ、ncurses、Expat、libmpdec 等对应模块亦在包中 | B 提供各模块的配置、依赖源码/补丁、版本和许可原文；二进制字符串或 Python 主许可证不能替代这些凭据 |
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

关闭顺序：先解决设备接受的签名分发路线，同时补齐 B 的第三方依赖凭据；随后冻结必要的载荷改动、再生成清单/许可/SBOM/源码伴随包，签名实际 HAP 并复验安装与科学结果。最终哈希变更时，本记录的旧验收结果仅保留为历史证据。
