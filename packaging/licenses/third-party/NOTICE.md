# 第三方运行时组件 NOTICE（B 提供，C 复核补充）

本目录保存运行时载荷内嵌第三方组件的许可证原文，供成员 C 的最终 SBOM、
许可清单与分发审查使用。许可证文本按上游发布版本获取（2026-10-20），
来源与 SHA-256 见 [SOURCES.json](SOURCES.json)。

| 组件 | 版本 | 链接方式 | 许可证 | 文本 |
|---|---|---|---|---|
| libffi | 3.4.4 | 动态（`libffi.so.8`，`_ctypes` NEEDED） | MIT | `libffi-3.4.4-LICENSE.txt` |
| GDBM | 1.24 | 动态（`libgdbm.so.6`，`_gdbm` NEEDED） | GPL-3.0-or-later | `gdbm-1.24-COPYING.txt` |
| OpenSSL | 1.1.1w | 静态（`_ssl` / `_hashlib`） | OpenSSL/SSLeay 双许可 | `openssl-1.1.1w-LICENSE.txt` |
| SQLite | 3.49.1 | 静态（`_sqlite3`） | Public Domain | `sqlite-3.49.1-PUBLIC-DOMAIN.txt` |
| bzip2 | 1.0.8 | 静态（`_bz2`） | bzip2-1.0.6 | `bzip2-1.0.8-LICENSE.txt` |
| XZ / liblzma | 5.8.2 | 静态（`_lzma`） | 0BSD | `xz-5.8.2-COPYING.txt` |
| ncurses | 6.6.20251230 | 静态（`_curses`） | X11 风格 | `ncurses-6.6-COPYING.txt` |
| Expat | 2.6.4 | 静态（`pyexpat`） | MIT | `expat-2.6.4-COPYING.txt` |
| libmpdec | 2.5.1（随 CPython） | 静态（`_decimal`） | BSD-2-Clause | `libmpdec-2.5.1-LICENSE.txt` |
| OpenBLAS（SciPy） | 0.3.29 | 动态（`scipy.libs`，23 个模块 NEEDED） | BSD-3-Clause | `openblas-0.3.29-LICENSE.txt` |
| GCC Runtime / libgfortran | 9.3.0（Alpine） | 动态，**仅被 NumPy 未使用的 OpenBLAS64 引用** | GPL-3.0-or-later WITH GCC-exception-3.1 | `gcc-runtime-COPYING.txt` |
| OpenBLAS（NumPy 遗留） | 0.3.23.dev | 动态，**无消费者** | BSD-3-Clause | 同 OpenBLAS 文本；该库已列入移除 |
| GNU readline | 8.3（ELF 定义对象） | 静态（readline 扩展） | GPL-3.0-or-later | `readline-8.3-COPYING.txt` |
| gettext libintl | 发行方声明 0.26；准确构建待核 | 静态（libpython） | LGPL-2.1-or-later（0.26 上游） | `gettext-libintl-0.26-COPYING.LIB.txt` |

其他说明：

- `libz.so` 由 OHOS 系统提供（SDK sysroot 中的 `libz.so`），未随应用分发；
  许可证为 zlib。`binascii`、`zlib` 模块动态链接它。
- `libc++_shared.so` 由应用打包（`libs/arm64-v8a/`），许可证为
  Apache-2.0 WITH LLVM-exception；由 C 的 HAP 许可清单处理。
- `libgcc_s.so.1`、`libc.musl-aarch64.so.1` 只出现在 libgfortran 的
  NEEDED 中；移除 NumPy 遗留的 OpenBLAS64 与 libgfortran 后，
  C 的精简签名候选 HAP 已无这两个库和未匹配项；尚待新包真机验收，旧包保持原状。
- **C 实际 HAP 复核更正**：不能由没有 `DT_NEEDED libintl` 推断未分发。`libpython3.12.so` 实际定义了 6 个 `libintl_*` 函数；gettext/libintl 的准确构建对应关系及静态链接义务仍待核，C 已补入上游 LGPL 文本。readline 的已定义版本对象指向 GNU readline 8.3（GPL-3.0-or-later）；`EditLine wrapper` 是包装器文字，不能据此认定 libedit，见 [C 复核记录](../../../docs/C_THIRD_PARTY_REVIEW.md)。

许可证文本取自下列上游发布版本；`gcc-runtime-COPYING.txt` 取自 Debian
`gcc-11-base` 的版权文件（含 GPL-3 与 GCC Runtime Library Exception 3.1），
实际运行库由 GCC 9.3.0 构建，例外条款文本相同。

最终分发判断由成员 C 作出；本 NOTICE 不构成许可批准。

C 新增的两份 GNU 文本从官方源码归档按原始字节取得，源归档与成员哈希均见 SOURCES.json。准确的修改源码、静态链接/重链接材料与其他分发义务仍待核，不因收录文本而批准。原始 B 清单中的两份遗留 GNU 库仅在 C 新精简候选中排除；许可原文继续保留作审查历史。
