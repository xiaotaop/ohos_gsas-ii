# C：签名包最终 SBOM 与许可材料审查

后续版本：0.1.1 / versionCode 2（`70588bde…`）已完成[成员 C 阶段三验收](C_PHASE3_ACCEPTANCE.md)及[同包最终审查](../packaging/reviews/70588bde-final/review-summary.json)。仅四个版本元数据字段变化，运行时/许可字节已重核一致；新设备证据、源码伴随和 SBOM 重新绑定。下文 `1190b1d5…` 是第 2 阶段固定历史快照，保留原结论与字节。

2026-10-20：**成员 C 对这份指定设备 internaltesting HAP 的工程交付、SBOM 和许可材料审查已完成。** 本结论仅覆盖同一 HAP 与完整伴随材料；组长的最终发布放行、商店包和公开分发未被授权或宣称通过。

## 固定交付

| 项目 | 最终记录 |
| --- | --- |
| HAP SHA-256 | `1190b1d5be7fa4520ed519f316db8f4035bb555aaaf8864295bd415aa23ce4e5` |
| HAP 大小 | 135975415 字节，原已验收字节未修改 |
| runtimeId | `c-controlled-license-prototype-20261020`；保留构建时名称，不据此否定后续实际验收 |
| SBOM SHA-256 | `73bc089265a01dc182fb657cfc82fb8836f3119747cb122df4f675cfd3e1d775` |
| 实际范围 | 2266 文件、219 ELF、27 个随包逻辑组件、4 个排除的平台组件、485 条原生 NEEDED 关系；无未匹配名称 |
| 许可材料 | HAP 中 19 份第三方许可/版权集合，另有原项目、Python 等许可；完整交付附可读 THIRD-PARTY-NOTICES.txt，补齐 Python incorporated notices 与 OpenBLAS 上游版权集合 |
| 设备证据 | HAD-W32/API23，同签名覆盖、旧输入保留、Core ready、真实五阶段 8.664 秒、12 项独立数值比较、GPX/JSON/日志系统导出、成功任务重启恢复 14 文件均通过 |

[最终 SBOM](../packaging/reviews/1190b1d5-final/hap-sbom.cdx.json)、[审查决策](../packaging/reviews/1190b1d5-final/review-decisions.json) 和 [摘要/材料哈希](../packaging/reviews/1190b1d5-final/review-summary.json) 已纳入仓库。原始观察、逐项绑定证据和可读版权材料在同目录，不要求仅凭本文相信“已完成”。

## 审查处置

| 原问题 | 实际处理与结论 |
| --- | --- |
| GNU 静态/动态范围 | 新核心按固定源码/补丁编译且禁用 libintl；原核心被替换。GDBM、_gdbm、GNU readline、GNU Fortran 帮助库和闲置 OpenBLAS64 不在实际 HAP；219 ELF 的指定已定义函数标记扫描无匹配。不是仅凭没有 DT_NEEDED 推断未包含。保留的 GNU 许可证只是文本文件，不生成相应库组件。 |
| DIFFaX/Shapes | 实际 HAP 与提供的 GSAS 相关源码归档均排除 pydiffax/DIFFaX 和 G2shapes.py；原主许可中对其提及仍保留，不能篡改原许可。 |
| 原生源码交付 | GSAS/移植伴随包含 771 个文件，50 个实际 app 源文件哈希一致；核心伴随包含官方归档、81 个补丁、C 的增量和配方共 87 项。核心源码准备结果与编译输入 4556 个文件逐字节相同。没有声称完整重跑编译脚本或位级可复现。 |
| PyCIFRW | SBOM 使用实际 ANSTO PyCIFRW License Agreement 名称及原文，不将其自定义协议简写为 PSF-2.0。 |
| 宽松许可组件 | 实际许可/版权和伴随材料逐项保留。未知补丁集如实披露，不再把维护者联系方式、精确编译日志或源码位级复建当作所有宽松许可的共同前提。 |
| SciPy 配置差异 | 0.3.33 是生成配置声明，0.3.29 是实际 BLAS 标记；二者都记录。数值验收通过，不冒称已证明全部 ABI 或精确社区构建配方。此项作为非阻塞来源观察保留。 |
| SciPy 静态 LLVM | 115 个原始 SciPy 库装载节已绑定，14 个消费者实际定义 LLVM runtime 函数，许可/例外原文已保留。编译器 22.1.8 不能代替准确静态归档版本，最终 SBOM 省略未证实版本，保留原声明为观察。此来源精度限制已明确接受。 |
| 系统依赖 | libace_napi.z.so、libc.so、libohfileuri.so、libz.so 标记 scope=excluded；只记 SDK 文件名观察，不假称它们随包分发或猜测系统版本/许可。 |

[Apache 2.0 原文第 4 节](https://www.apache.org/licenses/LICENSE-2.0) 和 [Python 官方许可及 incorporated notices](https://docs.python.org/3.12/license.html) 用于对照分发材料要求；实际入包文本和固定源码版本仍以逐哈希证据为准。对社区预编译的版本/补丁精度限制予以披露，不等于替其作虚假的来源证明。

## 可复核和交接

Finalize-HapSbom.py 必须重新核对 HAP 内容、原草稿/观察报告的 canonical JSON 哈希、每项审查证据、同 HAP 设备验收、每个逻辑组件和每条发现的处置、实际许可哈希、原生关系以及所有文件/引用。没有审查决策或输入变化就拒绝生成；不会自动授予公开发布权限。GSAS、libffi、BLAS 等重复声明已合并，版权集合归属文档而不冒充额外原生库。

本地完整交付目录为原仓库忽略的 `app/build/member-c-step2-reviewed-1190b1d5/`，含签名 HAP、最终 SBOM、运行时清单、可读版权材料、两份源码归档、审查记录和 SHA256SUMS。**须整套交接，不能只分发 HAP 而丢弃源码和许可材料。** 未含私钥、密码、Profile 或私人设备转储。

复核最终 SBOM 的示例（在该目录执行，工具路径指向本仓库）：

```sh
python3 /absolute/path/to/repo/scripts/Finalize-HapSbom.py \
  --hap entry-default-signed.hap --manifest runtime-manifest.json \
  --draft hap-sbom.original-draft.cdx.json \
  --report review/third-party-observations.json \
  --review review/review-decisions.json --evidence-dir review/evidence \
  --output NEW-hap-sbom.cdx.json
```

旧原始报告中的 pending/step2Complete=false 是当时自动审查快照，予以保留；新结论由本次外部哈希绑定审查覆盖。没有改写 HAP 内的历史清单，也没有通过改 pending 来绕过普通发布构建门禁。任何实际 HAP 或必需伴随材料变化都需要重新绑定结论。

下一阶段是同一版本的团队联合验收、API20/API24 与生命周期矩阵，以及组长最终放行；不再因本次已关闭的安装或许可材料事项要求 B 重交不存在的自有构建日志。
