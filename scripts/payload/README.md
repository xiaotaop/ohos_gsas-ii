# 运行时载荷装配（成员 B）

本目录是 [RUNTIME_PACKAGING](../docs/RUNTIME_PACKAGING.md) §2 所要求的
"已展开 OHOS aarch64 目录" 的可复现装配配方。脚本只做复制、解包与裁剪，
从不在载荷上运行解释器或构建工具；所有二进制均来自下表所列、可按 SHA-256
复核的下载。

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

结果：2214 个文件、约 178 MB；哈希复算、逐文件内容门禁（ELF AArch64、
无归档/字节码/外平台库）全部通过；状态如实为
`prepared-not-device-validated`。

SBOM 草案：`python3 scripts/payload/make_sbom.py` 从 `components.json` 生成
[`packaging/sbom.draft.cdx.json`](../../packaging/sbom.draft.cdx.json)
（CycloneDX 1.5，9 个组件，无文件哈希；`distributionReview` 保持 `pending`，
最终 SBOM 须由成员 C 从签名 HAP 重新生成）。

静态闭包：`GSASIIscriptable` 可达的模块级导入 21 项，缺失 0；函数内缺失 12 项，
全部指向尚未构建的原生扩展（`pyspg`、`pypowder`、`pytexture`、`fmask`、
`histogram2d`）。**`pyspg` 不是可选加速器**：GSAS-II 2.0.0 的
`GSASIIobj.SetNewPhase` 以 `GSASIIspc.SpcGroup('P 1')` 初始化 `P1SGData`，
而 `SpcGroup` 直接调用 `pyspg.sgforpy`；缺少 `pyspg` 时该调用抛
`NameError: name 'P1SGData' is not defined`，任何相文件（含 PbSO4 CIF）都无法
导入，五阶段精修在设备上必然失败。本载荷未包含任何 GSAS-II `.so`，因此
`check_gsas_native.py` 会把发布载荷判为不合格；修复方式见 §5。

## 5. 未闭环项

- **设备侧加载**：`libpython3.12.so` 的 dlopen 链、rawfile 解包、沙箱权限
  未在真机验证。
- **原生扩展（发布阻断项）**：8 个编译模块（`pyspg`、`pypowder`、`pytexture`、
  `fmask`、`histogram2d`、`pack_f`、`unpack_cbf`、`kvec_general`）均未随载荷
  构建；`pyspg` 缺失时连相文件都无法导入（见 §4），五阶段数值验收因此不可达。
  修复路径：按 `scripts/ohos/` 的第二阶段配置在设备上用 flang 20.1.0 重新构建
  并签名，或复用第二阶段已签名的同一批模块（需先补来源/许可/SBOM 审查）。
  门禁脚本：`check_gsas_native.py`；发布时必须通过且不带 `--allow-missing`。
- **Sobol QMC**：见 §3 的 `.npz` 说明，属发布门禁导致的明确功能裁剪。