# macOS / Linux host → OHOS ARM64 extensions

This is member C's alternative to the on-device recipe in
`docs/EXTENSIONS_BUILD.md`. It built all eight extensions on macOS through a
**disposable Ubuntu 22.04 amd64 Docker container**, using Flang/LLVM **20.1.8**
(the device recipe uses 20.1.0). Rebuild FortranRuntime/FortranDecimal from
matching 20.1.8 sources. Never link host Linux Fortran archives into OHOS files.

`gsas-ohos.patch` applies to the unmodified upstream tree at
`2b4aba1bc44de63a3da9d4495944c3b99e389399`. It uses target Python/NumPy headers,
host f2py/Cython generation and clang as the final OHOS linker. It excludes the
DIFFaX library, pydiffax wrapper/target and standalone tools before compilation.
The one functional upstream fix moves `fmask`'s unreachable `import_array()`
before the module return. A real NumPy-array call was tested on the emulator.

## Inputs and mounts

Use a new host working directory mounted at `/work`; mount the expanded runtime
input read-only at `/runtime-input`; mount this recipe directory read-only at
`/recipe`. Do not mount an existing source checkout at `/work/GSAS-II`: Meson/f2py
and `patch` write into that disposable source copy.

* `/work/GSAS-II`: extract the pinned upstream archive; its hash and LLVM source
  URLs/hashes are in `sources.lock.json`.
* `/work/llvm-project/{llvm,clang,flang,cmake}`: extract each matching source
  archive into the corresponding directory (remove the archive's top directory).
* `/runtime-input/extract/python-3.12.9-ohos-aarch64/include/python3.12`: actual
  OHOS Python 3.12.9 headers, including the target `pyconfig.h`.
* `/runtime-input/payload/libs/libpython3.12.so`: the actual interpreter shipped
  in the payload; `/runtime-input/payload/runtime/lib/python3.12/site-packages/numpy`
  must include the target NumPy 2.2.6 `_core/include` and `f2py/src` files.
* Copy **the installed DevEco native SDK**, without redistributing it, into
  `/work/sdk`: `sysroot/` from `native/sysroot`, `include/c++/v1/` from
  `native/llvm/include/c++/v1`, `lib/aarch64-linux-ohos/` from
  `native/llvm/lib/aarch64-linux-ohos`, and `clang-resource/15.0.4/` from
  `native/llvm/lib/clang/15.0.4`. These are deliberate container paths.

Verify input hashes before extraction. `setup-container.sh` installs the recorded
compiler package version and host generators inside the disposable container;
it requires root and network access. If the pinned apt version disappears,
stop and record a new toolchain deviation rather than silently upgrading.

```sh
sh /recipe/setup-container.sh
sh /recipe/Build-Extensions.sh
```

The build leaves eight `*.cpython-312-aarch64-linux-ohos.so` under
`/work/build-ohos/sources` (including `k_vec_cython/`). Inspect AArch64/ET_DYN,
`PyInit_*`, `DT_NEEDED` and prohibited targets. Copy only the eight modules to
`runtime/lib/python3.12/site-packages/GSASII/` in a **new** expanded payload.
Do not put the LLVM source/build tree or compiler archives in the runtime.

## Prepare an application payload

1. Assemble/prune the runtime using `scripts/payload/assemble_payload.py` and
   `prune_release_payload.py`; keep NumPy's runtime helper
   `numpy/_core/tests/_natype.py` (the assembly recipe now preserves it).
2. If consumers require `libpython3.12.so.1.0` but the single shipped interpreter
   is `libpython3.12.so`, run `Normalize-PythonNeeded.py --input RAW --output
   NORMALIZED --report needed.json`. It alters only exact dynamic dependencies
   in a new copy and invalidates the old manifest. It does not establish ABI
   compatibility or add an interpreter alias.
3. Use `Sign-NativeModules.py` on that copy: strip first, remove stale `.codesign`,
   then sign. The tested development self-signatures are **not formal release
   signatures**. Preserve the signing receipt and original download hashes.
4. Run `Stage-NativeRuntime.py --input SIGNED --output PAYLOAD --components
   components.json --components-output components-native.json --report layout.json`.
   It flattens ELFs and records the Python names, including namespace packages
   whose empty directories would disappear from a HAP. Re-staging preserves
   existing mappings. Use its exact `nativeLibBuildOption` in the entry profile.
5. Refresh production bridge files, excluding `fake_core.py` and tests. Generate
   `Write-RuntimeManifest.py` **after** the final byte changes. Then run the strict
   native gate, `Prepare-Runtime.py`, `Build-App.py`, `Audit-Hap.py` and
   `Build-HapSbom.py`. With `--native-build-receipt native-modules.json`, the SBOM
   verifies all eight hashes against the HAP before adding static LLVM obligations.
6. Install and run the application. A command-line import pass alone does not
   establish HAP namespace resolution, scientific correctness or release readiness.

See `docs/C_NATIVE_ACCEPTANCE.md` for the tested build, remaining licensing and
hardware gates, and delivery hashes. Binaries, SDK files, signing material and
HAPs remain excluded from Git; this PR contains sources, recipes and compact
verification records. The full local payload remains available for handoff.
