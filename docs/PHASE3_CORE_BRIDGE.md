# 第三阶段：Python Bridge 与本地核心自测（成员 B）

接口基线：`docs/CORE_API.md` v1.0（提交 `5e486c6`）。本文档描述 `bridge/`
包——嵌入式 Python Bridge 与宿主侧本地 CoreService 仿真层。原始开发分支为
`core/python-bridge`，现已由组长完成审核并合入 `main`。

## 1. 组件布局

| 文件 | 职责 | 对应契约章节 |
|---|---|---|
| `bridge/engine.py` | `initialize`/`execute` 稳定入口、事件流水线、阶段边界取消、产物写出、私有 traceback 落盘 | §3.1–3.2、§6–§8、§10 |
| `bridge/core.py` | `powder-five-stage-v1` 真实 GSAS-II 精修器（迁移自 `poc/core_refinement.py`，容差一致） | §5、§8 |
| `bridge/fake_core.py` | 假计算 refiner：同协议、同事件流，短延时返回基线数值（交接书 §7.2 第 2 步；仅限开发期，禁止进入发布 HAP） | 同上 |
| `bridge/service.py` | 本地 CoreService 仿真：单工作线程、`BUSY` 单任务门、jobId 唯一、快照、事件分发（模拟未来 N-API 的职责） | §3、§7、§10 |
| `bridge/request.py` | 请求同步校验（结构/recipe 错误不发事件） | §5 |
| `bridge/errors.py` | 统一错误码与脱敏（绝对路径、对象地址、traceback 不进 UI 通道） | §6、§9 |
| `bridge/events.py` | CoreEvent 构造不变式（序号连续、eventId 唯一、percent 不倒退、单终态） | §6 |
| `bridge/files.py` | `fileId`→沙箱目录解析与五份 fixture SHA-256 门禁 | §4 |

## 2. 运行自测

假核心（任意真 Python，标准库即可）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Run-BridgeSelfTest.ps1
```

含真实 GSAS-II 五阶段数值验收（使用本机复跑环境）：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Run-BridgeSelfTest.ps1 `
  -Python D:\miniconda3\envs\gsas-poc\python.exe -DllDirectory D:\mingw64\bin
```

生成的事件流按 `scripts/Validate-CoreContracts.py` 的同一套语义函数校验，
等价于组长门禁。

## 3. 已覆盖的 §5.3 验收标准

- 契约校验通过（自测复用官方语义校验器）。
- 第二个并发任务同步返回 `BUSY`，且不产生任何事件。
- Python 计算只在 `gsas-core-worker` 线程执行（有专项断言）。
- 每任务恰一个终态事件（服务层对二次终态抛异常）。
- PbSO4 五阶段满足既定容差（真实场景，`validateAgainstBaseline` 在引擎内强制执行）。
- Python 异常映射为 `INTERNAL_ERROR`，traceback 仅写入
  `jobs/<jobId>/logs/traceback.log` 私有日志；UI listener 抛异常不影响任务。

## 4. 设备侧待验项（N-API 与运行时装配已交付）

1. ~~C++ N-API 模块：嵌入 CPython 3.12.9、按 §8 签名调用本包两个入口、
   线程安全函数切回 ArkTS。本包接口即 N-API 的稳定边界。~~
   已在 `core/napi-runtime` 分支交付（`napi_core.cpp`、`python_host.cpp`、
   `CoreBridgeService.ets`），含真实 DevEco 无签名构建与 aarch64
   交叉编译/自签名；设备 dlopen 与 `Py_Initialize` 运行未验，
   详见 [PHASE3_NAPI_CORE](PHASE3_NAPI_CORE.md) §3.2/§3.3。
2. 应用沙箱内验证 `runtime`/`jobs`/`outputs` 目录与重签名后的
   NumPy/SciPy/PyCifRW/GSAS-II 加载。（`RuntimeInstaller` 已提供影子解包、
   激活、升级回滚与崩溃恢复；设备端执行未验证。）
3. 发布构建排除 `pydiffax`：本包不含任何 `pydiffax` 引用，自测有静态检查；
   载荷门禁 [`scripts/payload/check_gsas_native.py`](../scripts/payload/check_gsas_native.py)
   同时拒绝 `pydiffax` 并要求 8 个 GSAS-II 原生扩展。扩展尚未构建，是
   设备端相文件导入与五阶段的发布阻断项（见 PHASE3_NAPI_CORE §5）。

## 5. 已知限制（MVP 边界）

- `powder-five-stage-v1` 只接受一支 X 射线加一支中子直方图的标准 PbSO4
  组合；其余组合返回 `INVALID_REQUEST` 而非静默降级。
- 取消为阶段边界协作式取消，不中断进行中的单次 GSAS-II 数值调用。
- 假核心写出的是占位 `.gpx`（文本 stub），仅供 UI 联调。
- 换设备/环境时 `D:\mingw64\bin` 等路径须重新探测（交接书 §10.5 同理）。
