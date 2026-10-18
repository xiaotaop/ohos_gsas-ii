import { common } from '@kit.AbilityKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { AppFile, FileLibrary, FileRole, describeFileError } from '../contracts/Files';
import { AppServices } from '../services/AppServices';
import { FilePickerService } from '../services/FilePickerService';
import { runFileServiceChecks } from '../verification/FileServiceCheck';

@Entry
@Component
struct Index {
  @State private files: AppFile[] = [];
  @State private status: string = '正在打开文件库…';
  @State private ready: boolean = false;
  @State private busy: boolean = false;
  @State private checks: string = '';
  private service: FileLibrary | undefined = undefined;
  private context: common.UIAbilityContext | undefined = undefined;

  aboutToAppear(): void { this.openFiles(); }

  private async openFiles(): Promise<void> {
    this.context = this.getUIContext().getHostContext() as common.UIAbilityContext;
    try {
      this.service = await AppServices.files(this.context);
      this.files = await this.service.listFiles(); this.ready = true;
      this.status = this.files.length > 0 ? `已恢复 ${this.files.length} 个文件` : '请选择粉末数据、仪器参数和相文件。';
    } catch (error) { this.status = describeFileError(error); }
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
        Text('导入数据与管理结果').fontSize(20)
        Text('先准备 X 射线、中子粉末数据，各自的仪器参数和 CIF 相文件。').fontColor('#526174').fontSize(15)
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
