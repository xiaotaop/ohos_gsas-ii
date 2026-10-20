# 应用组件清单初稿（成员 C）

用途：从正式工程建立时持续维护来源与分发范围。该表不是最终 HAP 的 SBOM，也不表示第三方运行时分发审计已完成。

状态说明：下表“当前 app 范围”是成员 C **最初开发 HAP 的历史收件快照**，不能当成现状。最新指定设备 internaltesting 签名 HAP 已含 2246 文件/224 ELF/2225 运行时文件并完成应用内五阶段；实际字节、动态依赖及 SBOM 草案见[C 交付](C_SIGNED_HAP_DELIVERY.md)。最终第三方源码/许可与 `distributionReview` 未关闭，C 仍须依据冻结的公开分发 HAP 核对最终 SBOM。

| 组件 | 当前 app 范围 | 来源/版本 | 后续处理 |
|---|---|---|---|
| C 的 FileService/页面/构建脚本 | 源码和开发 HAP | 本分支新增实现 | 保存源码提交、验证记录和构建指纹 |
| Ability/资源/工程模板 | 开发 HAP | 从本仓库 A 的 ui-mock 工程复用结构；页面业务已另实现 | 保留 NOTICE 和来源说明 |
| 五份 PbSO4 fixture | rawfile/fixtures | 固定上游 2b4aba1bc44de63a3da9d4495944c3b99e389399 的原始字节 | 与 tests/fixtures 哈希逐项核对；沿用 GSAS-II 主许可/NOTICE |
| C 的 libgsas_fileio.so | 开发 HAP | 本分支独立实现，私有目标排他创建；SDK FileURI/N-API | 与 B 的计算桥接分开维护 |
| libc++_shared.so | 开发 HAP，arm64-v8a | 本机 SDK API26 自动装配的 C++ 运行库 | 构建记录锁定包内哈希；rawfile/licenses 保留 LLVM 及 libc++/libc++abi 许可 |
| HarmonyOS 平台 API | 系统提供 | 编译 SDK API 26，最低20/目标24 | 不将完整 SDK 拷入 HAP；检查实际构建产物与系统能力 |
| CPython | 当前未打包 | 计划复用已验证 3.12.9 | 后续记录实际 OHOS 载荷来源、许可原文、源码与哈希 |
| NumPy / SciPy / PyCifRW | 当前未打包 | 计划 2.2.6 / 1.16.3 / 5.0.1 | 从 B 取得实际依赖图与构建说明，审计原生链接库 |
| GSAS-II 核心和原生扩展 | 当前未打包 | 固定上游提交 | 发布构建排除 pydiffax；处理 G2shapes 范围；核对相关源码义务 |
| flang / BLAS 等运行库 | 当前未打包 | 以实际载荷为准，不推断版本 | 向 B 获取来源、版本、许可和链接依赖 |
| mock/fake core | 当前 app 不包含 | ui-mock 与 bridge/fake_core 仅在仓库开发范围 | 发布装配时继续验证最终载荷排除 |

DevEco CLI、Hvigor、ohpm、Node.js 为构建工具，当前不是 app 的自带运行时组件。最终 SBOM 必须以实际发布 HAP 文件与链接关系为依据，不能直接把此计划表当作成品 SBOM。

后续收件使用 [运行时清单模板](../packaging/runtime-manifest.example.json)和 [装配流程](RUNTIME_PACKAGING.md)。Audit-Hap 对实际 HAP 生成逐文件哈希、运行时组件归属及许可记录，作为最终 SBOM 的基础；仍须补充静态/动态依赖分析、源码义务和人工审查。模板缺少真实载荷时明确失败，不将上述计划组件列为已经入包。
