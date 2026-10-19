> 历史阶段 1 记录。2026-10-19 的 8 模块本地构建、依赖修复及应用内验收见 [C_NATIVE_ACCEPTANCE.md](C_NATIVE_ACCEPTANCE.md)，以下缺模块/导入失败描述仅对应旧 HAP。

C 阶段 1：macOS 开发原生库签名与 HAP 装配

本地基线：A a1fe97e（已包含 B 665c001）+ C 既有修复。只交付本地开发验收，不代表科学计算、许可证审查或正式发布通过。

原始故障：RuntimeInstaller 将扩展 ELF 解到可写 files/runtime 目录后，应用加载 math 扩展失败（No error information）。仅为同一文件补开发自签名仍失败。把标准库扩展装入 HAP 的原生库目录后，应用内 math.sqrt(9)=3、bridge、CifFile、_ctypes 均通过。实际模块路径为 /data/storage/el1/bundle/libs/arm64/…；证据来自应用进程，不是 /data/local/tmp 壳层。

实现：

- Sign-NativeModules.py 使用 DevEco 自带 Java、llvm-strip/objcopy 和 binary-sign-tool.jar；复制输入到新输出，保留原始文件，逐项记录签名前后 SHA-256、大小、架构、SONAME/NEEDED 和签名工具结果。支持 .so 及版本化 ELF；不需要帐号、私钥或证书。
- Stage-NativeRuntime.py 把签过的 ELF 移到 payload/libs，生成每项准确归属的派生 components 清单和 Python 模块映射。保留帮助库的依赖名称；SciPy 两个同名 _zeros 扩展使用不同目标名，映射仍保留其完整 Python 模块名。排除一个不可导入的 .so.t 临时备份。
- bridge/native_loader.py 仅为清单声明的嵌套扩展创建 ExtensionFileLoader；纯 Python 包仍在 runtimeRoot。映射拒绝路径跳转、文件名冲突及缺失目标；安装可重复调用，不执行用户传入代码。
- python_host.cpp 用公开 dladdr 获取当前解释器的安装库目录，加入 Python 查找路径并安装映射。CoreConfig/CORE_API 字段保持不变，既有 GIL 修复保留。
- build-profile.json5 的 collectAllLibs 收集版本化依赖；debugSymbol.exclude 保留已签名库的字节，防止后续 strip 破坏签名或哈希。CMake 继续去掉主机临时 RUNPATH。
- Write-RuntimeManifest.py/release_tools.py 支持严格的 .so[.数字版本] 文件名；仍校验架构、所有权和逐文件哈希。GSAS 原生门禁认识映射布局，仍拒绝缺件、无效映射及 pydiffax。

复用顺序（在集成源码根目录；所有输出路径均须为新路径）：

1. python3 scripts/ohos/Sign-NativeModules.py --input RAW_PAYLOAD --output SIGNED_PAYLOAD --report SIGN_RECEIPT.json --development-self-sign
2. python3 scripts/ohos/Stage-NativeRuntime.py --input SIGNED_PAYLOAD --output NATIVE_PAYLOAD --components scripts/payload/components.json --components-output COMPONENTS_NATIVE.json --report NATIVE_LAYOUT.json
3. 将 NATIVE_LAYOUT.json 中的 nativeLibBuildOption 写到 app/entry/build-profile.json5 的 buildOption.nativeLib。它只配置原生库收集与 strip 排除，不增加权限。沿用 B 对应 CPython 3.12.9 的头文件/链接库；不要使用 macOS Python 库。
4. python3 scripts/Write-RuntimeManifest.py --payload NATIVE_PAYLOAD --components COMPONENTS_NATIVE.json --runtime-id UNIQUE_RUNTIME_ID --output RUNTIME_MANIFEST.json
5. python3 scripts/Build-App.py --check --build-mode release --runtime-manifest RUNTIME_MANIFEST.json --runtime-payload NATIVE_PAYLOAD --output-dir BUILD_EVIDENCE

签名及文件装配均在生成清单之前完成。只要字节或映射发生变化，就更换 runtimeId 并重算清单；不要修改 pending 状态来绕过发布门禁。

当前边界：NumPy 已定位到安装目录的 _multiarray_umath，但因它依赖 libpython3.12.so.1.0 而失败；SciPy 随之无法导入。现有解释器库名为 libpython3.12.so。未复制出第二份解释器或伪造别名来掩盖此差异，需 B 给出一致的 ABI/依赖方案。libc.musl-aarch64.so.1、libgcc_s.so.1 仍是静态未匹配项。8 个 GSAS 计算扩展仍缺，启动预检应继续返回 CORE_NOT_READY。

诊断检查只在独立验证副本启用，最终开发 HAP 不含该探针或详细错误界面。正式签名、API20/API24 设备矩阵、真实五阶段、终态产物导出与许可证终审属于后续验收。

依据：[OpenHarmony 二进制签名工具](https://gitcode.com/openharmony/developtools_hapsigner/tree/OpenHarmony-6.1-LTS)、[Huawei 模块构建配置](https://developer.huawei.com/consumer/cn/doc/doccenter-deveco-studio/ide-hmos-hvigor-build-profile-app)。签名工具识别签名不等于应用可加载；本轮以实际 HAP 进程检查为准。
