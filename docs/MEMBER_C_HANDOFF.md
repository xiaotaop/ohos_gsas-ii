# 成员 C：正式工程与文件服务交付

适用范围：成员 C 工作计划的阶段 1、2（C01/C02），不是项目第一、第二阶段的计算 PoC。开发基线为 `12db7e7`，实现分支 `release/stages-1-2`。

## 1. 工程入口与范围

正式应用源码放在 `app/`，entry 模块、入口 `EntryAbility`、首页 `pages/Index`。现有 `ui-mock/` 原样保留，A 后续可把真实计算页面接入 app 的服务。当前首页提供真实文件管理和隔离的设备自测，不模拟精修、不生成假 GPX。

开发配置：

| 配置 | 当前实现 |
|---|---|
| 应用显示名 | GSAS PC · 开发版 |
| bundleName | com.xiaotaop.gsaspc |
| 版本 | 0.1.0 / versionCode 1 |
| 设备 | 2in1 |
| 最低/目标 API | 20 / 24，沿用 M1 版本范围 |
| 本机工具链 | DevEco Studio 26.0.0.821，编译 SDK API 26，DevEco CLI 1.3.5 |
| 构建模式 | debug、release |

名称和包名是开发接入配置，上架名称尚未确定。API 26 编译不表示最低兼容版本升级；API 20/24 真机兼容仍待验收。

跨成员方案在此给出可运行实现，**不是新增团队批准记录**。冻结 CORE_API、请求/事件 Schema 和原始示例未修改。组长仍需确认 A01～A07 中的工程/角色/错误结构/产物交接选择，以及 B03 的日志可发现方式。

## 2. 构建与运行

Hvigor 不接受当前 SeaDrive 中文路径。`scripts/Build-App.py` 每次将 app 源码复制到新的英文临时目录，通过 DevEco CLI 检查/构建；输出目录会打印。源码与 Git 留在原目录，依赖与构建缓存不进仓库。

在仓库根目录运行：

```sh
python3 scripts/Build-App.py --check
python3 scripts/Build-App.py --build-mode release
devecocli emulator start 'MateBook Pro 1'
python3 scripts/Build-App.py --check --device 'MateBook Pro 1'
```

首次启动模拟器时可能锁屏，需要解锁后再运行。调试过程中可以在英文构建目录重新调用 `devecocli run --module entry --device 'MateBook Pro 1' --skip-build`。

本机 PC 模拟器允许安装未签名 HAP；构建成功不代表真机签名已完成。调试签名由实际负责人登录华为账号后在英文工程目录使用 `signature generate` 配置。正式发布签名、Python/.so 部署、SBOM 最终审计属于后续阶段。

## 3. ArkTS 语法与官方依据

业务实现全部使用 `.ets`，不是把 TypeScript 隐藏到 `.ts` 以绕过 ArkTS 检查。采用显式接口/类、初始化属性、具体泛型、Map/数组和 Promise；没有 any/unknown、对象解构或动态属性索引。错误只抛出 Error 派生类，catch 内使用明确的 Error/BusinessError 转换。JSON.parse 后仍检查版本、ID、名称、大小、角色和哈希，类型断言不代替运行时校验。

通过 `devecocli docs read` 核对的官方文档：

- `开发指南/学习ArkTS语言/从TypeScript到ArkTS的适配指导/从TypeScript到ArkTS的适配规则/typescript-to-arkts-migration-guide`
- `开发指南/学习ArkTS语言/从TypeScript到ArkTS的适配指导/ArkTS语法适配背景/arkts-migration-background`
- `API参考/Core_File_Kit_文件基础服务/ArkTS_API/ohos_file_picker_选择器_/js-apis-file-picker`

文件 API 的签名、支持版本和 URI 处理也与本机 SDK 声明核对。真实 ArkTS 检查与 HAP 编译作为语法验收，普通 tsc 不代替它们。

## 4. A 的接入方式

公共类型：`app/entry/src/main/ets/contracts/Files.ets`。

```ts
const files = await AppServices.files(context);
const selection = new FilePickerService(context, files);
const imported = await selection.selectAndImport(FileRole.POWDER_DATA);
// imported 为 undefined 表示用户取消；有值才更新请求的 dataFileId。
```

FileLibrary 只提供 CORE_API 的四个文件方法以及 listFiles；页面不取得沙箱绝对路径、CoreConfig 或 native 解析能力。服务由应用持有，页面重建复用同一实例与操作队列。

| 方法 | 行为 |
|---|---|
| importFile(uri, role) | 复制到沙箱后计算 size/SHA-256，完整持久化后返回 AppFile |
| getFile(fileId) | 从索引解析，校验普通文件及哈希；未知 ID 返回 FILE_NOT_FOUND |
| deleteFile(fileId) | 只删除应用副本；活动任务引用时返回 BUSY；持久化删除标记用于中断恢复 |
| exportFile(fileId, destinationUri) | 沙箱目标原子排他创建；系统保存 URI 写入选择器预创建的授权空槽，拒绝仍有内容的目标 |
| listFiles() | 返回元数据副本；实际读/导出时仍校验哈希 |
| selectAndImport(role) | 打开系统文件选择器；取消返回 undefined，失败拒绝 Promise |
| selectAndExport(fileId) | 打开系统保存选择器；取消返回 false，完成真实写入才返回 true |

角色为当前 C 实现选择：`powder-data`、`instrument-parameters`、`phase`，产物为 `project`、`result`、`log`。这些角色不等同于 histogram 的 xray/neutron，后者仍由精修请求选择。文件后缀提示不表示核心已经支持全部格式；真正可计算范围由 B 的 recipe 决定。

错误为 FileServiceError（Error 派生类），含 code/message/retryable；页面使用 describeFileError，避免把平台原始路径/URI/错误堆栈呈现给用户。

## 5. B 的接入方式

由应用启动/核心门面调用 `AppServices.nativeFiles(context)`，取得 SandboxFileService。普通页面使用上一节的 FileLibrary。

| 内部接口 | 用途 |
|---|---|
| getCoreConfig() | runtime/jobs/outputs 根目录和单任务配置，均从实际 context.filesDir 推导 |
| resolveInputFile(fileId) | 校验登记、路径和哈希后返回输入绝对路径；不接受输出 ID 或原始 URI |
| beginJob(jobId, fileIds) | 验证输入并持久化引用；创建 input/work/logs 与 output 目录 |
| registerOutput(jobId, fileId, displayName, kind) | 登记已经写完的 outputs/jobId/name 文件；不接受任意绝对路径 |
| finishJob(jobId) | 终态后释放引用、清理 input/work；保留 logs 和 outputs |
| listInterruptedJobs() | 获取启动时从旧租约识别的任务，供 B 的快照层标记 PROCESS_INTERRUPTED；不恢复计算 |

建议调用顺序：

1. FileService 初始化完成，B 初始化 CoreService，随后向 A 暴露就绪状态。
2. 请求校验后，在 B 的单任务门内 beginJob 锁定全部输入 fileId。
3. 专用线程调用现有 Python Bridge。imports 布局与 `bridge/files.py` 一致；输入目录中只放一个数据文件，没有元数据。
4. 真实输出写出后，按事件 artifacts 逐项 registerOutput。B 现有 `file_out_*` ID 可以直接使用。
5. **完成产物登记后**再向页面交付 completed 结果，保证界面拿到的 fileId 可查询/导出。
6. 所有终态（包括失败、取消和调度异常）释放文件租约。失败/取消要先把脱敏用户日志写入 outputs，再登记为 log。
7. 重启时读取 interrupted job IDs，B 标记 PROCESS_INTERRUPTED，再 finishJob；C 已清理旧 input/work，原 imports、logs、outputs 保留。

本次没有实现 B 的计算 N-API、CoreService 或计算状态机。B03 的失败/取消日志如何进入快照/事件，仍需组长批准；C 的登记/导出入口已可使用。私有 traceback 不应登记为用户可导出日志。

## 6. 沙箱布局与恢复

```text
context.filesDir/
  imports/<fileId>/<原始文件名>
  runtime/                         # 为下一阶段预留，无 Python 载荷
  jobs/<jobId>/input|work|logs/
  outputs/<jobId>/<真实产物>
  metadata/files/<fileId>.json
  metadata/leases/<jobId>.json
  staging/<fileId>/<导入中的文件>
```

索引不存 URI 或绝对路径。所有应用内路径由经过正则校验的 ID、单段文件名及固定目录推导；逐层 lstat 拒绝符号链接。输出路径与 fileId 为一对一登记，重复提交同一登记保持幂等；不同 ID 不允许登记同一文件。复制、哈希和持久化调用异步平台 API，同一服务实例串行处理文件操作。

元数据通过临时文件、fsync、rename 发布。导入中断留下的 staging 或无索引 imports 副本在启动时清理；输出尚未登记时保留，避免误删核心已经生成的结果。删除先保存意图，重启可完成未结束的删除。索引损坏时初始化失败并可重试，不静默删除全部用户文件库。

导出区分两种平台能力：沙箱目标由 `libgsas_fileio.so` 使用公开 FileURI 转换 API 和 `O_EXCL | O_NOFOLLOW` 原子创建，避免已有空文件或外部并发创建被覆盖；系统 `file://docs/` URI 必须来自 DocumentViewPicker.save，由 FileIO 的 URI 接口写入。SDK 的 DocumentSaveOptions 默认预创建空文件（API23 起还可配置 autoCreateEmptyFile），因此该授权空槽不能按外部已有文件拒绝。系统选择器负责同名确认，应用还会拒绝仍有内容的目标。本机已验证同名时显示“文件已存在，要替换它？”，选择取消后原字节不变。调用方不得把导入 URI 当作保存授权槽使用。

原生模块只负责文件创建，不包含 CPython、科学计算桥接或任何测试符号链接后门。它使用的 SDK libc++_shared.so 随 HAP 打包；对应许可证位于 rawfile/licenses，见组件清单。

## 7. 验证方法与限制

点击首页“运行文件服务验证”，在独立 cache 目录执行真实平台文件测试，结束后删除测试目录，不触碰用户文件库。测试覆盖五份 fixture 哈希、单文件输入布局、持久化恢复、未知 ID/路径逃逸、格式拒绝、并发导入、任务引用和中断恢复、真实导出与不覆盖、真实 JSON 产物登记、内容变化、删除恢复和残留清理。

当前模拟器的 ArkTS symlink 创建返回 13900012；hdc 对应用私有副本的修改也受权限限制。SDK 声明指出 API 11 起禁止第三方应用创建符号链接；原生 POSIX 夹具也被设备权限拒绝。因此设备用例显示 SKIP，不能称作设备动态拒绝通过。`tests/file-service-host.test.cjs` 在宿主真实文件系统中运行实际服务源码，补验符号链接防护；生产模块没有夹具创建接口。

完整执行记录、最终 HAP 哈希与截图见 `MEMBER_C_VALIDATION.md`。当前产物是文件服务开发 HAP；模拟器验收不替代真机 GUI、真实精修、签名发布、离线运行时验收。
