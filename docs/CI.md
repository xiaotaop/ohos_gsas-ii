# GitCode 持续集成说明

## 1. 目标

本仓库使用 GitCode AtomGit Action 对无需 HarmonyOS PC 真机和专用 SDK 的内容进行持续验证。工作流文件位于：

```text
.gitcode/workflows/ci.yml
```

流水线使用 GitCode 官方托管的 Ubuntu x64 Runner 和 Python 3.12，不需要配置访问令牌或其他 Secret。

## 2. 触发条件

- 任意分支发生 push 时自动运行。
- 向 `main` 分支创建或更新 Pull Request 时自动运行。
- 可在 GitCode Actions 页面通过 `workflow_dispatch` 手动运行。

## 3. 质量门禁

流水线依次执行：

1. Python 文件语法编译检查。
2. `contracts/` 和 `poc/results/` 中全部 JSON 文件的编码及语法检查。
3. 核心接口 Schema、请求示例及成功、失败、取消事件序列检查。
4. 五个 PbSO4 测试样例的 SHA-256 完整性检查。

任意步骤失败时，流水线返回失败状态，不应合并对应 Pull Request。

## 4. 本地执行

在仓库根目录运行：

```powershell
python -m compileall -q scripts poc
python .\scripts\Validate-JsonFiles.py
python .\scripts\Validate-CoreContracts.py
python .\scripts\Verify-Fixtures.py
```

原有 PowerShell 完整性检查仍可使用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Verify-Fixtures.ps1
```

## 5. GitCode 启用要求

1. 将工作流文件提交并推送至 GitCode 仓库。
2. 在仓库的 Actions/流水线页面确认 AtomGit Action 已启用。
3. 首次可使用“Run workflow”手动执行，也可通过 push 自动触发。
4. 建议在分支保护中启用“流水线成功后才允许合并”。

## 6. 当前不纳入云端 CI 的项目

下列检查依赖 HarmonyOS PC 真机、签名环境、HarmonyOS SDK 或已经构建的科学计算运行时，暂不在公共 Runner 上执行：

- HarmonyOS aarch64 C/C++/Fortran 原生扩展构建。
- HAP 构建、签名、安装、冷启动和卸载。
- 嵌入式 CPython、NumPy、SciPy、PyCifRW 的应用沙箱加载。
- GSAS-II PbSO4 五阶段真机精修及数值对比。

这些项目继续作为发布候选版本的真机集成验收门禁。后续如配置包含 SDK、签名和设备连接能力的自托管 Runner，可另建 `device-ci.yml`，不得将签名密钥直接写入仓库或流水线文件。
