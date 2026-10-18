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
   登记为 `log`，再交付终态；所有终态后 `finishJob` + `releaseJob`。
   该 B03 方案沿用成员 C 的建议，**仍待组长批准**。
6. 重启：`listInterruptedJobs` 标记并 `finishJob`；其快照由门面合成 seq-0
   `job.failed`（`PROCESS_INTERRUPTED`），计算永不恢复。

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

## 4. 验证命令

```sh
python3 -m unittest discover -s tests -p 'test_runtime_manifest_tool.py' -v
GSAS_TYPESCRIPT_PATH=<typescript@5.4.5 路径> node --test tests/runtime-installer-host.test.cjs
GSAS_TYPESCRIPT_PATH=<同上> node --test tests/core-bridge-host.test.cjs
```

宿主套件用真实文件系统跑实际 `.ets` 源码，但只转译不类型检查；
真实类型检查以 DevEco `default@CompileArkTS` 为准（本文写作时 0 错误；
65 项警告均为项目既有类别的建议性提示——"Function may throw exceptions.
Special handling is required."——分布于成员 C 既有文件与 B 的新文件，
与成员 C 交付时已记录的风格一致）。

## 5. 已知限制

- `GSAS_HAS_PYTHON` 分支尚未在任何环境编译过：本机没有 aarch64 的
  Python 头/库；真实载荷到位后需先跑一次带定义的交叉编译。
- 门面/安装器的行为由宿主测试证明，设备端实际加载（dlopen 链、
  `libs/arm64-v8a` 的 `libpython3.12.so` 解析、沙箱权限）未在真机验证；
  无签名材料，`assembleHap` 产物为未签名 HAP。
- 事件通道队满丢弃（快照仍完整，符合空 sink 规则）；第二次终态被丢弃
  （Python 侧此情形抛异常，端口有意不复制崩溃行为）。
- B03 失败/取消日志进用户可见产物仍待组长批准；私有 traceback 只写
  `jobs/<jobId>/logs/`，从不登记。
- `RefinementPanel` 在核心就绪瞬间重挂，表单文本会被清空（A 侧组件契约
  如此约定；页面加载早期通常先于用户输入完成）。
- Windows 本机 `file-service-host.test.cjs` 因 `os.tmpdir()` 盘符路径被
  服务根校验拒绝，属宿主环境限制；CI（ubuntu）不受影响。
