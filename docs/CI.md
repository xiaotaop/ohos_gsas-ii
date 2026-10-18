# GitHub Actions 持续集成说明

## 1. 目标

本仓库使用 GitHub Actions 对无需 HarmonyOS PC 真机和专用 SDK 的内容进行持续验证。工作流文件位于：

```text
.github/workflows/ci.yml
```

流水线使用 GitHub 官方托管的 Ubuntu Runner、Python 3.12 和 Node.js 22，仅声明 `contents: read` 权限，不需要配置访问令牌或其他 Secret。

## 2. 触发条件

- 任意分支发生 push 时自动运行。
- 向 `main` 分支创建或更新 Pull Request 时自动运行。
- 可在 GitHub Actions 页面通过 `workflow_dispatch` 手动运行。

## 3. 质量门禁

流水线依次执行：

1. Python 文件语法编译检查（包括 Python Bridge）。
2. `contracts/` 和 `poc/results/` 中全部 JSON 文件的编码及语法检查。
3. 核心接口 Schema、请求示例及成功、失败、取消事件序列检查。
4. 五个 PbSO4 测试样例的 SHA-256 完整性检查。
5. Python Bridge 的请求校验、沙箱、事件、并发、取消、失败和产物自测。
6. 原生文件排他创建测试：已有文件、并发创建及符号链接不会被覆盖。
7. 宿主真实文件系统运行实际 FileService 源码，覆盖九项文件生命周期及符号链接防护场景。
8. 宿主运行时装配、HAP 内容门禁和构建记录测试（合成载荷，不证明真实运行时加载）。
9. ArkUI mock 状态模型的 TypeScript 类型检查、14 项行为/会话测试及契约示例同步检查。
10. A 的输入关联/记录归属模型 6 项、参数与本地记录草稿模型 12 项，以及正式 `.ets` 模型的契约/会话/宿主回放套件 18 项；后者复用 mock 套件的服务夹具，正式 HAP 不引入 mock。普通 TypeScript 转译只用于执行纯模型测试，ArkTS/HAP 检查仍由 DevEco 完成。
11. 核心服务 C++ 编排（`bridge/service.py` 移植）的宿主原生测试。
12. 设备运行时清单生成：合成载荷必须通过成员 C 的权威门禁并与 `Prepare-Runtime` 端到端一致。
13. 设备运行时装配器与核心门面在宿主环境运行实际 `.ets` 源码（装配器用真实文件系统，门面用注入接缝），固化成员 C 交接 §5 的调用顺序断言。

任意步骤失败时，流水线返回失败状态，不应合并对应 Pull Request。

## 4. 本地执行

在仓库根目录运行：

```powershell
python -m compileall -q scripts poc bridge
python .\scripts\Validate-JsonFiles.py
python .\scripts\Validate-CoreContracts.py
python .\scripts\Verify-Fixtures.py
python -m unittest -v bridge.tests.test_python_bridge
npx --yes --package typescript@5.4.5 tsc .\ui-mock\entry\src\main\ets\model\Refinement.ts --target ES2020 --module commonjs --strict --skipLibCheck --outDir .\ui-mock\build\test-model
node .\tests\ui-mock.test.cjs
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Sync-UiMockFixtures.ps1 -Check
```

原有 PowerShell 完整性检查仍可使用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Verify-Fixtures.ps1
```

C 的文件服务门禁可在 macOS/Linux 单独复现（需 C++ 编译器、Node.js 和 npm）：

```sh
c++ -std=c++17 -Wall -Wextra -Werror tests/file-exporter-native.test.cpp -o /tmp/gsas-exclusive-test
/tmp/gsas-exclusive-test
npm install --prefix /tmp/gsas-file-tests --no-package-lock --no-save typescript@5.4.5
GSAS_TYPESCRIPT_PATH=/tmp/gsas-file-tests/node_modules/typescript node --test tests/file-service-host.test.cjs
```

这些测试不替代 ArkTS 编译、系统选择器交互或真机验收。C01/C02 的平台证据及设备跳过项见 [成员 C 验证记录](MEMBER_C_VALIDATION.md)。

运行时/发布工具的标准库测试：

```sh
python3 -m unittest discover -s tests -p 'test_release_tools.py' -v
python3 -m unittest discover -s tests -p 'test_runtime_manifest_tool.py' -v
```

B 的设备侧门面与装配器宿主测试（同需 typescript@5.4.5 与上面的 C++ 编排原生测试命令）：

```sh
GSAS_TYPESCRIPT_PATH=/tmp/gsas-file-tests/node_modules/typescript node --test tests/runtime-installer-host.test.cjs
GSAS_TYPESCRIPT_PATH=/tmp/gsas-file-tests/node_modules/typescript node --test tests/core-bridge-host.test.cjs
```

真实 ArkTS 类型检查与 `arm64-v8a` 原生编译不进云端 CI，本机使用 DevEco 自带
hvigor 执行，见 [PHASE3_NAPI_CORE](PHASE3_NAPI_CORE.md) §3。

## 5. GitHub 启用要求

1. 将工作流文件提交并推送至 GitHub 仓库默认分支。
2. 在仓库的 Actions 页面确认 `Repository verification` 工作流已自动运行。
3. 也可在工作流页面选择 `main`，通过“Run workflow”手动执行。
4. 建议为 `main` 配置分支保护，并将 `Repository verification` 设置为合并前必须通过的状态检查。

## 6. 当前不纳入云端 CI 的项目

下列检查依赖 HarmonyOS PC 真机、签名环境、HarmonyOS SDK 或已经构建的科学计算运行时，暂不在公共 Runner 上执行：

- HarmonyOS aarch64 C/C++/Fortran 原生扩展构建。
- HAP 构建、签名、安装、冷启动和卸载。
- 嵌入式 CPython、NumPy、SciPy、PyCifRW 的应用沙箱加载。
- GSAS-II PbSO4 五阶段真机精修及数值对比。

这些项目继续作为发布候选版本的真机集成验收门禁。后续如配置包含 SDK、签名和设备连接能力的自托管 Runner，可另建 `device-ci.yml`，不得将签名密钥直接写入仓库或流水线文件。
