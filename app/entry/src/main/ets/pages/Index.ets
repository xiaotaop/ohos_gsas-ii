import { ParameterPanel } from '../components/ParameterPanel';
import { RefinementPanel } from '../components/RefinementPanel';
import { window } from '@kit.ArkUI';
import { common } from '@kit.AbilityKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { preferences } from '@kit.ArkData';
import { AppFile, FileRole, FileServiceError, describeFileError } from '../contracts/Files';
import { AppServices } from '../services/AppServices';
import { FilePickerService } from '../services/FilePickerService';
import { SandboxFileService } from '../services/SandboxFileService';
import { runFileServiceChecks } from '../verification/FileServiceCheck';
import { INPUT_SLOTS, InputSlot, InputSlotInfo, InputBinding, InputSelection, RefinementInputs, draftScope } from '../model/RefinementInputs';
import { CoreService, callError } from '../model/Refinement';

@Extend(Button) function desktopButton() {
  .type(ButtonType.Normal).height(28).fontSize(13).fontColor('#202020')
  .backgroundColor('#EEEEEE').borderRadius(2).border({ width: 1, color: '#B8B8B8' })
  .padding({ left: 10, right: 10 })
}

@Entry
@Component
struct Index {
  @State private files: AppFile[] = [];
  @State private status: string = '正在打开文件库…';
  @State private ready: boolean = false;
  @State private busy: boolean = false;
  @State private taskActive: boolean = false;
  @State private checks: string = '';
  @State private fileQuery: string = '';
  @State private fileRole: string = '';
  private readonly fileRoles: string[] = ['', FileRole.POWDER_DATA, FileRole.INSTRUMENT,
    FileRole.PHASE, FileRole.PROJECT, FileRole.RESULT, FileRole.LOG];
  @State private bindings: InputBinding[] = [];
  @State private prepared: boolean = false;
  @State private panelWidth: number = 1100;
  @State private treeWidth: number = 270;
  private dragStartWidth: number = 270;
  @State private page: string = 'Controls';
  @State private rootOpen: boolean = true;
  @State private phasesOpen: boolean = true;
  @State private xrayOpen: boolean = true;
  @State private neutronOpen: boolean = true;
  private readonly projectNodes: string[] = ['Notebook', 'Controls', 'Covariance', 'Constraints', 'Restraints', 'Rigid bodies'];
  private readonly powderNodes: string[] = ['Comments', 'Limits', 'Background', 'Instrument Parameters',
    'Sample Parameters', 'Peak List', 'Index Peak List', 'Unit Cells List', 'Reflection Lists'];
  private selection: InputSelection = new InputSelection();
  private settings: preferences.Preferences | undefined = undefined;
  private service: SandboxFileService | undefined = undefined;
  private core: CoreService | undefined = undefined;
  @State private coreReady: boolean = false;
  @State private coreOpening: boolean = false;
  @State private coreStatus: string = '等待文件服务就绪。';
  @State private phaseName: string = '';
  @State private cycles: string = '';
  @State private projectName: string = '';
  @State private knownJobId: string = '';
  private context: common.UIAbilityContext | undefined = undefined;
  private mainWindow: window.Window | undefined = undefined;
  private mounted: boolean = false;
  private coreGeneration: number = 0;
  private closeHandler: () => Promise<boolean> = async (): Promise<boolean> => this.blockClose();

  aboutToAppear(): void {
    this.mounted = true; this.openFiles(); this.observeClose();
  }

  aboutToDisappear(): void {
    this.mounted = false;
    this.coreGeneration++;
    this.coreOpening = false;
    try { this.mainWindow?.off('windowWillClose', this.closeHandler); } catch { /* Window may already be gone. */ }
    this.mainWindow = undefined;
  }

  onBackPress(): boolean { return this.blockClose(); }

  private async observeClose(): Promise<void> {
    try {
      const context = this.getUIContext().getHostContext() as common.UIAbilityContext;
      const mainWindow = await window.getLastWindow(context);
      if (!this.mounted) { return; }
      this.mainWindow = mainWindow; mainWindow.on('windowWillClose', this.closeHandler);
    } catch { this.status = '窗口关闭提示未能启用，请等待文件操作和任务结束后再退出。'; }
  }

  private blockClose(): boolean {
    if (!this.taskActive && !this.busy && !this.coreOpening) { return false; }
    this.getUIContext().showAlertDialog({ title: '操作尚未结束',
      message: this.taskActive ? '精修任务尚未结束。可以保持应用在后台运行，或在任务页请求取消并等待终态后退出。' :
        this.coreOpening ? '正在初始化计算服务并恢复任务状态，请稍候。' : '文件操作正在进行，请完成或取消文件选择后再退出。',
      confirm: { value: '返回应用', action: () => { if (this.taskActive) { this.page = 'refinement'; } } } });
    return true;
  }

  private async exit(): Promise<void> {
    if (this.blockClose()) { return; }
    try { await this.context?.terminateSelf(); } catch { this.status = '退出未完成，请重试。'; }
  }

  private async prepareTaskInputs(): Promise<RefinementInputs> {
    if (!this.service || !this.ready || this.busy) { throw new FileServiceError('CORE_NOT_READY', '文件服务尚未就绪。', true); }
    return this.selection.verify(this.service);
  }

  private async exportTaskArtifact(fileId: string): Promise<boolean> {
    if (!this.context || !this.service || this.busy) { throw new FileServiceError('BUSY', '请等待当前文件操作完成。', true); }
    this.busy = true;
    try { return await new FilePickerService(this.context, this.service).selectAndExport(fileId); }
    finally { this.busy = false; }
  }

  private async refreshFiles(): Promise<void> {
    const service = this.service;
    if (!service) { return; }
    try {
      const files = await service.listFiles();
      if (this.mounted && this.service === service) {
        this.files = files;
        this.status = `文件库：${files.length} 个文件`;
      }
    } catch (error) {
      if (this.mounted && this.service === service) { this.status = describeFileError(error); }
    }
  }

  private taskChanged(jobId: string, active: boolean): void {
    const wasActive = this.taskActive;
    this.taskActive = active;
    if (!active && jobId.length === 0) { this.knownJobId = ''; }
    // Includes restored terminal snapshots; progress and CancelAck keep the
    // task active. Outputs have been registered before the terminal event.
    if (wasActive && !active) { this.refreshFiles(); }
  }

  private async openFiles(): Promise<void> {
    if (this.busy || this.taskActive) { return; }
    this.busy = true;
    this.ready = false;
    this.settings = undefined;
    this.context = this.getUIContext().getHostContext() as common.UIAbilityContext;
    try {
      this.service = await AppServices.nativeFiles(this.context);
      this.files = await this.service.listFiles();
      this.settings = await preferences.getPreferences(this.context, { name: 'refinement-inputs' });
      const saved = await this.settings.get('bindings', '{"version":1,"bindings":[]}');
      const removed = this.selection.restore(String(saved), this.files);
      this.bindings = this.selection.entries();
      this.ready = true;
      this.status = this.files.length > 0 ? `已恢复 ${this.files.length} 个文件` : '请选择粉末数据、仪器参数和相文件。';
      if (removed > 0) { this.status += ` ${removed} 项输入关联已失效，请重新选择。`; }
      this.openCore();  // runtime unpacking and CPython boot run off the UI path
    } catch (error) {
      this.status = describeFileError(error);
      // A corrupt UI association must not make the persistent file library inaccessible.
      this.ready = this.service !== undefined && this.settings !== undefined;
    } finally { this.busy = false; }
  }

  /** Build and initialize the core facade; only then inject it as readyCore. */
  private async openCore(): Promise<void> {
    if (!this.mounted || !this.context || !this.service || this.coreOpening || this.coreReady) { return; }
    const generation = ++this.coreGeneration;
    const files = this.service;
    this.coreOpening = true;
    this.coreStatus = '正在初始化计算服务…';
    try {
      const core = await AppServices.core(this.context, files);
      await core.initialize(files.getCoreConfig());
      const jobId = await core.restoreJobId();
      if (!this.mounted || generation !== this.coreGeneration) { return; }
      this.knownJobId = jobId;
      this.core = core;
      this.coreReady = true;
      this.coreStatus = '计算服务已就绪。';
    } catch (error) {
      if (!this.mounted || generation !== this.coreGeneration) { return; }
      const failure = callError(error);
      this.coreStatus = `${failure.code}：${failure.message}`;
    } finally {
      if (this.mounted && generation === this.coreGeneration) { this.coreOpening = false; }
    }
  }

  private async saveSelection(): Promise<void> {
    this.bindings = this.selection.entries();
    this.prepared = false;
    if (!this.settings) { return; }
    try {
      await this.settings.put('bindings', this.selection.serialize());
      await this.settings.flush();
    } catch {
      // Preserve the in-memory choice, but never claim it survived a restart.
      this.status += ' 当前关联未能保存，重启后需要重新选择。';
    }
  }

  private candidates(slot: InputSlotInfo): AppFile[] {
    return this.files.filter((file: AppFile): boolean => file.role === slot.role);
  }

  private selectedName(slot: InputSlot): string {
    const binding = this.bindings.find((item: InputBinding): boolean => item.slot === slot);
    const file = this.files.find((item: AppFile): boolean => item.fileId === binding?.fileId);
    return file ? this.fileLabel(file) : '未选择';
  }

  private fileLabel(file: AppFile): string {
    return `${file.displayName} · ${file.sha256.slice(0, 8)}`;
  }

  private selectOptions(slot: InputSlotInfo): SelectOption[] {
    const options: SelectOption[] = [{ value: '未选择' }];
    return options.concat(this.candidates(slot).map((file: AppFile): SelectOption => ({ value: this.fileLabel(file) })));
  }

  private selectedIndex(slot: InputSlotInfo): number {
    const binding = this.bindings.find((item: InputBinding): boolean => item.slot === slot.id);
    return this.candidates(slot).findIndex((file: AppFile): boolean => file.fileId === binding?.fileId) + 1;
  }

  private async chooseExisting(slot: InputSlotInfo, index: number): Promise<void> {
    if (this.busy || this.taskActive || !this.ready) { return; }
    this.busy = true;
    try {
      if (index === 0) { this.selection.clear(slot.id); }
      else {
        const file = this.candidates(slot)[index - 1];
        if (!file) { return; }
        this.selection.select(slot.id, file);
      }
      this.status = '输入关联已更新，原文件保留在文件库中。';
      await this.saveSelection();
    } catch (error) { this.status = describeFileError(error); }
    finally { this.busy = false; }
  }

  private async importForSlot(slot: InputSlotInfo): Promise<void> {
    if (!this.context || !this.service || !this.ready || this.busy || this.taskActive) { return; }
    this.busy = true;
    try {
      const file = await new FilePickerService(this.context, this.service).selectAndImport(slot.role);
      if (!file) { this.status = '已取消选择，原关联保留。'; return; }
      this.files = await this.service.listFiles();
      this.selection.select(slot.id, file);
      this.status = `已将 ${file.displayName} 关联为${slot.label}。`;
      await this.saveSelection();
    } catch (error) { this.status = describeFileError(error); }
    finally { this.busy = false; }
  }

  private async verifyInputs(): Promise<void> {
    if (!this.service || !this.ready || this.busy || this.taskActive) { return; }
    this.busy = true;
    this.prepared = false;
    try {
      const inputs = await this.selection.verify(this.service);
      this.prepared = true;
      this.status = `已校验 ${inputs.histograms.length} 组粉末数据、仪器参数和 1 份相文件的存在性与完整性。尚未执行科学格式检查或精修。`;
    } catch (error) { this.status = describeFileError(error); }
    finally { this.busy = false; }
  }

  private async importFile(role: FileRole): Promise<void> {
    if (!this.context || !this.service || this.busy || this.taskActive) { return; }
    this.busy = true;
    try {
      const file = await new FilePickerService(this.context, this.service).selectAndImport(role);
      this.status = file ? `已导入 ${file.displayName}` : '已取消选择。';
      this.files = await this.service.listFiles();
    } catch (error) { this.status = describeFileError(error); }
    finally { this.busy = false; }
  }

  private async exportFile(fileId: string): Promise<void> {
    if (!this.context || !this.service || this.busy || this.taskActive) { return; }
    this.busy = true;
    try {
      const done = await new FilePickerService(this.context, this.service).selectAndExport(fileId);
      this.status = done ? '文件已导出。' : '已取消导出。';
    } catch (error) { this.status = describeFileError(error); }
    finally { this.busy = false; }
  }

  private async deleteFile(fileId: string): Promise<void> {
    if (!this.service || this.busy || this.taskActive) { return; }
    this.busy = true;
    try {
      await this.service.deleteFile(fileId); this.files = await this.service.listFiles();
      this.status = '已删除应用内副本，原文件不受影响。';
      this.selection.restore(this.selection.serialize(), this.files);
      await this.saveSelection();
    } catch (error) { this.status = describeFileError(error); }
    finally { this.busy = false; }
  }

  private async checkFiles(): Promise<void> {
    if (!this.context || this.busy || this.taskActive) { return; }
    this.busy = true; this.checks = '正在验证…';
    try {
      const report = await runFileServiceChecks(this.context);
      this.checks = `${report.passed} 项通过，${report.failed} 项失败，${report.skipped} 项跳过\n${report.lines.join('\n')}`;
      hilog.info(0, 'FileChecks', 'FILE_SERVICE_CHECKS %{public}d passed %{public}d failed', report.passed, report.failed);
      hilog.info(0, 'FileChecks', 'FILE_SERVICE_SKIPPED %{public}d', report.skipped);
      for (const line of report.lines) { hilog.info(0, 'FileChecks', '%{public}s', line); }
    } catch (error) { this.checks = describeFileError(error); }
    finally { this.busy = false; }
  }

  private boundFile(slot: InputSlot): AppFile | undefined {
    const binding = this.bindings.find((item: InputBinding): boolean => item.slot === slot);
    return this.files.find((file: AppFile): boolean => file.fileId === binding?.fileId);
  }

  private powderName(slot: InputSlot): string {
    return `PWDR ${this.boundFile(slot)?.displayName ?? ''}`;
  }

  private expandAll(): void {
    this.rootOpen = true; this.phasesOpen = true; this.xrayOpen = true; this.neutronOpen = true;
  }

  private importPowder(): void {
    this.getUIContext().showActionSheet({
      title: 'Import Powder Data',
      message: '',
      sheets: [
        { title: 'X-ray powder data', action: () => { this.page = 'xray'; this.importForSlot(INPUT_SLOTS[0]); } },
        { title: 'Neutron powder data', action: () => { this.page = 'neutron'; this.importForSlot(INPUT_SLOTS[2]); } }
      ]
    });
  }

  private confirmDelete(file: AppFile): void {
    this.getUIContext().showAlertDialog({
      title: `删除 ${file.displayName}？`, message: '仅删除应用内副本，并移除引用它的输入关联。原文件不受影响。',
      primaryButton: { value: '取消', action: () => {} },
      secondaryButton: { value: '删除副本', action: () => { this.deleteFile(file.fileId); } }
    });
  }

  @Builder
  fileMenu() {
    Menu() {
      MenuItem({ content: 'Open project...', labelInfo: 'Ctrl+O' }).enabled(false)
      MenuItem({ content: 'Open in new window...' }).enabled(false)
      MenuItem({ content: 'Reopen recent...', labelInfo: 'Ctrl+E' }).enabled(false)
      MenuItem({ content: 'Open w/project browser', labelInfo: 'Ctrl+B' }).enabled(false)
      MenuItem({ content: 'Save project', labelInfo: 'Ctrl+S' }).enabled(false)
      MenuItem({ content: 'Save project as...' }).enabled(false)
      MenuItem({ content: 'New project' }).enabled(false)
      MenuItem({ content: 'Preferences' }).enabled(false)
      MenuItem({ content: 'Exit', labelInfo: 'Alt+F4' }).onClick(() => { this.exit(); })
      MenuItemGroup({ header: 'HarmonyOS files' }) {
        MenuItem({ content: 'Imported files...' }).onClick(() => { this.page = 'files'; })
        MenuItem({ content: 'Input associations...' }).onClick(() => { this.page = 'Loaded Data'; })
      }
    }
  }

  @Builder
  dataMenu() {
    Menu() {
      ForEach(['Read Powder Pattern Peaks...', 'Sum or Average powder data', 'Sum image data',
        'Add new phase', 'Delete phase entries', 'Rename data entry', 'Delete data entries',
        'Delete plots', 'Delete sequential result entries'], (label: string) => {
        MenuItem({ content: label }).enabled(false)
      })
      MenuItem({ content: 'Expand tree items' }).onClick(() => { this.expandAll(); })
      MenuItem({ content: 'Move tree items' }).enabled(false)
    }
  }

  @Builder
  calculateMenu() {
    Menu() {
      MenuItem({ content: 'Setup PDFs' }).enabled(false)
      MenuItem({ content: 'View LS parms', labelInfo: 'Ctrl+L' }).enabled(false)
      MenuItem({ content: 'Refine...', labelInfo: 'Ctrl+R' }).onClick(() => { this.page = 'refinement'; })
      MenuItem({ content: 'Compute partials' }).enabled(false)
      MenuItem({ content: 'Parameter Impact', labelInfo: 'Ctrl+I' }).enabled(false)
      ForEach(['Evaluate expression and s.u.', 'Setup Cluster Analysis', 'Run Fprime', 'Run Absorb', 'Run PlotXNFF'],
        (label: string) => { MenuItem({ content: label }).enabled(false) })
    }
  }

  @Builder
  phaseImportMenu() {
    Menu() {
      MenuItem({ content: 'from CIF file' }).enabled(this.ready && !this.busy && !this.taskActive)
        .onClick(() => { this.page = 'phase'; this.importForSlot(INPUT_SLOTS[4]); })
    }
  }

  @Builder
  powderImportMenu() {
    Menu() {
      MenuItem({ content: 'from GSAS powder file' }).enabled(this.ready && !this.busy && !this.taskActive)
        .onClick(() => { this.importPowder(); })
    }
  }

  @Builder
  importMenu() {
    Menu() {
      MenuItem({ content: 'Image' }).enabled(false)
      MenuItem({ content: 'Phase', builder: this.phaseImportMenu })
      MenuItem({ content: 'Powder Data', builder: this.powderImportMenu })
      ForEach(['Fit instr. profile from fundamental parms...', 'Structure Factor', 'Small Angle Data',
        'Reflectometry Data', 'PDF G(R) Data', 'Read Powder Pattern Peaks...', 'Column metadata test'],
        (label: string) => { MenuItem({ content: label }).enabled(false) })
    }
  }

  @Builder
  exportMenu() {
    Menu() {
      ForEach(['Entire project as', 'Phase as', 'Powder data as', 'Small angle data as', 'Reflectometry data as',
        'Single crystal data as', 'Image data as', 'Maps as', 'Sequential project as CIF', 'Sequential phases',
        'Sequential histograms', 'Export All Peak Lists...', 'Export HKLs...', 'Export MTZ file...', 'Export PDF...'],
        (label: string) => { MenuItem({ content: label }).enabled(false) })
    }
  }

  @Builder
  helpMenu() {
    Menu() {
      MenuItem({ content: 'About GSAS-II' }).onClick(() => { this.page = 'about'; })
      ForEach(['Check for updates', 'Regress to old GSAS-II version', 'Add packages for more functionality',
        'Tutorials', 'Help on GSAS-II', 'Help on current data tree item', 'Help via LLM Docs Search', 'Citation information'],
        (label: string) => { MenuItem({ content: label }).enabled(false) })
    }
  }

  @Builder
  menuBar() {
    Row({ space: 0 }) {
      Button('File').desktopButton().borderWidth(0).bindMenu(this.fileMenu)
      Button('Data').desktopButton().borderWidth(0).bindMenu(this.dataMenu)
      Button('Calculate').desktopButton().borderWidth(0).bindMenu(this.calculateMenu)
        .keyboardShortcut('r', [ModifierKey.CTRL], () => { this.page = 'refinement'; })
      Button('Import').desktopButton().borderWidth(0).bindMenu(this.importMenu)
      Button('Export').desktopButton().borderWidth(0).bindMenu(this.exportMenu)
      Button('Help').desktopButton().borderWidth(0).bindMenu(this.helpMenu)
        .keyboardShortcut(FunctionKey.F1, [], () => { this.page = 'about'; })
    }.width('100%').height(30).backgroundColor('#EEEEEE')
  }

  @Builder
  treeLeaf(key: string, label: string, depth: number) {
    Button(label).type(ButtonType.Normal).fontSize(13).fontColor('#171717')
      .backgroundColor(this.page === key ? '#CBE4FA' : Color.Transparent).borderRadius(0)
      .width('100%').height(27).align(Alignment.Start).padding({ left: depth * 18 + 22, right: 4 })
      .onClick(() => { this.page = key; })
  }

  @Builder
  treeBranch(key: string, label: string, depth: number, open: boolean) {
    Row({ space: 0 }) {
      Button(open ? '▾' : '▸').type(ButtonType.Normal).fontSize(14).fontColor('#333333')
        .backgroundColor(Color.Transparent).borderRadius(0).width(22).height(27).padding(0)
        .accessibilityText(`${open ? 'Collapse' : 'Expand'} ${label}`)
        .onClick(() => {
          if (key === 'Loaded Data') { this.rootOpen = !this.rootOpen; }
          if (key === 'Phases') { this.phasesOpen = !this.phasesOpen; }
          if (key === 'xray') { this.xrayOpen = !this.xrayOpen; }
          if (key === 'neutron') { this.neutronOpen = !this.neutronOpen; }
        })
      Button(label).type(ButtonType.Normal).fontSize(13).fontColor('#171717')
        .backgroundColor(Color.Transparent).borderRadius(0).height(27).layoutWeight(1)
        .align(Alignment.Start).padding({ left: 0, right: 4 }).onClick(() => { this.page = key; })
    }.padding({ left: depth * 18 }).width('100%')
      .backgroundColor(this.page === key ? '#CBE4FA' : Color.Transparent)
  }

  @Builder
  dataTree() {
    Scroll() {
      Column({ space: 0 }) {
        this.treeBranch('Loaded Data', 'Loaded Data:', 0, this.rootOpen)
        if (this.rootOpen) {
          ForEach(this.projectNodes, (label: string) => { this.treeLeaf(label, label, 1) })
          if (this.boundFile(InputSlot.PHASE)) {
            this.treeBranch('Phases', 'Phases', 1, this.phasesOpen)
            if (this.phasesOpen) { this.treeLeaf('phase', this.boundFile(InputSlot.PHASE)?.displayName ?? '', 2) }
          }
          if (this.boundFile(InputSlot.XRAY_DATA)) {
            this.treeBranch('xray', this.powderName(InputSlot.XRAY_DATA), 1, this.xrayOpen)
            if (this.xrayOpen) {
              ForEach(this.powderNodes, (label: string) => { this.treeLeaf(`xray:${label}`, label, 2) })
            }
          }
          if (this.boundFile(InputSlot.NEUTRON_DATA)) {
            this.treeBranch('neutron', this.powderName(InputSlot.NEUTRON_DATA), 1, this.neutronOpen)
            if (this.neutronOpen) {
              ForEach(this.powderNodes, (label: string) => { this.treeLeaf(`neutron:${label}`, label, 2) })
            }
          }
        }
      }.alignItems(HorizontalAlign.Start).width('100%').padding({ top: 5, bottom: 12 })
    }.align(Alignment.TopStart).height('100%').width(this.treeWidth)
      .clip(true).backgroundColor(Color.White)
  }

  @Builder
  pageTitle(title: string) {
    Text(title).fontSize(16).fontWeight(FontWeight.Bold).width('100%').margin({ bottom: 8 })
  }

  @Builder
  unavailable(message: string) {
    Text(message).fontSize(13).fontColor('#555555').width('100%').margin({ top: 8, bottom: 8 })
  }

  @Builder
  inputRow(slot: InputSlotInfo) {
    Column({ space: 6 }) {
      Text(slot.label).fontSize(13).width('100%')
      Flex({ wrap: FlexWrap.Wrap, alignItems: ItemAlign.Center }) {
        Select(this.selectOptions(slot)).selected(this.selectedIndex(slot)).value(this.selectedName(slot.id))
          .font({ size: 13 }).height(30).width(290).constraintSize({ maxWidth: '100%' })
          .borderRadius(2).margin({ right: 8, bottom: 6 })
          .id(`select-${slot.id}`).enabled(this.ready && !this.busy && !this.taskActive)
          .onSelect((index: number) => { this.chooseExisting(slot, index); })
        Button('Import...').desktopButton().id(`import-${slot.id}`).enabled(this.ready && !this.busy && !this.taskActive)
          .onClick(() => { this.importForSlot(slot); }).margin({ bottom: 6 })
      }
    }.width('100%').margin({ bottom: 12 })
  }

  private parameterScope(): string {
    return draftScope(this.page, this.bindings);
  }

  @Builder
  parameters(panel: string) {
    if (this.ready && this.parameterScope()) {
      ParameterPanel({ panel, scope: this.parameterScope() })
    } else { this.unavailable('请等待文件库就绪，并关联此页面需要的输入文件后编辑。') }
  }

  @Builder
  inputPage() {
    this.pageTitle('Loaded Data')
    ForEach(INPUT_SLOTS, (slot: InputSlotInfo) => { this.inputRow(slot) }, (slot: InputSlotInfo) => slot.id)
    Button(this.prepared ? 'Recheck input files' : 'Check input files').desktopButton().id('verify-inputs')
      .enabled(this.ready && !this.busy && !this.taskActive).onClick(() => { this.verifyInputs(); })
  }

  @Builder
  powderPage(data: InputSlotInfo, instrument: InputSlotInfo) {
    this.pageTitle(this.powderName(data.id))
    this.inputRow(data)
    this.inputRow(instrument)
    this.unavailable('曲线预览暂不可用。')
  }

  private visibleFiles(): AppFile[] {
    const query = this.fileQuery.trim().toLowerCase();
    return this.files.filter((file: AppFile): boolean => (!this.fileRole || file.role === this.fileRole) &&
      (!query || file.displayName.toLowerCase().includes(query) || file.fileId.toLowerCase().includes(query) ||
        file.sha256.toLowerCase().includes(query)));
  }

  @Builder
  filesPage() {
    this.pageTitle('Imported files')
    Flex({ wrap: FlexWrap.Wrap }) {
      Button('Powder data...').desktopButton().enabled(this.ready && !this.busy && !this.taskActive)
        .onClick(() => { this.importFile(FileRole.POWDER_DATA); }).margin({ right: 8, bottom: 8 })
      Button('Instrument...').desktopButton().enabled(this.ready && !this.busy && !this.taskActive)
        .onClick(() => { this.importFile(FileRole.INSTRUMENT); }).margin({ right: 8, bottom: 8 })
      Button('Phase...').desktopButton().enabled(this.ready && !this.busy && !this.taskActive)
        .onClick(() => { this.importFile(FileRole.PHASE); }).margin({ right: 8, bottom: 8 })
      Button('Refresh').desktopButton().enabled(this.ready && !this.busy && !this.taskActive)
        .onClick(() => { this.refreshFiles(); }).margin({ bottom: 8 })
    }
    TextInput({ text: this.fileQuery, placeholder: '搜索文件' }).fontSize(13).height(32)
      .maxLength(256).id('file-library-search').accessibilityText('搜索文件库')
      .onChange((value: string) => { this.fileQuery = value; })
    Flex({ wrap: FlexWrap.Wrap, alignItems: ItemAlign.Center }) {
      Select(this.fileRoles.map((role: string): SelectOption => ({ value: role || '全部类型' })))
        .selected(this.fileRoles.indexOf(this.fileRole)).value(this.fileRole || '全部类型')
        .font({ size: 13 }).height(30).width(220).margin({ right: 8, top: 8, bottom: 8 })
        .accessibilityText('筛选文件类型').onSelect((index: number) => { this.fileRole = this.fileRoles[index] ?? ''; })
      Button('Clear filters').desktopButton().enabled(this.fileQuery !== '' || this.fileRole !== '')
        .onClick(() => { this.fileQuery = ''; this.fileRole = ''; })
    }.width('100%')
    Text(`显示 ${this.visibleFiles().length} / ${this.files.length} 个文件`).fontSize(12).width('100%').margin({ bottom: 12 })
    if (this.files.length === 0) { this.unavailable('文件库为空。') }
    else if (this.visibleFiles().length === 0) { this.unavailable('没有匹配的文件，请调整搜索词或清除筛选。') }
    ForEach(this.visibleFiles(), (file: AppFile) => {
      Column({ space: 5 }) {
        Text(file.displayName).fontSize(14).fontWeight(FontWeight.Bold).width('100%')
        Text(`${file.role} · ${file.size} bytes`).fontSize(12).width('100%')
        Row({ space: 8 }) {
          Button('Export copy...').desktopButton().enabled(!this.busy && !this.taskActive).onClick(() => { this.exportFile(file.fileId); })
          Button('Delete copy...').desktopButton().enabled(!this.busy && !this.taskActive).onClick(() => { this.confirmDelete(file); })
        }.width('100%')
        Divider().margin({ top: 8 })
      }.width('100%').margin({ bottom: 12 })
    }, (file: AppFile) => file.fileId)
  }

  @Builder
  dataPage() {
    Scroll() {
      Column({ space: 0 }) {
        if (this.page === 'Controls') { this.parameters('Controls') }
        else if (this.page === 'Notebook') { this.parameters('Notebook') }
        else if (this.page === 'xray:Comments' || this.page === 'neutron:Comments') {
          Text(this.powderName(this.page.startsWith('xray') ? InputSlot.XRAY_DATA : InputSlot.NEUTRON_DATA))
            .fontSize(16).fontWeight(FontWeight.Bold).width('100%').margin({ bottom: 8 })
          this.parameters('Comments')
        }
        else if (this.page === 'Loaded Data') { this.inputPage() }
        else if (this.page === 'files') { this.filesPage() }
        else if (this.page === 'Phases' || this.page === 'phase') {
          this.pageTitle('Phases')
          this.inputRow(INPUT_SLOTS[4])
          this.unavailable('晶胞与原子编辑暂不可用。')
        } else if (this.page === 'xray') { this.powderPage(INPUT_SLOTS[0], INPUT_SLOTS[1]) }
        else if (this.page === 'neutron') { this.powderPage(INPUT_SLOTS[2], INPUT_SLOTS[3]) }
        else if (this.page === 'xray:Instrument Parameters' || this.page === 'neutron:Instrument Parameters') {
          this.inputRow(this.page.startsWith('xray') ? INPUT_SLOTS[1] : INPUT_SLOTS[3])
          this.parameters('Instrument Parameters')
        } else if (this.page.endsWith(':Limits') || this.page.endsWith(':Background') || this.page.endsWith(':Sample Parameters')) {
          this.parameters(this.page.split(':')[1])
        } else if (this.page === 'about') {
          this.pageTitle('GSAS-II — HarmonyOS port')
          this.unavailable('GSAS-II 2.0.0 · 五阶段粉末精修 · 当前支持 PbSO4 样例')
          this.unavailable('Ctrl+R：精修；F1：帮助；Tab / Shift+Tab：切换控件。取消需等待当前阶段结束。')
          this.unavailable('参数页保存本地草稿；精修采用任务页中填写的参数。')
          Button('Check file library').desktopButton().id('file-checks').enabled(this.ready && !this.busy && !this.taskActive)
            .onClick(() => { this.checkFiles(); })
          if (this.checks.length > 0) { Text(this.checks).fontSize(12).width('100%') }
          this.unavailable('This product includes software produced by UChicago Argonne, LLC under Contract No. DE-AC02-06CH11357 with the Department of Energy.')
        } else {
          this.pageTitle(this.page.includes(':') ? this.page.split(':')[1] : this.page)
          this.unavailable('此功能暂不可用。')
        }
        if (!this.ready) {
          Button('重新打开文件库').desktopButton().enabled(!this.busy && !this.taskActive).onClick(() => { this.openFiles(); })
        }
      }.alignItems(HorizontalAlign.Start).width('100%').padding(16)
    }.align(Alignment.TopStart).height('100%').width('100%')
      .clip(true).backgroundColor('#F0F0F0')
  }

  build() {
    Column({ space: 0 }) {
      this.menuBar()
      Divider()
      Row({ space: 0 }) {
        this.dataTree()
        Column() {}.width(8).height('100%').backgroundColor('#D0D0D0')
          .accessibilityText('Resize data tree').gesture(
            PanGesture({ direction: PanDirection.Horizontal, distance: 1 })
              .onActionStart(() => { this.dragStartWidth = this.treeWidth; })
              .onActionUpdate((event: GestureEvent) => {
                this.treeWidth = Math.max(190, Math.min(450, this.panelWidth - 268, this.dragStartWidth + event.offsetX));
              })
          )
        Stack() {
          Column() { this.dataPage() }.width('100%').height('100%')
            .visibility(this.page === 'refinement' ? Visibility.None : Visibility.Visible)
          // B injects the initialized facade and the persisted job ID here.
          // Branch swap remounts the panel exactly when initialization flips
          // (panel contract: "mount a new panel when initialization finishes");
          // keeping either branch mounted preserves subscription while browsing.
          if (!this.coreReady) {
            RefinementPanel({ filesReady: this.ready && !this.busy,
              phaseName: this.phaseName, cycles: this.cycles, projectName: this.projectName,
              coreStatus: this.coreStatus, coreOpening: this.coreOpening,
              retryCore: (): void => { this.openCore(); },
              prepareInputs: async (): Promise<RefinementInputs> => this.prepareTaskInputs(),
              exportArtifact: async (fileId: string): Promise<boolean> => this.exportTaskArtifact(fileId),
              onTaskChange: (_jobId: string, active: boolean): void => { this.taskActive = active; } })
              .visibility(this.page === 'refinement' ? Visibility.Visible : Visibility.None)
          } else {
            RefinementPanel({ readyCore: this.core, knownJobId: this.knownJobId,
              phaseName: this.phaseName, cycles: this.cycles, projectName: this.projectName,
              filesReady: this.ready && !this.busy,
              prepareInputs: async (): Promise<RefinementInputs> => this.prepareTaskInputs(),
              exportArtifact: async (fileId: string): Promise<boolean> => this.exportTaskArtifact(fileId),
              onTaskChange: (jobId: string, active: boolean): void => { this.taskChanged(jobId, active); } })
              .visibility(this.page === 'refinement' ? Visibility.Visible : Visibility.None)
          }
        }.height('100%').layoutWeight(1)
      }.layoutWeight(1).width('100%')
      Divider()
      Row({ space: 8 }) {
        Text(this.status).fontSize(12).fontColor('#303030').layoutWeight(1).maxLines(3)
        Divider().vertical(true).height(28)
        Text(this.taskActive ? '精修中' : this.busy ? '处理中…' : this.coreOpening ? '初始化中…' : this.coreReady ? '就绪' : '计算不可用').fontSize(12).fontColor('#555555').width(110)
      }.width('100%').height(54).padding({ left: 8, right: 8 }).backgroundColor('#EEEEEE')
    }.width('100%').height('100%').backgroundColor('#F0F0F0')
      .onAreaChange((_old: Area, area: Area) => {
        this.panelWidth = Number(area.width);
        this.treeWidth = Math.max(190, Math.min(this.treeWidth, this.panelWidth - 268));
      })
  }
}
