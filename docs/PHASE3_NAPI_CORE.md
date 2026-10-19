# 阶段 3 M2：设备侧计算核心交付（成员 B）

本文档记录 C++ N-API 模块、嵌入式 CPython 宿主、设备运行时装配与
ArkTS 核心门面的实现、构建方式与已知限制。契约依据：
[CORE_API v1.0](CORE_API.md) §8、[运行时打包](RUNTIME_PACKAGING.md) §2/§3、
[成员 C 交接](MEMBER_C_HANDOFF.md) §5、[阶段 3 核心桥接](PHASE3_CORE_BRIDGE.md)。

## 1. 交付组件

| 组件 | 路径 | 职责 |
|---|---|---|
| N-API 模块 | `app/entry/src/main/cpp/napi_core.cpp` | `libgsas_core.so`：Promise 化 initialize/shutdown、同步单任务门（acquire/begin 顺序中的 acquire/start/cancel/snapshot）、线程安全函数按事件转发原始 JSON（逐字节，不重序列化） |
| C++ 编排 | `app/entry/src/main/cpp/core/core_service.{h,cpp}` | `bridge/service.py` 的对等移植：`gsas-core-worker`、`BUSY` 门、进程期 jobId 台账、快照、恰一个终态 |
| CPython 宿主 | `app/entry/src/main/cpp/python/python_host.{h,cpp}` | 嵌入 CPython 3.12.9，按 §8 签名调用 `bridge` 的 `initialize`/`execute`；`GSAS_HAS_PYTHON` 关闭时编译为可链接的 `CORE_NOT_READY` 桩 |
| 设备运行时装配 | `app/entry/src/main/ets/services/RuntimeInstaller.ets` | `rawfile/runtime` → `filesDir/runtime` 影子解包、逐项哈希复核、激活标记、目录交换式升级与崩溃恢复；失败不覆盖已激活副本 |
| 清单生成 | `scripts/Write-RuntimeManifest.py` | 扫描 B 展开的载荷目录，生成设备侧 `runtime/manifest.json` 与发布清单；复用成员 C 的 `release_tools` 权威门禁，自身从不下载 |
| ArkTS 门面 | `app/entry/src/main/ets/services/CoreBridgeService.ets` | 实现 A 冻结的 `CoreService` 接口；按 §5 顺序编排（见下）；宿主测试通过注入接缝驱动 |
| 应用接线 | `services/AppServices.ets`、`pages/Index.ets`、`cpp/types/libgsas_core/*` | 进程期单例、preferences 持久化活动/近期 jobId、初始化完成后换分支重挂 `RefinementPanel` |

## 2. §5 调用顺序映射

1. 文件服务就绪 → `RuntimeInstaller.install` 激活 runtimeRoot → `initializeCore`。
2. 请求校验在门面完成（recipe/cycles/路径名/五输入 ID）；`acquireJob`（C++ 门）
   成功后才 `beginJob` 锁定输入，再 `startAcquiredJob`。同步拒绝不产生事件，
   两层门立即关闭（`finishJob` + `releaseJob`）。
3. Python 只在 worker 线程执行；事件经 tsfn 回到 ArkTS，处理链串行保序。
4. `job.completed`：逐产物 `registerOutput` 成功后才向页面交付，登记失败项从
   `artifacts` 剪除（界面拿到的 fileId 均可查询/导出）。
5. 失败/取消：先写脱敏用户日志到 `outputs/<jobId>/job-log.txt`（仅契约级
   code/message/reason 与过滤后的 `job.log` 行；不含沙箱路径与 traceback），
   登记为 `log`，再把登记返回的 `artifacts`（v1.1 可选字段）放入终态载荷交付；
   所有终态后 `finishJob` + `releaseJob`。登记未完成时载荷不携带 `artifacts`，
   页面如实提示"日志登记未完成"，绝不从路径/文件名/历史消息推导 fileId。
   组长已在 2026-10-19 批准该顺序并要求同步契约、Schema、示例、类型、UI 和
   测试；该同步已在增量 PR `core/b03-terminal-artifacts` 完成宿主级实现，
   待组长复核后方可关闭。
6. 重启：`listInterruptedJobs` 标记并 `finishJob`；其快照由门面合成 seq-0
   `job.failed`（`PROCESS_INTERRUPTED`，payload 形状 `{state:'failed',
   error:{code,retryable:true}}`），计算永不恢复。任何终态（completed/failed/
   cancelled/中断合成）都持久化到 `outputs/<jobId>/core/terminal-snapshot.json`
   （与交付事件同形，含已登记 `artifacts`），供进程重启后 `getJobSnapshot` 在
   原生台账缺失时按 jobId 恢复；读回快照经形状再校验，未知/已清理 ID 保持
   `JOB_NOT_FOUND`，由 A 端只做失效近期 ID 的降级，不伪造中断。

## 3. 构建与载荷装配

本机（Windows，DevEco Studio 完整 SDK）已验证的无签名构建：

```sh
# 仓库 app/ 目录；使用 DevEco 自带 node/ohpm/hvigor
"<DevEco>/tools/node/node.exe" "<DevEco>/tools/ohpm/bin/pm-cli.js" install --all
DEVECO_SDK_HOME="<DevEco>/sdk" JAVA_HOME="<DevEco>/jbr" \
  "<DevEco>/tools/node/node.exe" "<DevEco>/tools/hvigor/bin/hvigorw.js" \
  --mode module -p module=entry@default -p product=default -p buildMode=debug \
  assembleHap --no-daemon
```

产物：`entry/build/default/outputs/default/entry-default-unsigned.hap`，
含 `arm64-v8a/libgsas_core.so`（当前为 `GSAS_HAS_PYTHON` 关闭的桩构建）。
带真实运行时的发布构建仍走 `scripts/Build-App.py`（需 `devecocli`）。

启用嵌入式解释器编译的开关是头文件存在性：将 B 展开载荷中的
CPython 头放入 `app/entry/src/main/cpp/python/include/`、
`libpython3.12.so` 放入 `app/entry/src/main/cpp/python/libs/<abi>/`
（两者已被 `.gitignore` 排除；`CMakeLists.txt` 检测到前者但缺后者时报错）。
载荷版本锁定见 RUNTIME_PACKAGING §2：CPython 3.12.9 / NumPy 2.2.6 /
SciPy 1.16.3 / PyCifRW 5.0.1 / GSAS-II 2.0.0@2b4aba1b；PoC 依据为
HAD-W24 上通过五阶段 PbSO4 的社区 ohos_aarch64 轮子（PHASE2_CORE_POC）。

载荷就位后：

```sh
python3 scripts/Write-RuntimeManifest.py --payload /work/runtime-payload \
  --components /work/components.json --runtime-id <id> --output /work/runtime-manifest.json
```

生成的 `payload/runtime/manifest.json` 随 `rawfile/runtime` 一并入包；
发布清单可直接交给 `Prepare-Runtime.py` / `Audit-Hap.py`，门禁不变。

### 3.1 载荷装配配方（已提交）

逐组件版本、下载地址、SHA-256、目录约定与每一步裁剪规则见
[`scripts/payload/README.md`](../scripts/payload/README.md)；`components.json`
是该目录下的 manifest 组件输入。2026-10-19 在宿主 x86_64 上按该配方完成了
一次无中断的完整装配与两级门禁：

- `Write-RuntimeManifest.py`：2214 个文件、约 178 MB、9 个组件，逐文件内容
  门禁（AArch64 ELF、无归档/字节码/外平台库）通过；
- `Prepare-Runtime.py`：再次复算全部哈希与内容，状态为
  `prepared-not-device-validated`。

装配过程暴露并记录了三类必须在发布载荷中处理的输入：CPython `ensurepip`
与 numpy/scipy 轮子自带的 `.whl`/`.a`、GSAS-II `help/`/`install/` 下的
`.gz`/`.tar.gz`，以及 SciPy 的 `_sobol_direction_numbers.npz`（ZIP 容器）。
前两类直接删除；`.npz` 仅被 Sobol QMC 引擎惰性读取，故该功能在载荷中明确
不可用，`scipy.stats` 的其余路径不受影响。门禁还要求文件大小 > 0，装配末尾
把上游的零字节包标记规范化为一个换行（仍为合法 Python/`py.typed` 标记）。

`GSASIIscriptable` 的静态导入闭包为 21 个模块级条目、缺失 0；函数内缺失
12 项全部指向未构建的原生扩展（`pyspg`、`pypowder`、`pytexture`、`fmask`、
`histogram2d`），见 §5。

### 3.2 OHOS aarch64 交叉编译（真实 CPython 3.12.9 头/库）

在 DevEco SDK 的 OHOS 工具链上，用 §3 所述载荷中的 `python/include` 与
`python/libs/arm64-v8a/libpython3.12.so` 对 cpp 目录做了一次完整交叉编译与
链接（Windows 侧 `cmake.exe`，源树为含本分支 CMakeLists 修复的副本）：

```sh
cmake.exe -G Ninja -S D:/gsas-cross/cpp -B D:/gsas-cross/build \
  -DCMAKE_TOOLCHAIN_FILE="D:/DevEco Studio/sdk/default/openharmony/native/build/cmake/ohos.toolchain.cmake" \
  -DOHOS_ARCH=arm64-v8a -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_MAKE_PROGRAM="D:/DevEco Studio/sdk/default/openharmony/native/build-tools/cmake/bin/ninja.exe"
```

编译启用 `-DGSAS_HAS_PYTHON` 并包含载荷头路径；`build.ninja` 记录了
`libpython3.12.so` 链接项。产物 `libgsas_core.so` 经 `file`/`readelf` 验证为
`ELF 64-bit LSB shared object, ARM aarch64 ... dynamically linked`，`SONAME`
为 `libgsas_core.so`，`NEEDED` 含 `libace_napi.z.so`、`libpython3.12.so`、
`libc++_shared.so`、`libc.so`；`Py_InitializeFromConfig` 等 25 个 `Py*`
符号作为动态未定义符号留给 `NEEDED` 的 `libpython3.12.so` 在加载时解析，
这正是共享库嵌入解释器的预期形态。该证据只覆盖交叉编译/链接，不含设备
dlopen 与 `Py_Initialize` 运行。

## 4. 验证命令

```sh
python3 -m unittest discover -s tests -p 'test_runtime_manifest_tool.py' -v
GSAS_TYPESCRIPT_PATH=<typescript@5.4.5 路径> node --test tests/runtime-installer-host.test.cjs
GSAS_TYPESCRIPT_PATH=<同上> node --test tests/core-bridge-host.test.cjs
```

嵌入式 §8 通道另有宿主冒烟（不进 CI：需要本机 libpython 开发包；复现命令见
`tests/python-host-embed-smoke.cpp` 头注释）。它用真实嵌入 CPython 加载真实
`bridge` 包并跑一个任务到唯一终态——在无 GSAS-II 载荷的宿主上必须恰好得到
`job.failed / CORE_NOT_READY` 且事件跨越 C capsule 边界。该冒烟曾暴露并促成
修复 `EmitCallback` 的 METH_O 参数缺陷（见 §5）。它不是 OHOS aarch64 证据，
也不做真实数值计算。

宿主套件用真实文件系统跑实际 `.ets` 源码，但只转译不类型检查；
真实类型检查以 DevEco `default@CompileArkTS` 为准（本文写作时 0 错误；
65 项警告均为项目既有类别的建议性提示——"Function may throw exceptions.
Special handling is required."——分布于成员 C 既有文件与 B 的新文件，
与成员 C 交付时已记录的风格一致）。

## 5. 已知限制

- `GSAS_HAS_PYTHON` 分支已在两类宿主上编译、链接：
  1. 宿主 x86_64（发行版 libpython3.10-dev）完成一次真实嵌入解释器加载冒烟；
     期间发现并修复了 `EmitCallback` 把 METH_O 单参数当元组解析的缺陷（修复前
     §8 execute 在真实解释器下必然抛 TypeError，桩构建与纯 Python 测试均无法
     暴露）。
  2. 2026-10-19 使用 DevEco OHOS 工具链 + CPython 3.12.9 ohos-aarch64 载荷的
     头文件与 `libpython3.12.so`，完成一次 `-DGSAS_HAS_PYTHON` 的 aarch64
     交叉编译与链接（证据见 §3.2）。
  仍**未关闭**：设备上 `libgsas_core.so` → `libpython3.12.so` 的 dlopen 链与
  `Py_Initialize` 运行、rawfile 解包与沙箱权限，均未在真机验证；载荷也未装入
  HAP 做端到端运行。
- 原生扩展 `pyspg`/`pypowder`/`pytexture`/`fmask`/`histogram2d` 未构建：
  `pyspg` 需要 flang 20.1.0，当前 DevEco SDK 与已核对的社区分发均未提供。
  `GSASIIscriptable` 的模块级导入闭包完整，但这些函数内导入在设备上会抛
  `ImportError`，对称性/部分粉末计算路径因此不可用；GSAS-II 载荷中不包含
  任何 `.so` 扩展。
- SciPy 的 Sobol QMC 因 `_sobol_direction_numbers.npz` 是 ZIP 容器而不随载荷
  发布（见 §3.1），`scipy.stats` 其余功能与 GSAS-II 所用路径不受影响。
- 门面/安装器的行为由宿主测试证明，设备端实际加载（dlopen 链、
  `libs/arm64-v8a` 的 `libpython3.12.so` 解析、沙箱权限）未在真机验证；
  无签名材料，`assembleHap` 产物为未签名 HAP。
- 事件通道队满丢弃（快照仍完整，符合空 sink 规则）；第二次终态被丢弃
  （Python 侧此情形抛异常，端口有意不复制崩溃行为）。
- B03 增量（终态 `artifacts`、跨进程终态快照与恢复）仅以宿主测试证明：
  未启用 `GSAS_HAS_PYTHON`、未构建 HAP、未上真机，不能计为真实载荷下的
  UI 可发现/可导出证据。私有 traceback 只写 `jobs/<jobId>/logs/`，从不登记。
- `RefinementPanel` 在核心就绪瞬间重挂，表单文本会被清空（A 侧组件契约
  如此约定；页面加载早期通常先于用户输入完成）。
- Windows 本机 `file-service-host.test.cjs` 因 `os.tmpdir()` 盘符路径被
  服务根校验拒绝，属宿主环境限制；CI（ubuntu）不受影响。
