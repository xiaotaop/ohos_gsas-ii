# 运行时装配与构建留档（成员 C）

本增量提供宿主装配工具、HAP 内容门禁和发布验收清单。B 的计算 N-API、设备侧 runtimeRoot 装配与应用内初始化已在 `core/napi-runtime` 分支交付（见 [PHASE3_NAPI_CORE](PHASE3_NAPI_CORE.md)）；真实 aarch64 运行时载荷、C03 应用沙箱加载、真实精修与最终发布验收仍未完成，工具通过不代表这些环节闭环。基于 C01/C02 交接分支开发，原交接 PR 单独审核。

## 1. 无运行时的开发包

在仓库根目录执行：

```sh
python3 scripts/Build-App.py --check --build-mode release
```

脚本使用系统临时目录，不再固定为 `/private/tmp`。临时目录含中文时，指定已存在的英文目录，例如 macOS/Linux 的 `--stage-root /tmp`；Windows 可指定 `--stage-root C:/gsas-build`。Windows npm 的 .cmd 入口通过 Node.js 运行已安装包的 cli.js，避免 cmd.exe 对路径/设备名的二次解释。Windows/Linux 构建分支尚需接收方的实际 SDK 环境验证；本机验证范围见本文件第 6 节。

每次创建独立英文工程目录。默认结果保留在 Git 忽略的 `app/build/deliverables/gsaspc-*/`；可用 `--output-dir` 指定另一个**不存在**的目录。输出包括：

- 实际 HAP 与每个 HAP 的 `.inventory.json` 内容清单，逐项记录大小和 SHA-256。
- `build-record.json`：Git 提交、工作区是否有改动、原 app 源码指纹、实际构建输入指纹、脚本/清单指纹、Python/Node/CLI/Git 版本、HAP 内编译 SDK/目标 API/版本信息、HAP 和清单哈希。
- 提供运行时后另保存 `runtime-manifest.json` 及其哈希；不保存签名私钥。SDK 缓存、生成文件和签名材料不作为 app 源码复制。

工作区有改动时会标记 `workingTreeDirty: true`，不能仅用父提交 SHA 代替源码指纹。`--build-mode release` 是 Hvigor 构建模式，默认仍执行 development 内容审计；不等于正式签名、最终 SBOM 或发布批准。`--device` 安装并运行后记录 CLI smoke 结果，不卸载既有应用。现有 C01/C02 的手工构建记录仍保留，不覆盖。

## 2. B 的运行时交付规范

复制 [清单模板](../packaging/runtime-manifest.example.json) 到 Git 外的工作目录。模板的 `awaiting-payload` 会主动拒绝装配，不能将空清单当作成功。

1. 提供已展开的 OHOS aarch64 文件目录，不在工具中联网 pip 安装或自动下载。原生库应先完成约定的 strip/重签，再记录最终字节哈希；任何后续修改必须更新清单。
2. 锁定 CPython 3.12.9、NumPy 2.2.6、SciPy 1.16.3、PyCifRW 5.0.1、GSAS-II 2.0.0 及现有上游提交；其他实际 BLAS/Fortran/Bridge/N-API 组件也逐项登记。
3. 每个组件填写实际构建/载荷来源 `sourceUrl`、对应源码 `sourceCodeUrl`（HTTPS 引用）、许可证标识、许可原文文件、直接依赖 ID 和分发审查状态。工具核对字段和文件，不联网证实引用或替代人工审查。构建配方、链接依赖分析和 OHOS 来源仍须由 B 随交接提交。
4. 每个文件登记 `source`（相对载荷目录）、`target`（相对 HAP 根目录）、`sha256`、`size`、`component`。哈希为小写 64 位 SHA-256，大小为正整数；目录中的所有文件必须登记，不接收路径越界、符号链接或大小写碰撞。
5. 将 `status` 改为 `ready` 仅表示文件清单已齐备。`distributionReview: pending` 可用于内部开发装配；改成 approved 必须附真实 `reviewReference`，正式审计要求全部批准。不得用测试引用代替审批。

允许的 target：

| target 范围 | 英文构建工程内的位置 | 用途 |
|---|---|---|
| `libs/arm64-v8a/<name>.so` | `entry/libs/arm64-v8a/<name>.so` | 顶层原生库；禁止覆盖既有 app/SDK 库 |
| `resources/rawfile/runtime/<relative>` | `entry/src/main/resources/rawfile/runtime/<relative>` | 展开的标准库、site-packages、GSAS-II、生产 Bridge 等 |
| `resources/rawfile/licenses/runtime/<id>/<name>` | `entry/src/main/resources/rawfile/licenses/runtime/<id>/<name>` | 对应组件的许可原文 |

至少需要顶层 `libpython3.12.so` 和 `runtime/lib/python3.12/encodings/__init__.py`，且每个锁定组件必须有实际载荷与归属自己的许可证。清单文件项示意：

```json
{
  "source": "python/lib/libpython3.12.so",
  "target": "libs/arm64-v8a/libpython3.12.so",
  "sha256": "填写实际文件的64位小写SHA256",
  "size": 123,
  "component": "cpython"
}
```

示意项不能直接构建。`.so` 核对 ELF64、小端、AArch64、ET_DYN；这不能区分 Linux/Android/OHOS ABI，也不证明依赖已齐全或签名有效。B/C 仍需真机验证所有扩展及 DT_NEEDED 依赖。payload 不接收 wheel/zip/tar、预编译 pyc、外平台二进制或开发 fake core。`pydiffax` 和 `G2shapes.py` 在当前方案中明确排除，授权范围改变时需单独审核工具策略。

## 3. 宿主装配、升级和构建

先生成一个新版本目录（路径为接收方本地实际路径）：

```sh
python3 scripts/Prepare-Runtime.py --manifest /work/runtime-manifest.json --payload /work/runtime-payload --output /work/prepared-v1
```

先验证完整清单和所有源文件，再复制并复核目标字节；成功后才写 `runtime-receipt.json`。失败删除本次新建目录；已存在的输出目录一律拒绝，不覆盖旧版本。升级应使用新的 runtimeId/输出目录，并保留旧版本便于对比。这个机制只管理宿主装配版本；设备 runtimeRoot 的解包、激活与升级迁移由 B 的 `RuntimeInstaller.ets` 实现（影子解包 `runtime-next`、逐项哈希复核、`.activation` 标记、目录交换发布与崩溃恢复；回滚即再次激活旧 runtimeId），设备侧 `runtime/manifest.json` 由 `scripts/Write-RuntimeManifest.py` 与发布清单同批生成，详见 [PHASE3_NAPI_CORE](PHASE3_NAPI_CORE.md)。

收到真实载荷后可在全新构建副本中装配并校验包内实际字节：

```sh
python3 scripts/Build-App.py --check --build-mode release --runtime-manifest /work/runtime-manifest.json --runtime-payload /work/runtime-payload
```

清单中的 native target 是否实际进入 HAP，最终按 ZIP 中的路径、大小、哈希核对；SDK 打包遗漏或修改会导致构建留档失败。准备目录和源码工作区分离，运行时二进制不提交 Git。此选项只准备包内容；ArkTS 解包逻辑（`RuntimeInstaller.ets`）、链接配置与计算桥接由 B 在 `core/napi-runtime` 分支另行交付，装配了真实载荷的应用才可能启动 Python，本工具的通过本身不构成该证明。

## 4. HAP 内容审计

对现有开发包可单独执行，报告路径不能已存在：

```sh
python3 scripts/Audit-Hap.py /work/entry.hap --output /work/entry-inventory.json
```

对包含完整运行时且许可审查已通过的包：

```sh
python3 scripts/Audit-Hap.py /work/entry.hap --manifest /work/runtime-manifest.json --mode release --output /work/entry-release-inventory.json
```

门禁覆盖实际 ZIP 文件清单、重复路径/大小写碰撞/越界/链接、已知禁分发和开发载荷、嵌套归档、原生架构、原生库归属、运行时文件及许可证哈希，并验证 app 自带五份许可/NOTICE 与仓库原文一致。release 模式另要求运行时齐备、分发审查已批准、包内为非 debug 的 release 构建。单个成员最大 256 MiB，总展开量最大 4 GiB；超限明确失败，不能跳过未扫描部分。

输出是 `hap-content-inventory`，用于最终 SBOM 的逐文件基础；目前不是完整 SPDX/CycloneDX SBOM。未知编译代码只能检查有限的开发标记，不能证明所有 fake 行为、静态依赖或全部许可证义务已排除。所有报告固定 `releaseCandidateApproved: false`，正式放行还需 [发布验收清单](RELEASE_ACCEPTANCE.md)。签名有效性、目标系统兼容、应用沙箱 Python 加载和五阶段数值正确性均需独立验收。

## 5. 自动化复核

```sh
python3 -m unittest discover -s tests -p 'test_release_tools.py' -v
```

CI 使用合成的最小 ELF 头和测试包验证腐败、越界、版本保护、漏交、篡改、原生架构和未批准组件等门禁，不把测试夹具视为真实运行时。真实构建应另行执行第 1 节命令；真实运行时装配及设备验证依赖 B 交付。

## 6. 实际验证记录

当前已执行宿主自动化测试，并对 C01/C02 开发 HAP 完成实际内容清单核对。最终构建/安装复核结果及产物哈希在本增量完成后记录于 [发布工具验证记录](RELEASE_TOOLING_VALIDATION.md)。Windows/Linux 的 SDK 构建、真实 B 载荷装配、设备激活及精修均保持待验证。
