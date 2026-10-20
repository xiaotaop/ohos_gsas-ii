# 第三方运行时组件 NOTICE（成员 B）

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

其他说明：

- `libz.so` 由 OHOS 系统提供（SDK sysroot 中的 `libz.so`），未随应用分发；
  许可证为 zlib。`binascii`、`zlib` 模块动态链接它。
- `libc++_shared.so` 由应用打包（`libs/arm64-v8a/`），许可证为
  Apache-2.0 WITH LLVM-exception；由 C 的 HAP 许可清单处理。
- `libgcc_s.so.1`、`libc.musl-aarch64.so.1` 只出现在 libgfortran 的
  NEEDED 中；移除 NumPy 遗留的 OpenBLAS64 与 libgfortran 后，
  这两个未匹配项随之消失。
- gettext/libintl 只出现在 CPython 构建的 `LIBS=-lintl` 中，载荷内没有任何
  ELF 的 NEEDED 指向 `libintl`，未随应用分发。

许可证文本取自下列上游发布版本；`gcc-runtime-COPYING.txt` 取自 Debian
`gcc-11-base` 的版权文件（含 GPL-3 与 GCC Runtime Library Exception 3.1），
实际运行库由 GCC 9.3.0 构建，例外条款文本相同。

最终分发判断由成员 C 作出；本 NOTICE 不构成许可批准。
