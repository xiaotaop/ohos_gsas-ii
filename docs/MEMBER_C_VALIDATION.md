# 成员 C 阶段 1/2 验证记录

状态提示（2026-10-20）：以下是 C01/C02 的历史开发验收；完整运行时签名 HAP 的后续指定设备证据见[C_SIGNED_HAP_DELIVERY](C_SIGNED_HAP_DELIVERY.md)，当前放行条件见[RELEASE_ACCEPTANCE](RELEASE_ACCEPTANCE.md)。

验证范围：成员 C 的 C01 正式工程、C02 文件服务；分支 `release/stages-1-2`，基线 main 为 `12db7e78cf689ef032438139d6819d76fd1a7c99`。验证日期：2026-10-15（America/Chicago）。本次未接入计算核心。

## 2026-10-17 交接复核（北京时间）

本次仅更新交接、对齐及 CI 说明文档，app/测试/构建脚本未改；实现仍对应 `3d6957d`。重新执行契约语义校验、11 份 JSON 校验、五份 fixture SHA-256、宿主文件服务九项测试及原生排他创建测试，均通过。另检查交接相关文档的本地链接和锚点，未发现失效引用。

本机未安装 jsonschema，契约工具使用标准库语义校验。此次未重复 DevEco 构建及设备测试，下面的平台结果仍为原验证记录；不把文档提交称为新的真机或核心计算验收。交接提交的云端结果以对应合并请求的 Repository verification 为准。

## 结果与范围

| 检查 | 结果 |
|---|---|
| ArkTS | 全部 7 个 .ets 文件，0 错误；SDK 异常传播提示由调用层处理 |
| Code Linter | 最终源码 0 问题；独立副本中 7 个违规探针准确报告 7 文件/7 错误，证明实际扫描 |
| Release 构建/安装/启动 | PASS，包含文件创建 N-API 辅助模块，Smoke PASS |
| 平台文件测试 | 18 PASS / 0 FAIL / 1 SKIP |
| 宿主文件服务 | TypeScript 5.4.5，直接运行实际服务源码，9 PASS / 0 FAIL / 0 SKIP |
| 原生排他创建 | 实际生产头文件在宿主编译执行，已有空文件、并发抢先创建、符号链接不被覆盖 |
| 系统选择器导出 | PASS，取回 49,445 字节，与原 fixture 逐字节一致 |
| 同名冲突/取消 | PASS，系统弹出替换确认；取消后原文件保留 |
| 覆盖安装 | PASS，旧版没有 deleting 字段的索引兼容，恢复 1 个原有文件 |
| 仓库契约/JSON/fixture | PASS，11 个 JSON、契约语义、五份原始数据 SHA-256 |
| Bridge 既有测试 | 20 项，18 通过/2 跳过；本机未装 jsonschema/真实 GSAS-II 运行时 |
| ArkUI mock 模型 | TypeScript 5.4.5 编译，6 项全通过；四份 mock 资源与契约文本一致 |

平台跳过项仅为“创建符号链接夹具”：SDK API11 起禁止第三方应用使用该创建接口，原生 POSIX 试验也被系统权限拒绝。因此**不能称为设备符号链接动态拒绝通过**。该防护通过宿主真实文件系统补验：运行实际 SandboxFileService 源码，动态覆盖载荷、父目录、根目录、元数据、输出及导出目标符号链接，验证外部内容不变。生产 N-API 模块只有排他创建接口，没有测试夹具后门。

本机平台是 MateBook Pro 1 / HarmonyOS 7.0.0 API26 PC 模拟器，DevEco Studio 26.0.0.821、CLI 1.3.5。兼容/目标 API 20/24 沿用项目范围；本次不声称 API20/24 真机验收完成。

## 交付物与可追溯性

Git 忽略的本地开发包：`app/build/deliverables/gsas-pc-files-0.1.0-release-unsigned.hap`。

HAP SHA-256：

```text
892bb8d661ed4a825a7bdf44aa987fcfd3a2c95c830f40e8830cc5f90e9c4275
```

37 个工程源文件与最终构建目录逐项字节一致；源码清单 SHA-256：

```text
d90889c476aa3a59c717d8e98256d1509cbb28aaad86894ab29dec735350689c
```

`app/build/deliverables/build-record.json` 保存每个源文件、构建脚本、HAP 和包内两份 .so 的 SHA-256。源码指纹按路径排序后，对紧凑 JSON 的 sourceFiles 数组取 SHA-256。五份包内 fixture 与 tests/fixtures 的原始字节一致；五份许可证与源码中的副本一致。

HAP 仅含 `libgsas_fileio.so` 和 SDK 的 `libc++_shared.so`，不含 Python、科学计算原生库、pydiffax 或 fake core。对应 SDK LLVM/libc++/libc++abi 许可及 GSAS-II LICENSE/NOTICE 均保留在 rawfile/licenses。该组件清单不是最终应用 SBOM。

## 导出行为

沙箱目标通过原生 `O_EXCL | O_NOFOLLOW` 原子创建，已有空文件和外部并发抢先创建均返回失败，不覆盖内容。系统保存 URI 则由 DocumentViewPicker 预创建授权空文件，应用通过 FileIO URI 接口写入；系统负责同名确认，应用拒绝仍有内容的目标。已实际看到“文件已存在，要替换它？”并验证取消；不能将系统预留空槽与外部已有文件混为一谈。调用方应使用 FilePickerService，不得把导入 URI 作为保存授权槽。

真实导出文件 SHA-256：`CA2DA02FC7E17D2FC912DE22A979F8101BA6140F2E8104F9D3AA64F030CA58BB`。

还修复了同一输出路径被不同 fileId 重复登记的问题，避免删除一项后使另一项失效；旧版索引缺少 deleting 字段按 false 兼容，非法字段类型拒绝打开。冻结 CORE_API、Schema、示例未改动。

## 复现与证据

```sh
python3 scripts/Build-App.py --check --build-mode release --device 'MateBook Pro 1'
GSAS_TYPESCRIPT_PATH=/path/to/typescript node --test tests/file-service-host.test.cjs
c++ -std=c++17 -Wall -Wextra -Werror tests/file-exporter-native.test.cpp -o /tmp/gsas-exclusive-test
/tmp/gsas-exclusive-test
```

仓库 CI 安装 TypeScript 5.4.5 执行宿主测试；该转译用于测试实际服务逻辑，不能代替 DevEco 的 ArkTS 检查和 HAP 编译。

- [最终设备验证截图](evidence/member-c/release-file-checks.png) / [设备 UI 树](evidence/member-c/release-file-checks.json)
- [宿主回归输出](evidence/member-c/host-file-service-checks.txt)
- [静态检查结果](evidence/member-c/code-linter.json) / [独立副本的预期违规探针](evidence/member-c/linter-coverage.json)
- [系统真实导入截图](evidence/member-c/system-picker-import.png)
- [真实导出 UI 树](evidence/member-c/system-picker-export.json) / [同名确认](evidence/member-c/system-save-conflict.json) / [取消](evidence/member-c/picker-cancel.json)

## 后续集成

A 可接入 FileLibrary/选择器；B 可接入 CoreConfig、输入解析、任务引用和产物登记。真机签名、计算核心 N-API、CPython/科学计算包装配、真实精修、最终 SBOM 与发布验收属于后续阶段。文件角色及日志交接仍按交接文档作为实现提案供组长审核；该开发 HAP 不作为发布候选。
