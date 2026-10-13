// Source-guided ArkUI port of GSASII/GSASIIdataGUI.py, commit 2b4aba1bc44de63a3da9d4495944c3b99e389399.
// Upstream: Copyright 2010, UChicago Argonne, LLC. All rights reserved. See repository LICENSE and NOTICE.
// Translation/modifications: noth1ng, ohos_gsas-ii (Member A), 2026-10-13.
// wx widgets/layout/events are translated below; Python object access is replaced by CORE_API v1.0.
// This is an explicit M1 subset, not a port of every upstream menu, editor or scientific operation.
import { util } from '@kit.ArkTS';
import {
  CoreEvent, CoreService, MockCoreService, MockData, RefinementRequest, RefinementView,
  StageResult, Artifact, isActive, newMockRequest, receiveEvent, stageLabel
} from '../model/Refinement';

interface DemoChoice { id: string; label: string; description: string; }
interface InputLabel { name: string; role: string; }
interface ReadOnlyValue { label: string; value: string; }

@Entry
@Component
struct Index {
  @State private view: RefinementView = new RefinementView();
  @State private scenario: string = 'success';
  @State private ready: boolean = false;
  @State private cycleCount: string = '—';
  @State private cancelRequested: boolean = false;
  @State private wide: boolean = true;
  @State private notice: string = '';
  @State private selectedItem: string = 'Controls';
  @State private showProgress: boolean = false;
  @State private showPlots: boolean = false;
  @State private phaseExpanded: boolean = true;
  @State private xrayExpanded: boolean = true;
  @State private neutronExpanded: boolean = false;
  private mock?: MockCoreService;
  private core?: CoreService;
  private data?: MockData;
  private unsubscribe?: () => void;
  private mounted: boolean = false;
  private choices: DemoChoice[] = [
    { id: 'success', label: '成功', description: '五阶段结果与产物摘要' },
    { id: 'failed', label: '失败', description: '仪器参数错误与修正提示' },
    { id: 'cancelled', label: '取消', description: '请求取消 → 等待 → 已取消' }
  ];
  private inputs: InputLabel[] = [
    { name: 'PBSO4.XRA', role: 'X 射线粉末数据' },
    { name: 'INST_XRY.PRM', role: 'X 射线仪器参数' },
    { name: 'PBSO4.CWN', role: '中子粉末数据' },
    { name: 'inst_d1a.prm', role: '中子仪器参数' },
    { name: 'PbSO4-Wyckoff.cif', role: '晶体相文件' }
  ];

  aboutToAppear(): void {
    this.mounted = true;
    this.loadDemo();
  }

  aboutToDisappear(): void {
    this.mounted = false;
    if (this.unsubscribe) { this.unsubscribe(); }
    if (this.mock) { this.mock.dispose(); }
  }

  private async readExample(name: string): Promise<string> {
    try {
      const context = this.getUIContext().getHostContext();
      if (!context) { throw new Error('CONTEXT_UNAVAILABLE'); }
      const bytes = await context.resourceManager.getRawFileContent(name);
      return util.TextDecoder.create('utf-8', { ignoreBOM: true }).decodeToString(bytes);
    } catch {
      throw new Error('MOCK_RESOURCE_UNAVAILABLE');
    }
  }

  private async loadDemo(): Promise<void> {
    try {
      const request = JSON.parse(await this.readExample('refinement-request.json')) as RefinementRequest;
      const success = JSON.parse(await this.readExample('core-events-success.json')) as CoreEvent[];
      const failed = JSON.parse(await this.readExample('core-events-failed.json')) as CoreEvent[];
      const cancelled = JSON.parse(await this.readExample('core-events-cancelled.json')) as CoreEvent[];
      if (!this.mounted) { return; }
      this.data = { request, success, failed, cancelled };
      this.cycleCount = request.options.cycleCount.toString();
      this.mock = new MockCoreService(this.data);
      this.core = this.mock;
      // Subscribe before startRefinement, including synchronous accepted events.
      this.unsubscribe = this.core.onEvent((event: CoreEvent) => {
        this.view = receiveEvent(this.view, event);
        if (!isActive(this.view.state)) { this.cancelRequested = false; }
      });
      this.ready = true;
    } catch {
      this.notice = '演示数据加载失败，请检查安装包是否包含完整示例后重新打开。';
    }
  }

  private async startDemo(): Promise<void> {
    if (!this.core || !this.mock || !this.data || isActive(this.view.state)) { return; }
    this.notice = '';
    this.cancelRequested = false;
    this.showProgress = true;
    const request = newMockRequest(this.data.request);
    const pending = new RefinementView();
    pending.jobId = request.jobId;
    pending.state = 'queued';
    pending.message = '正在提交任务';
    this.view = pending;
    try {
      this.mock.setScenario(this.scenario);
      await this.core.startRefinement(request);
      // Do not overwrite events already received while this Promise was pending.
    } catch {
      const failed = new RefinementView();
      failed.jobId = request.jobId;
      failed.state = 'failed';
      failed.message = '任务未能启动，请稍后重试。';
      failed.error = { code: 'INTERNAL_ERROR', message: failed.message, retryable: true };
      this.view = failed;
    }
  }

  private async cancel(): Promise<void> {
    if (!this.core || !isActive(this.view.state) || this.cancelRequested) { return; }
    this.cancelRequested = true;
    try {
      await this.core.cancelJob(this.view.jobId);
      // CancelAck is not completion. Keep waiting for a terminal CoreEvent.
    } catch {
      this.cancelRequested = false;
      if (isActive(this.view.state)) { this.notice = '取消请求未能送达，请重试或等待任务结束。'; }
    }
  }

  private reset(): void {
    this.view = new RefinementView();
    this.cancelRequested = false;
    this.notice = '';
    this.showProgress = false;
  }

  private statusTitle(): string {
    if (this.cancelRequested && isActive(this.view.state)) { return '正在取消'; }
    switch (this.view.state) {
      case 'succeeded': return '精修完成';
      case 'failed': return '任务未完成';
      case 'cancelled': return '任务已取消';
      case 'queued': return '任务已接受';
      case 'validating': return '正在检查输入';
      case 'saving': return '正在保存结果';
      case 'running': return '精修进行中';
      case 'cancelling': return '正在取消';
      default: return '准备开始';
    }
  }

  private statusColor(): string {
    if (this.view.state === 'failed') { return '#A93632'; }
    if (this.view.state === 'cancelled' || this.cancelRequested) { return '#896018'; }
    return '#275E90';
  }

  // GSASIIdataGUI.FillMainMenu and _Add_*MenuItems: preserve order and command names.
  @Builder
  fileMenu() {
    Menu() {
      MenuItem({ content: 'Open project...', labelInfo: 'Ctrl+O' }).enabled(false)
      MenuItem({ content: 'Save project', labelInfo: 'Ctrl+S' }).enabled(false)
      MenuItem({ content: 'Save project as...' }).enabled(false)
      MenuItem({ content: 'New project' }).enabled(false)
    }
  }

  @Builder
  dataMenu() {
    Menu() {
      MenuItem({ content: 'Add new phase' }).enabled(false)
      MenuItem({ content: 'Delete phase entries' }).enabled(false)
      MenuItem({ content: 'Rename data entry' }).enabled(false)
      MenuItem({ content: 'Delete data entries' }).enabled(false)
    }
  }

  @Builder
  calculateMenu() {
    Menu() {
      MenuItem({ content: 'View LS parms', labelInfo: 'Ctrl+L' }).enabled(false)
      MenuItem({ content: 'Refine', labelInfo: 'Ctrl+R' })
        .enabled(this.ready && !isActive(this.view.state))
        .onClick(() => this.startDemo())
      MenuItem({ content: 'Compute partials' }).enabled(false)
    }
  }

  @Builder
  importMenu() {
    Menu() {
      MenuItem({ content: 'Phase' }).enabled(false)
      MenuItem({ content: 'Powder Data' }).enabled(false)
      MenuItem({ content: 'Image' }).enabled(false)
      MenuItem({ content: 'Structure Factor' }).enabled(false)
    }
  }

  @Builder
  exportMenu() {
    Menu() {
      MenuItem({ content: 'Project / GPX' }).enabled(false)
      MenuItem({ content: 'Result / JSON' }).enabled(false)
      MenuItem({ content: 'Powder Data' }).enabled(false)
    }
  }

  @Builder
  helpMenu() {
    Menu() {
      MenuItem({ content: 'About GSAS-II / M1' }).onClick(() => { this.selectedItem = 'About'; })
    }
  }

  @Builder
  mainMenu() {
    Scroll() {
      Row() {
        Button('File', { type: ButtonType.Normal }).bindMenu(this.fileMenu)
          .fontColor('#202020').backgroundColor('#F0F0F0').height(30).fontSize(14)
        Button('Data', { type: ButtonType.Normal }).bindMenu(this.dataMenu)
          .fontColor('#202020').backgroundColor('#F0F0F0').height(30).fontSize(14)
        Button('Calculate', { type: ButtonType.Normal }).bindMenu(this.calculateMenu)
          .fontColor('#202020').backgroundColor('#F0F0F0').height(30).fontSize(14)
        Button('Import', { type: ButtonType.Normal }).bindMenu(this.importMenu)
          .fontColor('#202020').backgroundColor('#F0F0F0').height(30).fontSize(14)
        Button('Export', { type: ButtonType.Normal }).bindMenu(this.exportMenu)
          .fontColor('#202020').backgroundColor('#F0F0F0').height(30).fontSize(14)
        Text('|').fontColor('#999999').margin({ left: 6, right: 6 })
        Button('Help', { type: ButtonType.Normal }).bindMenu(this.helpMenu)
          .fontColor('#202020').backgroundColor('#F0F0F0').height(30).fontSize(14)
      }
    }.scrollable(ScrollDirection.Horizontal).align(Alignment.TopStart).width('100%').backgroundColor('#F0F0F0')
  }

  @Builder
  treeItem(label: string, id: string, depth: number, available: boolean) {
    Button({ type: ButtonType.Normal }) {
      Text(label).fontSize(14).fontColor(available ? '#202020' : '#888888')
        .width('100%').textAlign(TextAlign.Start).maxLines(1).textOverflow({ overflow: TextOverflow.Ellipsis })
    }.width('100%').height(29).padding({ left: 12 + depth * 18, right: 6 })
      .backgroundColor(this.selectedItem === id ? '#CDE8FF' : Color.White)
      .enabled(available).onClick(() => { this.selectedItem = id; this.showPlots = false; })
  }

  // CheckNotebook creates these six common nodes in this exact order.
  // OnImportPowder creates PWDR nodes and their children; OnImportPhase creates Phases.
  @Builder
  dataTree() {
    Column() {
      Text('GSAS-II data tree').fontSize(13).fontColor('#444444').width('100%')
        .padding(8).backgroundColor('#E6E6E6')
      Scroll() {
        Column() {
          this.treeItem('▾  PbSO4 (M1 mock)', 'Project', 0, true)
          this.treeItem('Notebook', 'Notebook', 1, true)
          this.treeItem('Controls', 'Controls', 1, true)
          this.treeItem('Covariance', 'Covariance', 1, true)
          this.treeItem('Constraints', 'Constraints', 1, false)
          this.treeItem('Restraints', 'Restraints', 1, false)
          this.treeItem('Rigid bodies', 'Rigid bodies', 1, false)
          Button((this.phaseExpanded ? '▾  ' : '▸  ') + 'Phases', { type: ButtonType.Normal })
            .width('100%').height(29).fontSize(14).fontColor('#202020').backgroundColor(Color.White)
            .align(Alignment.Start).padding({ left: 30 })
            .onClick(() => { this.phaseExpanded = !this.phaseExpanded; })
          if (this.phaseExpanded) { this.treeItem('PbSO4', 'Phase', 2, true) }
          Button((this.xrayExpanded ? '▾  ' : '▸  ') + 'PWDR PBSO4.XRA', { type: ButtonType.Normal })
            .width('100%').height(29).fontSize(14).fontColor('#202020')
            .backgroundColor(this.selectedItem === 'xray' ? '#CDE8FF' : Color.White)
            .align(Alignment.Start).padding({ left: 30 })
            .onClick(() => { this.selectedItem = 'xray'; this.showPlots = false; this.xrayExpanded = !this.xrayExpanded; })
          if (this.xrayExpanded) {
            this.treeItem('Comments', 'xrayComments', 2, false)
            this.treeItem('Limits', 'xrayLimits', 2, false)
            this.treeItem('Background', 'xrayBackground', 2, false)
            this.treeItem('Instrument Parameters', 'xrayInstrument', 2, true)
            this.treeItem('Sample Parameters', 'xraySample', 2, false)
            this.treeItem('Peak List', 'xrayPeaks', 2, false)
            this.treeItem('Index Peak List', 'xrayIndex', 2, false)
            this.treeItem('Unit Cells List', 'xrayCells', 2, false)
            this.treeItem('Reflection Lists', 'xrayReflections', 2, false)
          }
          Button((this.neutronExpanded ? '▾  ' : '▸  ') + 'PWDR PBSO4.CWN', { type: ButtonType.Normal })
            .width('100%').height(29).fontSize(14).fontColor('#202020')
            .backgroundColor(this.selectedItem === 'neutron' ? '#CDE8FF' : Color.White)
            .align(Alignment.Start).padding({ left: 30 })
            .onClick(() => { this.selectedItem = 'neutron'; this.showPlots = false; this.neutronExpanded = !this.neutronExpanded; })
          if (this.neutronExpanded) {
            this.treeItem('Comments', 'neutronComments', 2, false)
            this.treeItem('Limits', 'neutronLimits', 2, false)
            this.treeItem('Background', 'neutronBackground', 2, false)
            this.treeItem('Instrument Parameters', 'neutronInstrument', 2, true)
            this.treeItem('Sample Parameters', 'neutronSample', 2, false)
            this.treeItem('Peak List', 'neutronPeaks', 2, false)
            this.treeItem('Index Peak List', 'neutronIndex', 2, false)
            this.treeItem('Unit Cells List', 'neutronCells', 2, false)
            this.treeItem('Reflection Lists', 'neutronReflections', 2, false)
          }
        }.width('100%').alignItems(HorizontalAlign.Start)
      }.width('100%').height(this.wide ? 530 : 215).align(Alignment.TopStart)
    }.width('100%').border({ width: 1, color: '#A0A0A0' }).backgroundColor(Color.White)
  }

  @Builder
  readOnlyField($$: ReadOnlyValue) {
    Row({ space: 12 }) {
      Text($$.label).fontSize(14).width(135).fontColor('#202020')
      Text($$.value).fontSize(14).fontColor('#404040').padding(6).layoutWeight(1)
        .backgroundColor('#F7F7F7').border({ width: 1, color: '#B8B8B8' })
    }.width('100%')
  }

  // UpdateControls: translate the label/control grid. Only max cyc is in CORE_API v1.0.
  // The other upstream controls stay unavailable rather than acquiring invented values.
  @Builder
  controlsPage() {
    Column({ space: 12 }) {
      Text('Least squares controls').fontSize(18).fontWeight(FontWeight.Bold)
      this.readOnlyField({ label: 'Max cycles:', value: this.cycleCount })
      this.readOnlyField({ label: 'Refinement type:', value: '固定 recipe 管理；M1 不开放选择' })
      this.readOnlyField({ label: 'Min delta-M/M:', value: '当前接口未提供' })
      this.readOnlyField({ label: 'Recipe:', value: 'powder-five-stage-v1' })
      Text('固定流程：初始拟合 → 比例与背景 → 晶胞 → 微应变/位移/原子 → 择优取向')
        .fontSize(13).fontColor('#505050').lineHeight(20)
      Text('Max cycles 来自契约示例，当前只读。通过 Calculate → Refine 或 Ctrl+R 启动模拟精修。')
        .fontSize(13).fontColor('#505050').lineHeight(20)
      Button('Refine (mock)', { type: ButtonType.Normal }).fontSize(14).height(34)
        .backgroundColor('#E1E1E1').fontColor('#202020').border({ width: 1, color: '#999999' })
        .enabled(this.ready && !isActive(this.view.state)).onClick(() => this.startDemo())
      if (this.view.result) { this.resultPage() }
    }.width('100%').alignItems(HorizontalAlign.Start)
  }

  @Builder
  resultPage() {
    if (this.view.result) {
      Column({ space: 12 }) {
        Divider().color('#B0B0B0')
        Text('Refinement results — M1 示例').fontSize(17).fontWeight(FontWeight.Bold)
        Text('示例耗时 ' + this.view.result.elapsedSeconds.toFixed(3) + ' s；非此次回放计时')
          .fontSize(13).fontColor('#505050')
        Row() {
          Text('Stage').layoutWeight(1).fontSize(13)
          Text('X-ray Rwp %').width(100).textAlign(TextAlign.End).fontSize(13)
          Text('Neutron Rwp %').width(108).textAlign(TextAlign.End).fontSize(13)
        }.width('100%').padding(6).backgroundColor('#E1E1E1')
        ForEach(this.view.result.stages, (stage: StageResult) => {
          Row({ space: 4 }) {
            Text(stageLabel(stage.name)).layoutWeight(1).fontSize(13)
            Text(stage.rwpByHistogram['xray'].toFixed(4)).width(100).textAlign(TextAlign.End).fontSize(13)
            Text(stage.rwpByHistogram['neutron'].toFixed(4)).width(108).textAlign(TextAlign.End).fontSize(13)
          }.width('100%').padding({ left: 6, right: 6, top: 5, bottom: 5 })
        }, (stage: StageResult) => stage.name)
        if (this.view.result.validation?.performed) {
          Text(this.view.result.validation.passed ? '示例基线校验：通过' : '示例基线校验：未通过')
            .fontSize(14).fontColor(this.view.result.validation.passed ? '#246329' : '#A12622')
        }
        Text('Output files').fontSize(15).fontWeight(FontWeight.Bold)
        ForEach(this.view.result.artifacts, (artifact: Artifact) => {
          Row({ space: 8 }) {
            Text(artifact.displayName).fontSize(14).layoutWeight(1)
            Button('Export', { type: ButtonType.Normal }).enabled(false).height(28).fontSize(12)
          }.width('100%')
        }, (artifact: Artifact) => artifact.fileId)
        Text('仅显示契约中的产物名称；没有真实文件可导出。').fontSize(12).fontColor('#606060')
      }.alignItems(HorizontalAlign.Start).width('100%')
    }
  }

  @Builder
  dataPage() {
    Column({ space: 14 }) {
      if (this.selectedItem === 'Controls') {
        this.controlsPage()
      } else if (this.selectedItem === 'Notebook') {
        Text('Notebook').fontSize(18).fontWeight(FontWeight.Bold)
        Text('当前显示 CoreEvent 任务消息；尚未接入原项目的可编辑 Notebook 或 Python 日志。')
          .fontSize(13).fontColor('#606060').lineHeight(20)
        if (this.view.history.length === 0) { Text('尚无任务记录。').fontSize(14) }
        ForEach(this.view.history, (message: string, index: number) => {
          Text((index + 1).toString().padStart(2, '0') + '  ' + message).fontSize(13).lineHeight(21)
        }, (message: string, index: number) => index.toString())
      } else if (this.selectedItem === 'Covariance') {
        Text('Covariance').fontSize(18).fontWeight(FontWeight.Bold)
        Text('当前契约未提供协方差矩阵、GOF、Nobs 或 Nvar；此数据页待核心接口扩展。')
          .fontSize(14).lineHeight(22)
        Text('五阶段 Rwp 摘要位于 Controls 页，不作为协方差结果。').fontSize(13).fontColor('#606060')
      } else if (this.selectedItem === 'Phase') {
        Row({ space: 14 }) {
          Text('General').fontSize(14).fontWeight(FontWeight.Bold)
          Text('Data').fontSize(14).fontColor('#888888')
          Text('Atoms').fontSize(14).fontColor('#888888')
          Text('Draw Options').fontSize(14).fontColor('#888888')
        }.padding(8).width('100%').backgroundColor('#E3E3E3')
        this.readOnlyField({ label: 'Phase name:', value: 'PbSO4' })
        this.readOnlyField({ label: 'Source CIF:', value: 'PbSO4-Wyckoff.cif' })
        Text('晶胞、原子及结构绘图尚未由接口提供；M1 不解析或编辑 CIF。').fontSize(13).lineHeight(20)
      } else if (this.selectedItem === 'About') {
        Text('GSAS-II / HarmonyOS M1').fontSize(18).fontWeight(FontWeight.Bold)
        Text('按 GSASIIdataGUI.py 的菜单、项目树、分栏、Controls 和 Refine 事件入口移植的 ArkUI 子集。')
          .fontSize(14).lineHeight(22)
        Text('上游提交：2b4aba1bc44de63a3da9d4495944c3b99e389399').fontSize(12)
        Text('Copyright 2010, UChicago Argonne, LLC. All rights reserved.').fontSize(12)
        Text('This product includes software produced by UChicago Argonne, LLC under Contract No. DE-AC02-06CH11357 with the Department of Energy.')
          .fontSize(12).lineHeight(18)
        Text('本页面为模拟数据演示，不表示完整 GSAS-II GUI、真实计算或发布版本已经移植。')
          .fontSize(13).lineHeight(20)
      } else if (this.selectedItem === 'Project') {
        Text('PbSO4 — Project files').fontSize(18).fontWeight(FontWeight.Bold)
        ForEach(this.inputs, (file: InputLabel) => { this.readOnlyField({ label: file.role, value: file.name }) },
          (file: InputLabel) => file.name)
        Text('内置示例清单，只读。正式导入、保存和导出等待 FileService。').fontSize(13).lineHeight(20)
      } else {
        Text(this.selectedItem.endsWith('Instrument') ? 'Instrument Parameters' : 'Powder Data')
          .fontSize(18).fontWeight(FontWeight.Bold)
        this.readOnlyField({ label: 'Histogram:', value: this.selectedItem.startsWith('xray') ? 'PWDR PBSO4.XRA' : 'PWDR PBSO4.CWN' })
        this.readOnlyField({ label: 'Data file:', value: this.selectedItem.startsWith('xray') ? 'PBSO4.XRA' : 'PBSO4.CWN' })
        this.readOnlyField({ label: 'Instrument file:', value: this.selectedItem.startsWith('xray') ? 'INST_XRY.PRM' : 'inst_d1a.prm' })
        this.readOnlyField({ label: 'Format:', value: 'GSAS powder' })
        Text('仅显示示例文件关联。仪器参数的具体数值、编辑及重选尚未接入。')
          .fontSize(13).lineHeight(20).fontColor('#606060')
      }
    }.width('100%').padding(18).alignItems(HorizontalAlign.Start)
  }

  // OnRefine -> RefinementProgress: native progress/cancel UI; CoreService replaces Python calls.
  @Builder
  refinementProgress() {
    Column({ space: 14 }) {
      Text('GSAS-II Refinement — M1 mock').fontSize(17).fontWeight(FontWeight.Bold)
      Divider().color('#B0B0B0')
      Text(this.statusTitle()).fontSize(22).fontWeight(FontWeight.Bold).fontColor(this.statusColor())
      Text(this.cancelRequested && isActive(this.view.state) ?
        '取消请求已发出，正在等待当前计算阶段安全结束。' : this.view.message)
        .fontSize(14).lineHeight(22)
      Progress({ value: this.view.percent, total: 100, type: ProgressType.Linear })
        .width('100%').color(this.statusColor()).backgroundColor('#D5D5D5')
      Text((this.view.stage ? stageLabel(this.view.stage) : '等待执行') + '   ' + this.view.percent.toFixed(0) + '%')
        .fontSize(13).fontColor('#505050')
      if (isActive(this.view.state)) {
        if (this.scenario === 'cancelled' && !this.cancelRequested) {
          Text('取消演示正在等待操作，请点击 Cancel。').fontSize(13)
        }
        Button(this.cancelRequested ? '等待取消完成…' : 'Cancel / 取消任务', { type: ButtonType.Normal })
          .enabled(!this.cancelRequested).onClick(() => this.cancel())
          .backgroundColor('#E1E1E1').fontColor('#202020').border({ width: 1, color: '#999999' })
      } else if (this.view.state === 'failed') {
        if (this.view.error) {
          Text(this.view.error.code).fontSize(13).fontColor('#A12622')
          Text(this.view.error.retryable ? '可以重新尝试启动任务。' :
            '请检查仪器参数文件并修正输入。此错误不支持直接重试。').fontSize(14).lineHeight(21)
          if (this.view.error.retryable) {
            Button('Retry / 重试', { type: ButtonType.Normal }).onClick(() => this.startDemo())
          }
        }
        Button('返回并检查输入', { type: ButtonType.Normal }).onClick(() => {
          this.reset(); this.selectedItem = 'xrayInstrument'; this.xrayExpanded = true;
        })
      } else if (this.view.state === 'cancelled') {
        Text('未生成精修结果。').fontSize(14)
        Button('Close / 关闭', { type: ButtonType.Normal }).onClick(() => { this.showProgress = false; })
      } else if (this.view.state === 'succeeded') {
        Text('示例五阶段精修完成。').fontSize(14)
        Button('View results / 查看结果', { type: ButtonType.Normal }).onClick(() => {
          this.showProgress = false; this.selectedItem = 'Controls'; this.showPlots = false;
        })
      }
      if (this.notice) { Text(this.notice).fontSize(13).fontColor('#A12622') }
    }.padding(22).width('100%').alignItems(HorizontalAlign.Start)
  }

  build() {
    Stack({ alignContent: Alignment.Center }) {
      Scroll() {
        Column() {
          Text('GSAS-II — PbSO4  [M1 mock]').fontSize(16).fontWeight(FontWeight.Bold)
            .width('100%').padding(10).backgroundColor('#E2E2E2')
          this.mainMenu()
          Flex({ direction: FlexDirection.Row, wrap: FlexWrap.Wrap, alignItems: ItemAlign.Center }) {
            Text('M1 场景：').fontSize(13).margin({ right: 8 })
            ForEach(this.choices, (choice: DemoChoice) => {
              Button((this.scenario === choice.id ? '● ' : '○ ') + choice.label, { type: ButtonType.Normal })
                .height(30).fontSize(13).margin({ right: 6 }).backgroundColor('#F8F6E7').fontColor('#202020')
                .border({ width: 1, color: this.scenario === choice.id ? '#517FAB' : '#C0C0C0' })
                .onClick(() => { this.reset(); this.scenario = choice.id; })
            }, (choice: DemoChoice) => choice.id)
            Text('模拟数据 · 不运行真实精修').fontSize(12).fontColor('#665E3D').margin(6)
          }.padding(8).width('100%').backgroundColor('#F8F6E7')
          Row({ space: 8 }) {
            Button('Data window', { type: ButtonType.Normal }).height(28).fontSize(13)
              .backgroundColor(this.showPlots ? '#E9E9E9' : '#FFFFFF').fontColor('#202020')
              .onClick(() => { this.showPlots = false; })
            Button('GSASII Plots', { type: ButtonType.Normal }).height(28).fontSize(13)
              .backgroundColor(this.showPlots ? '#FFFFFF' : '#E9E9E9').fontColor('#202020')
              .onClick(() => { this.showPlots = true; })
            Blank()
          }.padding({ left: 5, top: 5, bottom: 5 }).width('100%').backgroundColor('#D5D5D5')
          if (this.showPlots) {
            Column({ space: 16 }) {
              Text('GSASII Plots').fontSize(18).fontWeight(FontWeight.Bold)
              Text('当前没有可绘制的曲线。').fontSize(14)
              Text('M1 契约只提供阶段 Rwp，不包含原始谱线、计算曲线或差值。绘图窗口待接口接入。')
                .fontSize(13).fontColor('#606060').lineHeight(21)
            }.width('100%').height(360).padding(24).alignItems(HorizontalAlign.Start).backgroundColor(Color.White)
          } else {
            // wx.SplitterWindow + G2DataWindow(wx.ScrolledWindow) -> responsive ArkUI panes.
            Flex({ direction: FlexDirection.Row, wrap: FlexWrap.Wrap, alignItems: ItemAlign.Start }) {
              Column() { this.dataTree() }.width(this.wide ? '28%' : '100%')
              Column() {
                Text('GSAS-II data window / ' + this.selectedItem).fontSize(13).fontColor('#444444')
                  .padding(8).width('100%').backgroundColor('#E6E6E6')
                Scroll() { this.dataPage() }.width('100%').height(530).align(Alignment.TopStart)
              }.width(this.wide ? '72%' : '100%').border({ width: 1, color: '#A0A0A0' })
                .backgroundColor('#F0F0F0')
            }.width('100%')
          }
          Row({ space: 10 }) {
            Text(this.statusTitle()).fontSize(13).fontColor(this.statusColor()).layoutWeight(1)
            Button('Refine (Ctrl+R)', { type: ButtonType.Normal }).fontSize(13).height(30)
              .backgroundColor('#E1E1E1').fontColor('#202020').border({ width: 1, color: '#999999' })
              .enabled(this.ready && !isActive(this.view.state)).onClick(() => this.startDemo())
              .keyboardShortcut('r', [ModifierKey.CTRL], () => this.startDemo())
          }.padding(6).width('100%').backgroundColor('#E6E6E6')
          if (this.notice) { Text(this.notice).fontSize(13).fontColor('#A12622').padding(8).width('100%') }
          Text('灰色菜单和节点：尚未移植。M1 未接入真实计算、文件读写与绘图。')
            .fontSize(12).fontColor('#606060').padding(8).width('100%')
        }.width('100%')
      }.width('100%').height('100%').align(Alignment.TopStart).enabled(!this.showProgress)
      if (this.showProgress) {
        Column().width('100%').height('100%').backgroundColor('#66000000')
        Scroll() { this.refinementProgress() }.width('90%').constraintSize({ maxWidth: 600, maxHeight: 570 })
          .backgroundColor('#F0F0F0').border({ width: 1, color: '#666666' }).shadow({ radius: 12, color: '#55000000' })
      }
    }.width('100%').height('100%').backgroundColor('#F0F0F0')
      .onAreaChange((_old: Area, area: Area) => { this.wide = Number(area.width) >= 900; })
  }
}
