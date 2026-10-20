# 运行时载荷装配（成员 B）

本目录是 [RUNTIME_PACKAGING](../../docs/RUNTIME_PACKAGING.md) §2 所要求的
"已展开 OHOS aarch64 目录" 的基础装配配方。脚本只做复制、解包与裁剪，
从不在载荷上运行解释器或构建工具；初次 2214 文件装配的二进制来自下表所列、
可按 SHA-256 复核的下载。本文保留 B 的基础载荷配方及历史增量；最终候选 HAP 的
8 个 GSAS-II 扩展由 C 按[锁定源码与 Flang 20.1.8 配方](../ohos/local-cross/README.md)
重建并在 HAD-W32/API23 应用内验证，见[签名 HAP 记录](../../docs/C_SIGNED_HAP_DELIVERY.md)。
基础下载来源与 8 模块构建来源**均已交付**；仍待 C 审核预编译运行时中其他第三方
动态/静态依赖的对应源码、版本和许可，必要时由 B 协助追溯发行者物料。

## 1. 组件版本与来源

| 组件 | 版本 | 下载 | SHA-256 |
|---|---|---|---|
| CPython | 3.12.9 (ohos-aarch64) | `https://artifacts-cn-beijing.volces.com/repository/ophcd.pkg/pkg/kernel-1.13.0/python/3.12.9/python-3.12.9-ohos-aarch64.tar.gz` | `767b7ef43155551aeeb147b15a828d8b996a3ef70fec7edd4eee01800b163576` |
| CPython 源码（仅取 LICENSE） | 3.12.9 | `https://www.python.org/ftp/python/3.12.9/Python-3.12.9.tgz` | `45313e4c5f0e8acdec9580161d565cf5fea578e3eabf25df7cc6355bf4afa1ee` |
| NumPy | 2.2.6 (ohos_aarch64 wheel) | 社区 cnb 轮子仓库（见 `components.json` `sourceUrl`） | `8468135b1d7aabdc0778c7ca4e50f5db1b2148aed97144bf354b80f2a091fcb0` |
| SciPy | 1.16.3 (ohos_aarch64 wheel) | 同上 | `a7e2095d76bfb55460b4f66ba5a7eb7861ca644c5c6326252b7cdb02a6d61dcd` |
| PyCifRW | 5.0.1 (sdist) | `https://files.pythonhosted.org/packages/source/P/PyCifRW/pycifrw-5.0.1.tar.gz` | `e636b80be6a2be15b215e69ecec0c0a784ebcbfed8b1e3bac4bcc6e6ba9a75e0` |
| prettytable | 3.18.0 | PyPI `prettytable-3.18.0-py3-none-any.whl` | `b3346e0e6f79180833aebaac088ae926340586cf6d7d991b9eb125b65f72313a` |
| wcwidth | 0.9.2 | PyPI `wcwidth-0.9.2-py3-none-any.whl` | `89ca642c5bf0101157a09366be69fad0379db1f700ae39a920e103234573670e` |
| ply | 3.11 | PyPI `ply-3.11-py2.py3-none-any.whl` | `096f9b8350b65ebd2fd1346b12452efe5b9607f7482813ffca50c22722a807ce` |
| GSAS-II | 2.0.0 @ `2b4aba1bc44de63a3da9d4495944c3b99e389399` | 上游仓库 checkout | — |
| bridge | 1.1.0 | 本仓库 `bridge/` | — |

`components.json` 是 `Write-RuntimeManifest.py --components` 的输入，含每个
组件的许可证、源码地址、依赖与载荷前缀。当前 `distributionReview` 全部为
`pending`，因此发布审计（`Audit-Hap.py --mode release`）仍会被阻止，这是
如实状态，不是遗漏。

## 2. 目录约定

脚本通过 `GSAS_PAYLOAD_BASE`（默认 `/home/dax/gsas-payload`）定位工作目录：

```
$GSAS_PAYLOAD_BASE/
  downloads/                       # 上表文件，按原文件名放置
  extract/python-3.12.9-ohos-aarch64/   # 已解包的 CPython 载荷
  extract/pycifrw-full/pycifrw-5.0.1/   # 已解包的 PyCifRW sdist
  extract/ply-3.11/                # 已解包的 ply sdist（仅用于提取许可证）
  payload/                         # 输出，每次运行重建
```

GSAS-II 源码由 `GSAS_II_SRC` 指定（默认
`/mnt/d/vscode_projects/GSAS-II`），本仓库路径由 `GSAS_REPO` 指定。

## 3. 装配步骤

```sh
python3 scripts/payload/assemble_payload.py        # CPython + 轮子 + PyCifRW + GSAS-II + bridge + 许可证
python3 scripts/payload/expand_pydeps.py           # 展开 prettytable / ply / wcwidth
python3 scripts/payload/prune_release_payload.py   # 发布裁剪（见下）
python3 scripts/payload/finalize_payload.py        # 零字节文件规范化 + 归档残留断言
python3 scripts/payload/check_scriptable_closure.py # GSASIIscriptable 导入闭包
python3 scripts/payload/check_gsas_native.py --payload "$GSAS_PAYLOAD_BASE/payload" --allow-missing
                                                    # 原生扩展完整性（发布时必须去掉 --allow-missing）
```

`assemble_payload.py` 的关键裁剪：

- stdlib 去掉 `test`、`idle_test`、`ensurepip`、`config-3.12-*`（后两者带
  `.whl`/`.a`）与解释器自带 `pip`；
- GSAS-II 去掉 `DIFFaXsubs/`、`help/`（含 `.gz` sitemap）、`install/`
  （含 `g2app.tar.gz`）与 `G2shapes.py`（许可证门禁）；
- 站点包内删静态库 `.a`、压缩测试数据与 numpy/scipy 的 `tests/`；
- SciPy 的 `_sobol_direction_numbers.npz` 是 ZIP 容器，被 §2 拒绝；`_sobol.pyx`
  仅在构造 Sobol QMC 引擎时惰性读取它，因此该文件不随包发送。**Sobol QMC
  在此载荷中不可用**，`scipy.stats` 其余功能与 GSAS-II 所用路径不受影响。

`prune_release_payload.py` 的两项内容保持型修改：

1. `GSASIIpwd.py` 的 `import pydiffax` 块替换为等价的 `raise ImportError`，
   模块原有 "不可用" 回退不变；
2. 删除模块级 `import wx`（或 `import G2shapes`）的 25 个 GUI 模块，并把
   剩余的 GUI 专用函数内导入替换为 `raise ImportError`；随后用 AST 复扫，
   任何残留的 pydiffax/G2shapes/fake_core 导入都会使脚本失败。

## 4. 门禁与已验证结果

宿主需要 Python **3.12**：门禁会对载荷内每个 `.py` 做 AST 解析，而宿主
Python 3.10 的解析器无法读取 3.12 的 PEP 701 f-string。已验证的一次完整
装配（2026-10-19，宿主 x86_64）：

```sh
python3 scripts/Write-RuntimeManifest.py --payload "$GSAS_PAYLOAD_BASE/payload" \
  --components scripts/payload/components.json \
  --runtime-id b-ohos-aarch64-3.12.9-p1 --output "$GSAS_PAYLOAD_BASE/runtime-manifest.json"
# {"runtimeId":"b-ohos-aarch64-3.12.9-p1","files":2214,"components":[cpython,numpy,scipy,
#  pycifrw,prettytable,wcwidth,ply,gsas-ii,bridge],"deviceManifest":"runtime/manifest.json",...}

python3 scripts/Prepare-Runtime.py --manifest "$GSAS_PAYLOAD_BASE/runtime-manifest.json" \
  --payload "$GSAS_PAYLOAD_BASE/payload" --output "$GSAS_PAYLOAD_BASE/prepared/p1"
# {"runtimeId":"b-ohos-aarch64-3.12.9-p1","status":"prepared-not-device-validated"}
```

初次装配结果：2214 个文件、约 178 MB；哈希复算、逐文件内容门禁（ELF AArch64、
无归档/字节码/外平台库）全部通过；该版本仍缺原生扩展，状态为
`prepared-not-device-validated`。2026-10-19 从 HAD-W32 已有环境导出 8 个扩展后，本地重新组装为 2230 文件；`check_gsas_native.py` 不带 `--allow-missing` 通过。详见[补充验证记录](../../docs/B_DEVICE_VALIDATION_2026-10-19.md)。这不代表最终可重建分发载荷或应用内验证完成。

SBOM 草案：`python3 scripts/payload/make_sbom.py` 从 `components.json` 生成
[`packaging/sbom.draft.cdx.json`](../../packaging/sbom.draft.cdx.json)
（CycloneDX 1.5，9 个组件，无文件哈希；`distributionReview` 保持 `pending`，
最终 SBOM 须由成员 C 从签名 HAP 重新生成）。

初次装配的静态闭包：`GSASIIscriptable` 可达的模块级导入 21 项，缺失 0；函数内缺失 12 项，
当时指向尚未装入的原生扩展（`pyspg`、`pypowder`、`pytexture`、`fmask`、
`histogram2d`）。**`pyspg` 不是可选加速器**：GSAS-II 2.0.0 的
`GSASIIobj.SetNewPhase` 以 `GSASIIspc.SpcGroup('P 1')` 初始化 `P1SGData`，
而 `SpcGroup` 直接调用 `pyspg.sgforpy`；缺少 `pyspg` 时该调用抛
`NameError: name 'P1SGData' is not defined`，任何相文件（含 PbSO4 CIF）都无法
导入，五阶段精修会失败。初次装配未包含任何 GSAS-II `.so`，因此
`check_gsas_native.py` 判其不合格；后续 2230 文件本地组装物已通过此门禁，但 HAP 内执行仍待验。

## 5. 未闭环项（初次 B 载荷快照；当前状态见上方链接）

- **应用沙箱加载**：HiShell 中已导入 8 个扩展并完成五阶段，但
  `libgsas_core.so` → `libpython3.12.so` 的加载链、`Py_Initialize`、rawfile
  解包和沙箱权限当时仍未在已安装 HAP 内验证；C 的指定设备签名包现已完成成功路径。
- **最终原生载荷与分发审计**：8 个编译模块（`pyspg`、`pypowder`、
  `pytexture`、`fmask`、`histogram2d`、`pack_f`、`unpack_cbf`、`kvec_general`）
  已用于本地组装物，门禁通过；仍需将其来源、构建/复用方式、最终字节清单和
  许可证审查与 C 的正式签名 HAP 对齐。来源、构建步骤与许可义务见
  [EXTENSIONS_BUILD](../../docs/EXTENSIONS_BUILD.md)；最终发布时
  `check_gsas_native.py` 必须不带 `--allow-missing` 通过，且不能只复用本地测试报告。
- **Sobol QMC**：见 §3 的 `.npz` 说明，属发布门禁导致的明确功能裁剪。

## 6. 原生扩展与清单冻结顺序

1. 把 8 个 `*.cpython-312-aarch64-linux-ohos.so` 放入
   `runtime/lib/python3.12/site-packages/GSASII/`；`pydiffax` 不得出现。
2. **先 strip、再生成清单**：对顶层 `libs/libpython3.12.so`（以及约定的
   重签）执行 `llvm-strip` 之后，才运行 `Write-RuntimeManifest.py`。
   2026-10-19 在设备侧验证过：用 strip 前字节生成的清单，会让 Hvigor 打包后的
   `Audit-Hap.py` 报 `packaged runtime mismatch`。
3. 生成并核对：

   ```sh
   python3 scripts/Write-RuntimeManifest.py --payload <payload> \
     --components scripts/payload/components.json --runtime-id <id> --output <manifest.json>
   python3 scripts/Prepare-Runtime.py --manifest <manifest.json> \
     --payload <payload> --output <prepared-dir>
   python3 scripts/payload/check_gsas_native.py --payload <payload>   # 不得带 --allow-missing
   ```

4. 本地补充组装为 2230 文件（初次装配 2214 + 16），冻结时逐项核对差异来源；
   清单哈希与 runtimeId 交 C 记录，不同 HAP 的证据不得混用。
5. 扩展静态链接 LLVM **FortranRuntime**（Apache-2.0 WITH LLVM-exception）；
   SBOM 草案已标注该义务，最终许可清单由 C 汇总。
