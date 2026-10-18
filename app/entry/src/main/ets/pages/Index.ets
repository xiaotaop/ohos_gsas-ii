import { common } from '@kit.AbilityKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { preferences } from '@kit.ArkData';
import { AppFile, FileLibrary, FileRole, describeFileError } from '../contracts/Files';
import { AppServices } from '../services/AppServices';
import { FilePickerService } from '../services/FilePickerService';
import { runFileServiceChecks } from '../verification/FileServiceCheck';
import { INPUT_SLOTS, InputSlot, InputSlotInfo, InputBinding, InputSelection } from '../model/RefinementInputs';

@Entry
@Component
struct Index {
  @State private files: AppFile[] = [];
  @State private status: string = '正在打开文件库…';
  @State private ready: boolean = false;
  @State private busy: boolean = false;
  @State private checks: string = '';
  @State private bindings: InputBinding[] = [];
  @State private prepared: boolean = false;
  private selection: InputSelection = new InputSelection();
  private settings: preferences.Preferences | undefined = undefined;
  private service: FileLibrary | undefined = undefined;
  private context: common.UIAbilityContext | undefined = undefined;

  aboutToAppear(): void { this.openFiles(); }

  private async openFiles(): Promise<void> {
    if (this.busy) { return; }
    this.busy = true;
    this.ready = false;
    this.settings = undefined;
    this.context = this.getUIContext().getHostContext() as common.UIAbilityContext;
    try {
      this.service = await AppServices.files(this.context);
      this.files = await this.service.listFiles();
      this.settings = await preferences.getPreferences(this.context, { name: 'refinement-inputs' });
      const saved = await this.settings.get('bindings', '{"version":1,"bindings":[]}');
      const removed = this.selection.restore(String(saved), this.files);
      this.bindings = this.selection.entries();
      this.ready = true;
      this.status = this.files.length > 0 ? `已恢复 ${this.files.length} 个文件` : '请选择粉末数据、仪器参数和相文件。';
      if (removed > 0) { this.status += ` ${removed} 项输入关联已失效，请重新选择。`; }
    } catch (error) {
      this.status = describeFileError(error);
      // A corrupt UI association must not make the persistent file library inaccessible.
      this.ready = this.service !== undefined && this.settings !== undefined;
    } finally { this.busy = false; }
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
    if (this.busy || !this.ready) { return; }
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
    if (!this.context || !this.service || !this.ready || this.busy) { return; }
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
    if (!this.service || !this.ready || this.busy) { return; }
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
    if (!this.context || !this.service || this.busy) { return; }
    this.busy = true;
    try {
      const file = await new FilePickerService(this.context, this.service).selectAndImport(role);
      this.status = file ? `已导入 ${file.displayName}` : '已取消选择。';
      this.files = await this.service.listFiles();
    } catch (error) { this.status = describeFileError(error); }
    finally { this.busy = false; }
  }

  private async exportFile(fileId: string): Promise<void> {
    if (!this.context || !this.service || this.busy) { return; }
    this.busy = true;
    try {
      const done = await new FilePickerService(this.context, this.service).selectAndExport(fileId);
      this.status = done ? '文件已导出。' : '已取消导出。';
    } catch (error) { this.status = describeFileError(error); }
    finally { this.busy = false; }
  }

  private async deleteFile(fileId: string): Promise<void> {
    if (!this.service || this.busy) { return; }
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
    if (!this.context || this.busy) { return; }
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

  build() {
    Scroll() {
      Column({ space: 18 }) {
        Text('GSAS PC').fontSize(30).fontWeight(FontWeight.Bold)
        Text('粉末精修 · 输入准备').fontSize(20)
        Text('先准备 X 射线、中子粉末数据，各自的仪器参数和 CIF 相文件。').fontColor('#526174').fontSize(15)
        Text('当前准备 GSAS powder 五阶段输入。请选择每个位置对应的文件；相同文件名不会自动关联。').fontColor('#526174').fontSize(14)
        ForEach(INPUT_SLOTS, (slot: InputSlotInfo) => {
          Column({ space: 8 }) {
            Text(slot.label).fontSize(17).fontWeight(FontWeight.Bold).width('100%')
            Flex({ wrap: FlexWrap.Wrap, alignItems: ItemAlign.Center }) {
              Select(this.selectOptions(slot)).selected(this.selectedIndex(slot))
                .value(this.selectedName(slot.id)).width(360).margin({ right: 12, bottom: 8 })
                .id(`select-${slot.id}`).enabled(this.ready && !this.busy)
                .onSelect((index: number) => { this.chooseExisting(slot, index); })
              Button('导入并关联').id(`import-${slot.id}`).enabled(this.ready && !this.busy)
                .onClick(() => { this.importForSlot(slot); }).margin({ bottom: 8 })
            }
          }.padding(14).width('100%').backgroundColor('#EFF4F9').borderRadius(10)
        }, (slot: InputSlotInfo) => slot.id)
        Flex({ wrap: FlexWrap.Wrap }) {
          Button(this.prepared ? '重新校验输入' : '校验五份输入').id('verify-inputs')
            .enabled(this.ready && !this.busy).onClick(() => { this.verifyInputs(); }).margin({ right: 12, bottom: 8 })
          Button('Refine / 开始精修').id('refine-unavailable').enabled(false)
        }
        Text('计算服务尚未接入。可先保存输入关联；当前不会运行精修或生成结果。').fontColor('#526174').width('100%')
        Divider()
        Text('文件库').fontSize(20).fontWeight(FontWeight.Bold)
        Flex({ wrap: FlexWrap.Wrap }) {
          Button('导入粉末数据').id('import-powder').onClick(() => { this.importFile(FileRole.POWDER_DATA); })
            .enabled(this.ready && !this.busy).margin({ right: 12, bottom: 12 })
          Button('导入仪器参数').id('import-instrument').onClick(() => { this.importFile(FileRole.INSTRUMENT); })
            .enabled(this.ready && !this.busy).margin({ right: 12, bottom: 12 })
          Button('导入相文件').id('import-phase').onClick(() => { this.importFile(FileRole.PHASE); })
            .enabled(this.ready && !this.busy).margin({ right: 12, bottom: 12 })
        }
        Text(this.status).fontSize(15).fontColor('#24486B').width('100%')
        if (!this.ready) { Button('重新打开文件库').onClick(() => { this.openFiles(); }) }
        if (this.files.length === 0) {
          Text('文件库为空。导入后将保存应用内副本，重启后仍可使用。')
            .width('100%').padding(22).backgroundColor('#EFF4F9').borderRadius(12)
        }
        ForEach(this.files, (file: AppFile) => {
          Column({ space: 9 }) {
            Text(file.displayName).fontWeight(FontWeight.Bold).fontSize(18).width('100%')
            Text(`${file.role} · ${file.size} 字节`).fontColor('#526174').width('100%')
            Text(`SHA-256 ${file.sha256}`).fontSize(11).fontColor('#526174').width('100%')
            Row({ space: 12 }) {
              Button('导出副本').onClick(() => { this.exportFile(file.fileId); }).enabled(!this.busy)
              Button('删除副本').onClick(() => { this.deleteFile(file.fileId); }).enabled(!this.busy)
            }.width('100%')
          }.padding(18).width('100%').backgroundColor('#EFF4F9').borderRadius(12)
        }, (file: AppFile) => file.fileId)
        Text('计算核心尚待接入；当前可导入、保存和导出真实文件。').fontColor('#526174').width('100%')
        Divider()
        Button('运行文件服务验证').id('file-checks').onClick(() => { this.checkFiles(); }).enabled(this.ready && !this.busy)
        if (this.checks.length > 0) { Text(this.checks).fontSize(13).width('100%') }
        Text('This product includes software produced by UChicago Argonne, LLC under Contract No. DE-AC02-06CH11357 with the Department of Energy.')
          .fontSize(10).fontColor('#64748B').width('100%')
      }.alignItems(HorizontalAlign.Start).padding(28).width('100%').constraintSize({ maxWidth: 1100 })
    }.width('100%').height('100%').align(Alignment.TopStart).backgroundColor('#FFFFFF')
  }
}
