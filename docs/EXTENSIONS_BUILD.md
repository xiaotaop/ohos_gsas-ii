# GSAS-II 原生扩展：来源、构建与冻结（成员 B）

状态更新（2026-10-20）：B 在 HAD-W32 的 Flang 20.1.0/HiShell 配方保留为独立历史证据；**不再把 B 当时的设备导出模块当成最终 HAP 的构建来源**。C 已以锁定上游源码、Flang 20.1.8 和[可复建补丁](../scripts/ohos/local-cross/README.md)生成 8 模块，并为指定设备签名 HAP 提供哈希凭据与 GSAS 源码伴随包；该 HAP 的五阶段已通过。第三方预编译运行时的最终 SBOM/许可与公开分发审计仍由 C 关闭，见[C 交付](C_SIGNED_HAP_DELIVERY.md)。

C 的宿主交叉编译增量使用 Flang 20.1.8，并已在 API26 模拟器的正式应用进程内完成五阶段精修。
可复建补丁与容器路径见 [local-cross 配方](../scripts/ohos/local-cross/README.md)，同一 HAP 的数值、导出与恢复记录见 [C 验收记录](C_NATIVE_ACCEPTANCE.md)。下列 B 设备配方继续保留 20.1.0 的独立记录，两个构建的归档与清单应分别核验。

## 1. 组件与上游

| 项 | 值 |
|---|---|
| 上游 | GSAS-II 2.0.0，提交 `2b4aba1bc44de63a3da9d4495944c3b99e389399` |
| 构建模块（8 个） | `pyspg`、`pypowder`、`pytexture`、`fmask`、`histogram2d`、`pack_f`、`unpack_cbf`、`kvec_general` |
| 排除 | `pydiffax`（DIFFaX 下游分发依据未确认）；`G2shapes.py` 不编译 |
| 源位置 | 设备上的固定提交源码树；对应文件 `GSAS-II/sources/*.for`、`*module.c`、`k_vec_cython/kvec_general.pyx` |

扩展来自设备上既有的、与该提交对齐的环境（当时导出的原始 `gsas-native-device.tar` SHA-256
`f03d81c6bc1935cfe3c802e4f6aff2b7b658b875e47963b0a6cfe79d7f3de2c8`）。**仓库不包含这些
二进制**；下文步骤仅供在设备上诊断性重建和复核，尚不是排除 DIFFaX 的最终发布配方。

## 2. 构建环境（设备侧）

| 组件 | 版本 | 备注 |
|---|---|---|
| 设备 | HAD-W32 / HarmonyOS 6.1.0.115 / aarch64 | 目标验收机仍为 HAD-W24 / 6.1.0.117 |
| SDK | Harmonybrew SDK 26.0.0.18（Clang 15.0.4） | 设备用户终端安装 |
| Fortran | flang 20.1.0（OpenHarmonyPCDeveloper 社区包） | 需 `LD_LIBRARY_PATH` 含其 `lib/` 与 SDK `llvm/lib` |
| Python | CPython 3.12.9，NumPy 2.2.6 | 与载荷锁定版本一致 |
| 构建 | Meson 1.12.1、Ninja 1.13.2 | |

## 3. 配方文件

- [`scripts/ohos/gsas-ohos-cross.ini`](../scripts/ohos/gsas-ohos-cross.ini)：Meson cross file；
  `c_link_args` 必须静态链接 `FortranRuntime`/`FortranDecimal`，否则导入时会缺 `_FortranA*`。
- [`scripts/ohos/flang-ohos-wrapper.sh`](../scripts/ohos/flang-ohos-wrapper.sh)：补齐 sysroot、
  启动对象与运行库，绕过 Meson 的 Fortran 健康检查。
- [`scripts/ohos/sign-native-modules.sh`](../scripts/ohos/sign-native-modules.sh)：`llvm-strip`
  → 移除旧 `.codesign` → `binary-sign-tool sign -selfSign 1`。

cross file 中的绝对路径属于该设备环境；换设备、用户或 SDK 版本时必须重新生成。

## 4. 构建与导出步骤（设备上执行）

```bash
# 1) 固定源码提交并进入源码树
cd <GSAS-II checkout> && git checkout 2b4aba1bc44de63a3da9d4495944c3b99e389399

# 2) 用 cross file 配置诊断构建。固定提交的 sources/meson.build 没有关闭
#    pydiffax 的选项，以下命令也会编译它；不得分发完整构建目录。
meson setup build-ohos --cross-file <设备上的 gsas-ohos-cross.ini> --buildtype=release
ninja -C build-ohos

# 3) 签名（设备会拒绝未签名 ELF）。脚本属于本移植仓库，不在 GSAS-II 上游树中。
<ohos_gsas-ii checkout>/scripts/ohos/sign-native-modules.sh build-ohos

# 4) 仅导出 8 个允许的模块；不要导出 pydiffax 或完整构建目录。
tar -czf gsas-extensions-had-w32.tar.gz \
  build-ohos/GSASII/{pyspg,pypowder,pytexture,fmask,histogram2d,pack_f,unpack_cbf,kvec_general}*.so
sha256sum gsas-extensions-had-w32.tar.gz
```

此处新生成的 `.tar.gz` 与既有 `gsas-native-device.tar` 不是同一归档，哈希不应相等。
归档前须逐项核对模块名，确认没有 `pydiffax`；正式发布构建还须由 B 提供并验证
**在 Meson 源配置中排除 `DIFFaXsubs_lib` 和 `pydiffax` 目标**的固定补丁或等效构建步骤。
当前诊断命令不能代替该交付。

## 5. 入载荷与门禁

将 8 个 `.cpython-312-aarch64-linux-ohos.so` 放入载荷的
`runtime/lib/python3.12/site-packages/GSASII/`，然后运行：

```sh
python3 scripts/payload/check_gsas_native.py --payload <payload>
# 期望：8 项 PASS，releaseReady=true，退出码 0
```

HAD-W32 本地组装的 2230 文件载荷在不带 `--allow-missing` 时通过该门禁。该文件数比仓库
基线（2214）多 16，冻结时须逐项核对差异来源（8 个扩展及其余本地增补），不能直接当作
仓库可复现产物。

## 6. 校验清单

- 每个模块为 ELF64、AArch64、`ET_DYN`，导出 `PyInit_<name>`；
- 无 `pydiffax`；不含调试段（由 `llvm-strip --strip-debug` 保证）；
- 设备 HiShell 中逐个 `import GSASII.<name>` 成功，`GSASII.GSASIIscriptable` 可导入；
- `check_gsas_native.py` 通过；
- 对既有 `gsas-native-device.tar`，归档哈希与
  [B 侧真机补充验证](B_DEVICE_VALIDATION_2026-10-19.md) 记录一致；重建归档应单独记录哈希，
  不应预期与既有归档相同。

当前只记录了**归档**哈希，没有逐模块 SHA-256；如组长留存了逐模块值，应在冻结清单中补录。

## 7. 许可与分发

- 8 个模块本身属于 GSAS-II（GSAS-II Open Source License），许可原文随载荷
  `licenses/gsas-ii/` 提供。
- 模块静态链接 LLVM **FortranRuntime 20.1.0**（Flang 运行时），其许可为
  **Apache-2.0 WITH LLVM-exception**，源码 <https://github.com/llvm/llvm-project>。
  最终 SBOM 与许可清单必须包含该组件及许可原文（由 C 汇总）；
  [`packaging/sbom.draft.cdx.json`](../packaging/sbom.draft.cdx.json) 已在 metadata 中标注。
- `pydiffax` 不进入任何发布产物。

## 8. 边界与后续

- 本配方只在 HAD-W32 的 HiShell 用户环境验证；应用沙箱内的加载与运行需 C 提供可安装的
  签名 HAP 后由 B 执行。
- 设备工具链不可在仓库内复现（flang 20.1.0 为设备原生包）；本文仅列出同版本设备上的
  诊断性重建步骤，尚未证明最终发布载荷可重建。排除 `pydiffax` 的发布构建配方尚待 B 固化。
- 最终 strip/重签、清单冻结、`distributionReview` 与发布审计归 C；B 提供来源、构建记录与
  清单输入。
