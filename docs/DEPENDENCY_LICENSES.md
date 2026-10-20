# 运行时依赖与许可清单（成员 B）

更新日期：2026-10-20。适用对象：B 的基础运行时载荷（2214 文件，
`runtimeId = b-ohos-aarch64-3.12.9-p1`），不含 8 个 GSAS-II 计算扩展
（其来源与 LLVM 静态许可见 [EXTENSIONS_BUILD](EXTENSIONS_BUILD.md) 和
[C 的签名 HAP 记录](C_SIGNED_HAP_DELIVERY.md)）。

本清单回答三个问题：预编译 Python/NumPy/SciPy 实际附带哪些第三方库、
它们的版本与链接方式、以及许可证；对应源码与构建依据；两个旧帮助库是否
值得作为移除候选。机器可读版本见
[`packaging/third-party.dependencies.json`](../packaging/third-party.dependencies.json)，
许可证原文与索引见
[`packaging/licenses/third-party/`](../packaging/licenses/third-party/NOTICE.md)。

> 哈希均按上述基础载荷的真实字节计算。**最终签名 HAP 必须由 C 用实际包内
> 字节重新审计**；不同 HAP 的结论不得混用。

## 1. 预编译包与构建依据

| 组件 | 版本 | 下载（SHA-256） | 对应源码 | 构建依据 / 补丁 |
|---|---|---|---|---|
| CPython | 3.12.9 ohos-aarch64 | [volces tarball](https://artifacts-cn-beijing.volces.com/repository/ophcd.pkg/pkg/kernel-1.13.0/python/3.12.9/python-3.12.9-ohos-aarch64.tar.gz) `767b7ef4…163576` | [Python-3.12.9.tgz](https://www.python.org/ftp/python/3.12.9/Python-3.12.9.tgz) `45313e4c…4afa1ee` | 载荷内 `_sysconfigdata__ohos_aarch64-linux-ohos.py` 记录了完整配置：`--enable-shared --build/--host=aarch64-unknown-linux-ohos --with-openssl=<deps>`，`CC=clang`、`CFLAGS=-fPIC -O2 -fuse-ld=bfd`，依赖 openssl、sqlite3、readline、ncurses、gdbm、gettext 0.26、xz 5.8.2、libffi 3.4.4、bzip2 1.0.8。补丁：**未随包记录**，需向社区构建方索取 |
| NumPy | 2.2.6 ohos_aarch64 wheel | [cnb wheel](https://pypi.cnb.cool/OpenHarmonyPCDeveloper/pypi/-/packages/46/d1/ec3f782abdf0d8a87398feb6f732731945db028a9e59023f3c2f021bd910/numpy-2.2.6-cp312-cp312-ohos_aarch64.whl) `8468135b…091fcb0` | [numpy v2.2.6](https://github.com/numpy/numpy/releases/tag/v2.2.6) | wheel 内 NumPy 扩展只 NEED `libpython3.12` 与 `libc`，BLAS 内核内置（`lapack_lite`/`noblas`）；`numpy.libs` 里的 OpenBLAS64 无消费者（见 §3）。构建配置与补丁未随 wheel 发布 |
| SciPy | 1.16.3 ohos_aarch64 wheel | [cnb wheel](https://pypi.cnb.cool/OpenHarmonyPCDeveloper/pypi/-/packages/b5/eb/cb74cfabd35deed6c787d654513660eaefb062f275977043868d5cdb960b/scipy-1.16.3-cp312-cp312-ohos_aarch64.whl) `a7e2095d…a6d61dcd` | [scipy v1.16.3](https://github.com/scipy/scipy/tree/v1.16.3) | 23 个扩展 NEED `libscipy_openblas-80d8b5fa.so`（OpenBLAS 0.3.29，静态内含 Fortran 运行时）；构建配置与补丁未随 wheel 发布 |
| PyCifRW / prettytable / wcwidth / ply | 5.0.1 / 3.18.0 / 0.9.2 / 3.11 | 见 [载荷配方](../scripts/payload/README.md) §1 | PyPI / 上游 | 纯 Python，无原生依赖 |

“补丁未随包记录”是当前如实状态：社区 wheel 的构建配方未公开在包内，
不能声称与上游 sdist 完全相同。C 的最终许可审查应据此要求发行方补交
构建配方或自行从源码重建。

## 2. 内嵌第三方库（按实际载荷）

链接方式由 `readelf -d`（DT_NEEDED）与 `strings`/`sysconfig` 证据确定；
“静态”表示代码已并入对应 CPython 模块或 SciPy/NumPy 扩展，载荷中没有
独立文件。

| 库 | 版本 | 链接方式 | 证据 | 消费者 | 许可证 |
|---|---|---|---|---|---|
| libffi | 3.4.4 | 动态，`libffi.so.8` | DT_NEEDED | `_ctypes` | MIT |
| GDBM | 1.24 | 动态，`libgdbm.so.6` | DT_NEEDED；strings `1.24` | `_gdbm` | GPL-3.0-or-later |
| OpenSSL | 1.1.1w | 静态 | strings `OpenSSL 1.1.1w 11 Sep 2023` | `_ssl`、`_hashlib` | OpenSSL/SSLeay 双许可 |
| SQLite | 3.49.1 | 静态 | strings `3.49.1` | `_sqlite3` | Public Domain |
| bzip2 | 1.0.8 | 静态 | `MODULE__BZ2_LDFLAGS=-lbz2`；strings `1.0.8` | `_bz2` | bzip2-1.0.6 |
| XZ / liblzma | 5.8.2 | 静态 | `sysconfig` 的 `xz_v5.8.2`；strings `5.8.2` | `_lzma` | 0BSD |
| ncurses | 6.6.20251230 | 静态 | strings `6.6.20251230`；`-lncursesw` | `_curses`、`_curses_panel` | X11 风格 |
| Expat | 2.6.4 | 静态 | `MODULE_PYEXPAT_DEPS=Modules/expat/libexpat.a`；strings `expat_2.6.4` | `pyexpat` | MIT |
| libmpdec | 2.5.1 | 静态 | strings `__libmpdec_version__`、`2.5.1` | `_decimal` | BSD-2-Clause |
| OpenBLAS（SciPy） | 0.3.29（NO_AFFINITY ARMV8） | 动态，`scipy.libs/libscipy_openblas-80d8b5fa.so`，10,803,648 B，`094de356…c89bf60` | DT_NEEDED ×23 | SciPy 科学扩展 | BSD-3-Clause |
| **OpenBLAS64（NumPy 遗留）** | 0.3.23.dev（USE64BITINT DYNAMIC_ARCH） | 动态，`numpy.libs/libscipy_openblas64_.so`，23,271,424 B，`06883ce6…fceed` | **无任何 DT_NEEDED 引用** | 无 | BSD-3-Clause |
| **GNU Fortran 运行库** | 9.3.0（Alpine aports 构建） | 动态，`numpy.libs/libgfortran.so.5`，1,287,808 B，`2d227ceb…a7f5d` | 仅 `libscipy_openblas64_.so` NEEDED；其自身 NEED `libgcc_s.so.1`、`libc.musl-aarch64.so.1` | 无（随上述库） | GPL-3.0-or-later WITH GCC-exception-3.1 |

补充：

- `libz.so` 由 OHOS 系统提供（SDK sysroot 的 `libz.so`），被 `binascii`、
  `zlib` 动态链接，未随应用分发，许可证为 Zlib。
- `libc++_shared.so` 由应用打包（`libs/arm64-v8a/`），许可证
  Apache-2.0 WITH LLVM-exception，归 C 的 HAP 许可清单。
- gettext/libintl 只出现在 CPython 构建的 `LIBS=-lintl` 中；载荷内没有任何
   ELF NEED `libintl`，未随应用分发。
- **OpenSSL 1.1.1w 已停止维护**（1.1.1 系列 2023-09 结束支持）。当前
  `_ssl`/`_hashlib` 静态包含它；是否影响分发由 C 与组长在安全/兼容性复核后
  决定，并应在发布说明中如实披露。

## 3. 旧帮助库处理结论

**静态分析结论：`libscipy_openblas64_.so` 与 `libgfortran.so.5` 是移除候选，
尚未在删除后的签名 HAP 上验证，不得视为安全移除授权；SciPy 正在使用的
`libscipy_openblas-80d8b5fa.so` 必须保留。**

依据（对基础载荷全部 ELF 的 `DT_NEEDED` 扫描）：

1. 没有任何 ELF 的 `DT_NEEDED` 指向 `libscipy_openblas64_.so`；NumPy 的
   `_multiarray_umath`、`_umath_linalg`、`lapack_lite` 等只 NEED
   `libpython3.12.so` 与 `libc.so`，BLAS/LAPACK 以内置 `lapack_lite`/
   `noblas` 内核形式编译。
2. `libgfortran.so.5` 只被 `libscipy_openblas64_.so` 引用；
   `libgcc_s.so.1` 与 `libc.musl-aarch64.so.1` 也只出现在该库的 NEEDED 中。
   若移除这组文件，预计 C 的 SBOM 工具里两个 `unmatched` 依赖随之消失；
   仍须用新 HAP 的实际依赖扫描核实。
3. NumPy 源码中除 `numpy-2.2.6.dist-info/RECORD` 外，没有任何 Python 文件
   引用这两个库名；`_distributor_init.py` 只尝试导入可选的
   `_distributor_init_local`，没有 ctypes/dlopen 逻辑。
4. SciPy 的 OpenBLAS 被 23 个扩展模块 NEED，是实际计算路径，**不能删除**。

候选实验步骤（由 B 或 C **仅在新载荷副本**上执行，不改变已验收 HAP）：

```sh
rm runtime/lib/python3.12/site-packages/numpy.libs/libscipy_openblas64_.so
rm runtime/lib/python3.12/site-packages/numpy.libs/libgfortran.so.5
# 可选：numpy.libs 目录若为空可一并删除
python3 scripts/Write-RuntimeManifest.py --payload <payload> \
  --components scripts/payload/components.json --runtime-id <new-id> --output <manifest.json>
python3 scripts/Prepare-Runtime.py --manifest <manifest.json> \
  --payload <payload> --output <prepared-dir>
python3 scripts/payload/check_gsas_native.py --payload <payload>   # 不带 --allow-missing
```

预期收益：减少 24,559,232 B（约 23.4 MiB / 24.6 MB），并消除两个未匹配
依赖。风险与注意：

- `numpy-2.2.6.dist-info/RECORD` 仍列出这两个文件，删除后与 RECORD 不一致；
  运行时不做 RECORD 校验，不影响导入，但不要用 `pip check/verify` 作为
  完整性门禁。
- 若将来更换 NumPy wheel 或改为动态 BLAS，需重新评估；本结论只对上述
  wheel 字节成立。
- 删除后必须重新生成清单、重新签名并重新做应用内验证，包含相关 NumPy/SciPy
  导入和实际精修路径；不能沿用旧 HAP 的哈希或证据。只有 C 复核新包并由组长
  接受后，才能将候选移除写为最终分发结论。

## 4. 许可证与 NOTICE 位置

- 组件主许可：`payload/licenses/<component>/LICENSE`（CPython、NumPy、
  SciPy、PyCifRW、GSAS-II、bridge 等）。
- 内嵌第三方许可原文：
  [`packaging/licenses/third-party/`](../packaging/licenses/third-party/NOTICE.md)，
  含 NOTICE 汇总与 `SOURCES.json`（每个文件的上游 URL、版本、SHA-256）。
- 8 个 GSAS-II 扩展及其静态 FortranRuntime（Apache-2.0 WITH
  LLVM-exception）不由本清单重复，见 C 的签名 HAP 记录与
  [EXTENSIONS_BUILD](EXTENSIONS_BUILD.md)。

## 5. 未决项

| 项 | 说明 | 责任 |
|---|---|---|
| NumPy/SciPy wheel 构建补丁与配置 | 社区包未提供；不能声称与上游源码逐字一致 | 向发行方索取或 C 自行重建 |
| 内嵌库补丁 | libffi/GDBM/OpenSSL/bzip2/xz/ncurses/expat 是否打过补丁未记录 | 同上 |
| OpenSSL 1.1.1w EOL | 已在静态模块中；发布说明应披露，后续评估升级 | C/组长决策 |
| 最终 HAP 字节复核 | 本清单基于基础载荷；签名 HAP 的 strip/重签名会改变哈希 | C |
| `distributionReview` | 仍为 `pending` | C/组长 |

## 6. 复现方式

```sh
# 依赖图（需要 readelf；对 payload 全量扫描）
find <payload> -name '*.so*' -exec readelf -d {} \; | grep NEEDED
# 版本字符串
strings <file> | grep -E 'OpenBLAS|OpenSSL|libmpdec|expat_|6\.6\.2025|3\.49\.1'
# 构建配置
sed -n '/build_time_vars/,/^}/p' <payload>/runtime/lib/python3.12/_sysconfigdata__ohos_aarch64-linux-ohos.py
```

## 7. B 的处置说明（是否自行编译/修改）

**结论：B 没有编译、打补丁或替换清单中的任何社区二进制。** 全部来自上表所列社区包；
B 只做“哈希校验下载 → 解包/复制 → 按发布门禁裁剪文件集合”。唯一的内容级改动是
`finalize_payload.py` 把零字节标记文件写成一个换行（仍为合法 Python/`py.typed` 标记）。
因此**没有 B 自己的工具链版本和构建日志**：这些组件不是 B 构建的。

| 组件 | 来源 | B 的处理 | 是否自行编译/修改/替换 |
|---|---|---|---|
| CPython 3.12.9 | 社区 tarball（volces `ophcd.pkg`） | 解包；复制 `libpython3.12.so` 与 stdlib；排除 `test`、`idle_test`、`ensurepip`、`distutils-precedence.pth`、`config-3.12-*`；删除 `pip` 与字节码；零字节标记规范化 | 未自行编译/修改/替换（仅裁剪文件集合） |
| CPython 附带 libffi 3.4.4 / GDBM 1.24 | 同上 tarball | 原样复制到 `runtime/lib/` | 未自行修改 |
| CPython 静态内嵌 OpenSSL 1.1.1w、SQLite 3.49.1、bzip2 1.0.8、XZ 5.8.2、ncurses 6.6、Expat 2.6.4、libmpdec 2.5.1 | 社区 CPython 构建方在构建时静态链接 | 未接触 | 未自行修改 |
| CPython `readline` 模块（libedit） | 同上，静态链接 | 未接触；版本未嵌入二进制 | 未自行修改；版本未知 |
| gettext 0.26 | 仅出现在 CPython 构建的 `LIBS=-lintl` 与依赖路径 | 载荷内无任何 ELF NEED `libintl`，未随应用分发 | 未分发，B 未处理 |
| NumPy 2.2.6 | 社区 wheel（cnb pypi） | 原样解包写入；删除 `tests`、归档类文件、`_sobol_direction_numbers.npz`（数据文件）；跳过 wheel 根级文件 | 未自行编译/修改/替换二进制（仅裁剪文件集合） |
| NumPy 附带 OpenBLAS64 0.3.23.dev + libgfortran 9.3.0 | 同上 wheel 的 `numpy.libs` | 原样保留（已判定可移除，但未改字节） | 未自行修改 |
| SciPy 1.16.3 | 社区 wheel（cnb pypi） | 原样解包写入；同样裁剪 `tests`、归档、`.npz` | 未自行编译/修改/替换二进制 |
| SciPy 附带 OpenBLAS 0.3.29 | 同上 wheel 的 `scipy.libs` | 原样保留 | 未自行修改 |
| PyCifRW 5.0.1 | 社区 sdist | **只复制纯 Python 源码**；StarScan C 加速器未构建（第二阶段曾在真机单独构建，第三阶段载荷不含） | 未自行编译/修改；有选择的文件复制 |
| GSAS-II 2.0.0 | 锁定提交 `2b4aba1b` 源码 | 复制源码并裁剪：排除 `pydiffax`/DIFFaX、`G2shapes.py`、`help`、`install`、字节码 | 未自行编译（8 个扩展由 C 用 Flang 20.1.8 重建） |
| bridge 1.1.0 | 本仓库源码 | 直接复制 | 非社区包 |

### 构建配置与日志

- B 没有为上述组件运行任何编译器，因此**没有工具链版本、构建命令或构建日志**。
- 载荷 `_sysconfigdata__ohos_aarch64-linux-ohos.py` 记录的是**社区构建方**的配置：
  `CC=clang`、`CFLAGS=-fPIC -O2 -fuse-ld=bfd`、`--enable-shared`、`--with-openssl=…`，
  依赖 openssl、sqlite3、readline、ncurses、gdbm、gettext 0.26、xz 5.8.2、
  libffi 3.4.4、bzip2 1.0.8。这是社区记录，不是 B 的构建。

### 社区仓库、维护者与联系方式

| 项 | 已知 | 未知 |
|---|---|---|
| 发布者 | OpenHarmonyPCDeveloper 社区；Python 索引 `https://pypi.cnb.cool/OpenHarmonyPCDeveloper/pypi`；CPython 在 `artifacts-cn-beijing.volces.com/.../ophcd.pkg` | 具体维护者、联系方式 |
| 构建归档 | `OpenHarmonyPCDeveloper/build_in_harmonyos`（GitCode）：`archives/n/numpy`、`archives/l/libedit`、`archives/g/gettext` | 归档只有 NumPy 1.26.4/2.5.2，**没有 2.2.6、没有 SciPy**；gettext 只有 0.22.5.1（载荷构建记录为 0.26） |
| gettext | 归档 0.22.5.1；载荷构建记录 0.26 | 0.26 的来源与构建方 |
| libedit | 归档 20240808、20240817、20251016-3.1 | 载荷 `readline` 模块二进制无版本串，无法确认对应版本；构建记录未知 |
| SciPy OpenBLAS | 来自社区 SciPy 1.16.3 wheel 的 `scipy.libs`，版本 0.3.29 | 构建仓库、维护者、构建记录：不知道 |

以上“不知道”为如实说明，不推断联系人。已交付的清单与许可文件未被本节的补充改写。
