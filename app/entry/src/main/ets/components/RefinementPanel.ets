import { util } from '@kit.ArkTS';
import { describeFileError } from '../contracts/Files';
import { RefinementInputs } from '../model/RefinementInputs';
import { Artifact, CoreService, RefinementSession, RefinementView, StageResult,
  isActive, prepareRefinementRequest, stageLabel } from '../model/Refinement';

@Extend(Button) function refinementButton() {
  .type(ButtonType.Normal).height(30).fontSize(13).fontColor('#202020').backgroundColor('#EEEEEE')
  .borderRadius(2).border({ width: 1, color: '#B8B8B8' }).padding({ left: 12, right: 12 })
}

// Receives an initialized, application-owned service. Never creates a mock or
// guesses a persisted job ID. B/C supply these two values at the page entry.
@Component
export struct RefinementPanel {
  // Immutable service inputs: @Prop would copy the service's state. Mount a new
  // panel when application initialization finishes or the service is replaced.
  readyCore: CoreService | undefined = undefined;
  knownJobId: string = '';
  @Prop filesReady: boolean = false;
  prepareInputs: () => Promise<RefinementInputs> = async () => { throw new Error('Files unavailable'); };
  exportArtifact: (fileId: string) => Promise<boolean> = async () => { throw new Error('Files unavailable'); };
  onTaskChange: (jobId: string, active: boolean) => void = () => {};
  @State private view: RefinementView = new RefinementView();
  @State private cancelRequested: boolean = false;
  @State private notice: string = '';
  @State private formError: string = '';
  @State private cycles: string = '';
  @State private phaseName: string = '';
  @State private projectName: string = '';
  @State private submitting: boolean = false;
  @State private exporting: boolean = false;
  private session: RefinementSession | undefined = undefined;
  private generation: number = 0;
  private mounted: boolean = false;

  aboutToAppear(): void { this.mounted = true; this.connect(); }
  aboutToDisappear(): void {
    this.mounted = false; this.generation++; this.session?.disconnect();
  }

  private connect(): void {
    this.submitting = false;
    this.generation++; this.session?.disconnect(); this.session = undefined;
    if (!this.mounted || !this.readyCore) { return; }
    const generation = this.generation;
    const session = new RefinementSession(this.readyCore, () => {
      if (!this.mounted || this.generation !== generation || !this.session) { return; }
      this.view = this.session.view; this.cancelRequested = this.session.cancelRequested;
      this.notice = this.session.notice;
      this.onTaskChange(this.view.jobId, this.submitting || isActive(this.view.state));
    });
    this.session = session;
    session.connect(this.view.jobId || this.knownJobId).catch(() => {
      if (this.generation === generation) { this.notice = '任务订阅失败，请重新连接。'; }
    });
  }

  private async start(): Promise<void> {
    if (!this.session || !this.readyCore || !this.filesReady || this.submitting || isActive(this.view.state)) { return; }
    const session = this.session; const generation = this.generation;
    let submitted = false;
    this.submitting = true; this.formError = ''; this.onTaskChange(this.view.jobId, true);
    try {
      const inputs = await this.prepareInputs();
      if (!this.mounted || generation !== this.generation) { return; }
      const request = prepareRefinementRequest(`job_${util.generateRandomUUID()}`, inputs,
        this.phaseName, this.cycles, this.projectName);
      // Once start() is entered it owns the queued state. Do not block Cancel
      // (or keep files locked after a terminal event) on a late acceptance Promise.
      this.submitting = false; submitted = true;
      await session.start(request);
    } catch (error) { if (this.mounted && generation === this.generation) { this.formError = describeFileError(error); } }
    finally {
      if (!submitted && this.mounted && generation === this.generation) {
        this.submitting = false; this.onTaskChange(this.view.jobId, isActive(this.view.state));
      }
    }
  }

  private async saveArtifact(artifact: Artifact): Promise<void> {
    if (this.exporting || !this.filesReady) { return; }
    this.exporting = true; const generation = this.generation;
    try {
      const done = await this.exportArtifact(artifact.fileId);
      if (this.mounted && this.generation === generation) { this.formError = done ? '文件已导出。' : '已取消导出。'; }
    } catch (error) {
      if (this.mounted && this.generation === generation) { this.formError = describeFileError(error); }
    } finally { if (this.mounted) { this.exporting = false; } }
  }

  private title(): string {
    if (this.cancelRequested && isActive(this.view.state)) { return '正在取消 — 等待当前阶段结束'; }
    if (this.view.state === 'succeeded') { return '精修完成'; }
    if (this.view.state === 'failed') { return '任务失败'; }
    if (this.view.state === 'cancelled') { return '任务已取消'; }
    if (isActive(this.view.state)) { return '精修进行中'; }
    return '五阶段粉末精修';
  }

  @Builder
  resultStage(stage: StageResult) {
    Column({ space: 4 }) {
      Text(stageLabel(stage.name)).fontSize(14).fontWeight(FontWeight.Bold).width('100%')
      ForEach(Object.keys(stage.rwpByHistogram), (histogram: string) => {
        Text(`${histogram} · Rwp ${stage.rwpByHistogram[histogram].toFixed(5)}`).fontSize(13).width('100%')
      })
    }.width('100%').margin({ bottom: 8 })
  }

  build() {
    Scroll() {
      Column({ space: 12 }) {
        Text(this.title()).fontSize(18).fontWeight(FontWeight.Bold).width('100%')
        if (!this.readyCore) {
          Text('计算服务尚未接入。可以准备输入和参数，当前不能开始精修。').fontSize(14).fontColor('#805400').width('100%')
        }
        Text('X 射线 + 中子 + CIF · 当前仅支持已验证的 PbSO4 样例组合').fontSize(13).width('100%')
        Text('填写本次任务参数；其他参数页的本地草稿不会自动提交。').fontSize(13).fontColor('#555555').width('100%')
        TextInput({ text: this.phaseName, placeholder: '相名（明确填写，最多 80 字符）' }).maxLength(80)
          .id('refinement-phase-name').enabled(!this.submitting && !isActive(this.view.state))
          .onChange((value: string) => { this.phaseName = value; })
        TextInput({ text: this.cycles, placeholder: 'Max cycles（0～50，无预设值）' }).maxLength(2)
          .id('refinement-cycles').enabled(!this.submitting && !isActive(this.view.state))
          .onChange((value: string) => { this.cycles = value; })
        TextInput({ text: this.projectName, placeholder: '输出文件名，例如 PbSO4-refined.gpx' }).maxLength(104)
          .id('refinement-output').enabled(!this.submitting && !isActive(this.view.state))
          .onChange((value: string) => { this.projectName = value; })
        Flex({ wrap: FlexWrap.Wrap }) {
          Button(this.submitting ? 'Checking inputs...' : 'Refine').refinementButton().id('start-refinement')
            .enabled(this.readyCore !== undefined && this.filesReady && !this.submitting && !isActive(this.view.state))
            .onClick(() => { this.start(); }).margin({ right: 8, bottom: 8 })
          Button(this.cancelRequested ? 'Cancelling...' : 'Cancel refinement').refinementButton()
            .id('cancel-refinement').enabled(isActive(this.view.state) && !this.cancelRequested && !this.submitting)
            .onClick(() => { this.session?.cancel(); }).margin({ right: 8, bottom: 8 })
          Button('Reconnect').refinementButton().enabled(this.readyCore !== undefined && !this.submitting)
            .onClick(() => { this.connect(); }).margin({ bottom: 8 })
        }.width('100%')
        if (this.formError) { Text(this.formError).fontSize(13).width('100%') }
        if (this.notice) { Text(this.notice).fontSize(13).fontColor('#805400').width('100%') }
        if (this.view.jobId) {
          Divider()
          Text(`${this.view.jobId} · ${this.view.state}`).fontSize(12).width('100%')
          Progress({ value: this.view.percent, total: 100, type: ProgressType.Linear }).width('100%')
          Text(`${this.view.percent.toFixed(0)}% · ${this.view.message}`).fontSize(14).width('100%')
        }
        if (this.view.error) {
          Text(`${this.view.error.code}：${this.view.error.message}`).fontSize(14).fontColor('#B3261E').width('100%')
          Text(this.view.error.retryable ? '可在服务就绪且输入校验通过后重新提交。' : '请先修正输入或参数，再提交新任务。').fontSize(13).width('100%')
        }
        // B03: failure/cancellation logs come only from the registered
        // artifacts the terminal payload carried — never from names, paths
        // or the message history. No artifacts means registration did not
        // complete, and the page says so plainly.
        if (this.view.state === 'failed' || this.view.state === 'cancelled') {
          if (this.view.terminalArtifacts !== undefined && this.view.terminalArtifacts.length > 0) {
            Text(this.view.state === 'cancelled' ? '取消日志' : '失败日志').fontSize(14)
              .fontWeight(FontWeight.Bold).width('100%')
            ForEach(this.view.terminalArtifacts, (artifact: Artifact) => {
              Row({ space: 8 }) {
                Text(artifact.displayName).fontSize(13).layoutWeight(1)
                Button('Export...').refinementButton().enabled(this.filesReady && !this.exporting)
                  .onClick(() => { this.saveArtifact(artifact); })
              }.width('100%')
            }, (artifact: Artifact) => artifact.fileId)
          } else {
            Text('日志登记未完成，本次终态没有可导出的日志文件。').fontSize(12).fontColor('#805400').width('100%')
          }
        }
        if (this.view.result) {
          Text(`结果 · ${this.view.result.elapsedSeconds.toFixed(2)} 秒`).fontSize(16).fontWeight(FontWeight.Bold).width('100%')
          Text(`上游版本 ${this.view.result.upstreamCommit}`).fontSize(12).width('100%')
          ForEach(this.view.result.stages, (stage: StageResult) => { this.resultStage(stage) })
          if (this.view.result.preferredOrientation) {
            Text('择优取向').fontSize(14).fontWeight(FontWeight.Bold).width('100%')
            ForEach(Object.keys(this.view.result.preferredOrientation), (histogram: string) => {
              Text(`${histogram} · ${this.view.result?.preferredOrientation?.[histogram]}`).fontSize(13).width('100%')
            })
          }
          Text(this.view.result.validation?.performed ?
            (this.view.result.validation?.passed ? '基线校验通过' : '基线校验未通过') : '本次未执行基线校验')
            .fontSize(13).width('100%')
          ForEach(this.view.result.artifacts, (artifact: Artifact) => {
            Row({ space: 8 }) {
              Text(`${artifact.displayName} · ${artifact.kind}`).fontSize(13).layoutWeight(1)
              Button('Export...').refinementButton().enabled(this.filesReady && !this.exporting)
                .onClick(() => { this.saveArtifact(artifact); })
            }.width('100%')
          }, (artifact: Artifact) => artifact.fileId)
        }
        if (this.view.history.length > 0) {
          Text('任务消息').fontSize(14).fontWeight(FontWeight.Bold).width('100%')
          Text(this.view.history.join('\n')).fontSize(12).width('100%')
          Text('任务消息不是日志文件；只有已登记的产物才能导出。').fontSize(12).fontColor('#555555').width('100%')
        }
      }.width('100%').padding(16).alignItems(HorizontalAlign.Start)
    }.align(Alignment.TopStart).width('100%').height('100%').backgroundColor('#F0F0F0')
  }
}
