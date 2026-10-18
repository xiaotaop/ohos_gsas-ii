// B-side facade over CORE_API v1.0: the ArkTS CoreService that member A's
// RefinementPanel receives, wrapping the libgsas_core.so N-API module and
// member C's SandboxFileService in the call order mandated by
// MEMBER_C_HANDOFF §5 — runtime activated before initialize; beginJob inside
// the single-task gate before the worker starts; every artifact registered
// before job.completed reaches the page; the lease finished on ALL terminal
// states; interrupted jobs marked PROCESS_INTERRUPTED and never resumed.
// The failed/cancelled user log written before registration is C's
// recommended scheme (B03) and still awaits 组长 approval; private tracebacks
// never enter it.
// All dependencies are injected so host tests can drive this facade without
// the native module.
import { fileIo as fs } from '@kit.CoreFileKit';
import { AppFile, ArtifactKind, CoreConfig, FileServiceError } from '../contracts/Files';
import { Artifact, CancelAck, CoreError, CoreEvent, CoreInfo, CoreService, JobAccepted,
  JobSnapshot, RefinementRequest } from '../model/Refinement';
import { RawFileSource, RuntimeInstaller } from './RuntimeInstaller';

/** Structural mirror of libgsas_core's index.d.ts; injected, never imported here. */
export interface CoreNativeModule {
  setEventCallback(callback: ((eventJson: string) => void) | null): void;
  initializeCore(configJson: string): Promise<string>;
  acquireJob(jobId: string): void;
  releaseJob(jobId: string): void;
  startAcquiredJob(requestJson: string): string;
  cancelJob(jobId: string): string;
  getJobSnapshot(jobId: string): string;
  shutdownCore(): Promise<void>;
}

/** The SandboxFileService capabilities the facade needs, as an injectable seam. */
export interface CoreFileOps {
  getCoreConfig(): CoreConfig;
  listInterruptedJobs(): string[];
  beginJob(jobId: string, fileIds: string[]): Promise<void>;
  finishJob(jobId: string): Promise<void>;
  registerOutput(jobId: string, fileId: string, displayName: string, kind: ArtifactKind): Promise<AppFile>;
}

/** Persisted "active/recent" job id; preferences-backed in production. */
export interface JobIdStore {
  load(): Promise<string>;
  save(jobId: string): Promise<void>;
}

export interface CoreBridgeDeps {
  native: CoreNativeModule;
  files: CoreFileOps;
  runtime: RawFileSource;
  jobs: JobIdStore;
}

interface NativeErrorShape {
  code?: string;
  message?: string;
  retryable?: boolean;
}

const JOB_ID = /^job_[A-Za-z0-9_-]{8,64}$/;
const FILE_ID = /^file_[A-Za-z0-9_-]{8,64}$/;
const OPERATION = 'powder-refinement';
const RUNTIME_SUFFIX = '/runtime';
const LOG_NAME = 'job-log.txt';
const LOG_ID_PREFIX = 'file_log_';
const MAX_LOG_LINES = 400;
const MAX_LOG_LINE = 500;
const MAX_LOG_BYTES = 65536;

function toArtifactKind(kind: string): ArtifactKind | undefined {
  if (kind === 'project') { return 'project'; }
  if (kind === 'result') { return 'result'; }
  if (kind === 'log') { return 'log'; }
  return undefined;
}

export class CoreBridgeService implements CoreService {
  private native: CoreNativeModule;
  private files: CoreFileOps;
  private runtime: RawFileSource;
  private jobs: JobIdStore;
  private config: CoreConfig | undefined = undefined;
  private info: CoreInfo | undefined = undefined;
  private listeners: ((event: CoreEvent) => void)[] = [];
  private queue: Promise<void> = Promise.resolve();
  private logLines: Map<string, string[]> = new Map();
  private interrupted: Set<string> = new Set();

  constructor(deps: CoreBridgeDeps) {
    this.native = deps.native;
    this.files = deps.files;
    this.runtime = deps.runtime;
    this.jobs = deps.jobs;
  }

  async initialize(config: CoreConfig): Promise<CoreInfo> {
    if (this.info !== undefined) {
      // Re-initializing with the same roots is a no-op (the page may retry
      // openCore); a different sandbox would need a fresh interpreter anyway.
      if (this.config !== undefined && this.config.runtimeRoot === config.runtimeRoot) { return this.info; }
      throw new FileServiceError('CORE_ALREADY_INITIALIZED', '核心已按另一配置初始化，请重启应用。');
    }
    CoreBridgeService.checkConfig(config);
    const filesDir = config.runtimeRoot.substring(0, config.runtimeRoot.length - RUNTIME_SUFFIX.length);
    try {
      await RuntimeInstaller.install(this.runtime, filesDir);
    } catch (error) {
      if (error instanceof FileServiceError) { throw error; }
      throw new FileServiceError('RUNTIME_UNPACK_FAILED', '运行时装配未完成，请重试。', true);
    }
    this.config = config;
    for (const jobId of this.files.listInterruptedJobs()) {
      // §5 step 7: mark the persisted lease as interrupted, then release it.
      // Computation is never resumed; the snapshot layer answers instead.
      this.interrupted.add(jobId);
      try { this.native.releaseJob(jobId); } catch { /* no ledger entry in a new process */ }
      try { await this.files.finishJob(jobId); } catch { /* retried at next start */ }
    }
    this.native.setEventCallback((eventJson: string): void => this.observe(eventJson));
    let infoJson: string;
    try {
      infoJson = await this.native.initializeCore(JSON.stringify(config));
    } catch (error) {
      CoreBridgeService.detach(this.native);
      this.config = undefined;
      throw CoreBridgeService.wrapNative(error);
    }
    const info = JSON.parse(infoJson) as CoreInfo;
    if (info.schemaVersion !== '1.0' || info.ready !== true || !Array.isArray(info.supportedRecipes)) {
      CoreBridgeService.detach(this.native);
      this.config = undefined;
      throw new FileServiceError('UNSUPPORTED_SCHEMA', '核心信息不符合 v1.0 契约。');
    }
    this.info = info;
    return info;
  }

  /** The persisted active/recent job id, when it still looks like one. */
  async restoreJobId(): Promise<string> {
    const stored = await this.jobs.load();
    return JOB_ID.test(stored) ? stored : '';
  }

  /** Stops the worker (waiting for any in-flight execute) and closes the facade. */
  async shutdown(): Promise<void> {
    if (this.info === undefined) { return; }
    this.info = undefined;
    this.config = undefined;
    try {
      await this.native.shutdownCore();
    } catch (error) {
      throw CoreBridgeService.wrapNative(error);
    } finally {
      // Events already queued for delivery still run; handlers stay safe
      // because config-dependent steps degrade to best-effort.
      CoreBridgeService.detach(this.native);
    }
  }

  onEvent(listener: (event: CoreEvent) => void): () => void {
    this.listeners.push(listener);
    return (): void => {
      const index = this.listeners.indexOf(listener);
      if (index >= 0) { this.listeners.splice(index, 1); }
    };
  }

  async startRefinement(request: RefinementRequest): Promise<JobAccepted> {
    const info = this.info;
    if (info === undefined) { throw new FileServiceError('CORE_NOT_READY', '计算核心尚未就绪，请稍后重试。', true); }
    CoreBridgeService.checkRequest(request, info);
    const fileIds = CoreBridgeService.inputFileIds(request);
    try {
      this.native.acquireJob(request.jobId);  // gate: BUSY / JOB_ALREADY_EXISTS
    } catch (error) {
      throw CoreBridgeService.wrapNative(error);
    }
    try {
      await this.files.beginJob(request.jobId, fileIds);
      let acceptedJson: string;
      try {
        acceptedJson = this.native.startAcquiredJob(JSON.stringify(request));
      } catch (error) {
        // A synchronous rejection emits no event (§8): both gates close here.
        throw CoreBridgeService.wrapNative(error);
      }
      const accepted = JSON.parse(acceptedJson) as JobAccepted;
      if (accepted.schemaVersion !== '1.0' || accepted.jobId !== request.jobId || accepted.state !== 'queued') {
        throw new FileServiceError('UNSUPPORTED_SCHEMA', '任务回执不符合 v1.0 契约。');
      }
      await this.jobs.save(request.jobId);
      return { schemaVersion: '1.0', jobId: accepted.jobId, state: accepted.state, acceptedAt: accepted.acceptedAt };
    } catch (error) {
      try { await this.files.finishJob(request.jobId); } catch { /* best effort */ }
      try { this.native.releaseJob(request.jobId); } catch { /* best effort */ }
      throw CoreBridgeService.wrapNative(error);  // pass-through keeps contract codes
    }
  }

  async cancelJob(jobId: string): Promise<CancelAck> {
    if (this.info === undefined) { throw new FileServiceError('CORE_NOT_READY', '计算核心尚未就绪，请稍后重试。', true); }
    if (!JOB_ID.test(jobId)) { throw new FileServiceError('INVALID_REQUEST', '任务标识无效。'); }
    let ackJson: string;
    try {
      ackJson = this.native.cancelJob(jobId);
    } catch (error) {
      throw CoreBridgeService.wrapNative(error);
    }
    const ack = JSON.parse(ackJson) as CancelAck;
    // The bridge ack may omit fields the contract fills in at the boundary.
    return { schemaVersion: '1.0', jobId: typeof ack.jobId === 'string' ? ack.jobId : jobId,
      requested: ack.requested === true };
  }

  async getJobSnapshot(jobId: string): Promise<JobSnapshot> {
    if (!JOB_ID.test(jobId)) { throw new FileServiceError('INVALID_REQUEST', '任务标识无效。'); }
    if (this.interrupted.has(jobId)) {
      // Synthesized exactly like a §8 pre-event failure: seq-0 job.failed.
      const error: CoreError = { code: 'PROCESS_INTERRUPTED', message: '上次任务因进程退出而中断。', retryable: true };
      return { jobId, state: 'failed', lastSequence: 0, percent: 0, stage: null,
        terminal: { type: 'job.failed', payload: { error } } };
    }
    if (this.info === undefined) { throw new FileServiceError('CORE_NOT_READY', '计算核心尚未就绪，请稍后重试。', true); }
    let snapshotJson: string;
    try {
      snapshotJson = this.native.getJobSnapshot(jobId);
    } catch (error) {
      throw CoreBridgeService.wrapNative(error);
    }
    return JSON.parse(snapshotJson) as JobSnapshot;
  }

  /** Support/test hook: wait until queued event handling has fully drained. */
  async flushEvents(): Promise<void> {
    let previous: Promise<void>;
    do {
      previous = this.queue;
      await previous;
    } while (previous !== this.queue);
  }

  private observe(eventJson: string): void {
    let parsed: CoreEvent | undefined;
    try {
      parsed = CoreBridgeService.parseEvent(eventJson);
    } catch {
      parsed = undefined;
    }
    const event = parsed;  // const keeps the narrowing inside the queued closure
    if (event === undefined) { return; }
    const handled = this.queue.then(async (): Promise<void> => { await this.handle(event); });
    this.queue = handled.then((): void => {}, (): void => {});
  }

  private async handle(event: CoreEvent): Promise<void> {
    if (event.type === 'job.completed') {
      await this.registerArtifacts(event);
      this.dispatch(event);
      await this.cleanupTerminal(event.jobId);
      return;
    }
    if (event.type === 'job.failed' || event.type === 'job.cancelled') {
      await this.writeUserLog(event);
      this.dispatch(event);
      await this.cleanupTerminal(event.jobId);
      return;
    }
    if (event.type === 'job.log') { this.remember(event); }
    this.dispatch(event);
  }

  private dispatch(event: CoreEvent): void {
    for (const listener of this.listeners.slice()) {
      try { listener(event); } catch { /* A-side listener failures never abort delivery. */ }
    }
  }

  /** §5 steps 4-5: register real outputs first, then deliver only what the
   * page can query/export; unregistered entries are pruned from the result. */
  private async registerArtifacts(event: CoreEvent): Promise<void> {
    const result = event.payload.result;
    if (result === undefined || !Array.isArray(result.artifacts)) { return; }
    const kept: Artifact[] = [];
    for (const artifact of result.artifacts) {
      const kind = toArtifactKind(artifact.kind);
      if (kind === undefined || !FILE_ID.test(artifact.fileId) || typeof artifact.displayName !== 'string'
        || artifact.displayName.length === 0 || artifact.displayName.length > 180) { continue; }
      try {
        await this.files.registerOutput(event.jobId, artifact.fileId, artifact.displayName, kind);
        kept.push(artifact);
      } catch { /* an unexportable artifact must not swallow the result */ }
    }
    result.artifacts = kept;
  }

  /** §5 step 6: failed/cancelled first land a sanitized user log in outputs. */
  private async writeUserLog(event: CoreEvent): Promise<void> {
    const config = this.config;
    if (config === undefined) { return; }  // closed mid-event; dispatch still runs
    const text = this.buildUserLog(event, config);
    if (text.length === 0) { return; }
    const path = `${config.outputRoot}/${event.jobId}/${LOG_NAME}`;
    const fileId = `${LOG_ID_PREFIX}${event.jobId.substring(4)}`;
    try {
      const file = await fs.open(path, fs.OpenMode.CREATE | fs.OpenMode.WRITE_ONLY
        | fs.OpenMode.TRUNC | fs.OpenMode.NOFOLLOW);
      try {
        await fs.write(file.fd, text);
        await fs.fsync(file.fd);
      } finally {
        await fs.close(file);
      }
      await this.files.registerOutput(event.jobId, fileId, LOG_NAME, 'log');
    } catch { /* best effort: the terminal event must still reach the page */ }
  }

  private async cleanupTerminal(jobId: string): Promise<void> {
    this.logLines.delete(jobId);
    try { await this.files.finishJob(jobId); } catch { /* retried; outputs survive */ }
    try { this.native.releaseJob(jobId); } catch { /* best effort */ }
    try { await this.jobs.save(jobId); } catch { /* in-memory state stays usable */ }
  }

  private remember(event: CoreEvent): void {
    const message = event.payload.message;
    if (typeof message !== 'string' || message.length === 0) { return; }
    const clean = message.replace(/[\x00-\x08\x0B-\x1F\x7F]/g, ' ').substring(0, MAX_LOG_LINE);
    let lines = this.logLines.get(event.jobId);
    if (lines === undefined) { lines = []; this.logLines.set(event.jobId, lines); }
    lines.push(clean);
    if (lines.length > MAX_LOG_LINES) { lines.splice(0, lines.length - MAX_LOG_LINES); }
  }

  /** Only contract-safe text: no detail/traceback, no sandbox-root strings. */
  private buildUserLog(event: CoreEvent, config: CoreConfig): string {
    const lines: string[] = ['GSAS-II HarmonyOS 任务日志', `jobId: ${event.jobId}`,
      event.type === 'job.cancelled' ? '状态: 已取消' : '状态: 失败'];
    const error = event.payload.error as CoreError | undefined;
    if (error !== undefined && typeof error.code === 'string' && error.code.length > 0) {
      lines.push(`错误: ${error.code}: ${typeof error.message === 'string' ? error.message : ''}`);
    }
    const reason = event.payload.reason;
    if (typeof reason === 'string' && reason.length > 0) {
      lines.push(`取消原因: ${reason.replace(/[\x00-\x08\x0B-\x1F\x7F]/g, ' ').substring(0, MAX_LOG_LINE)}`);
    }
    lines.push('--- 任务消息 ---');
    const roots: string[] = [config.runtimeRoot, config.workspaceRoot, config.outputRoot];
    let used = 0;
    const remembered = this.logLines.get(event.jobId);
    if (remembered !== undefined) {
      for (const line of remembered) {
        let unsafe = false;
        for (const root of roots) { if (root.length > 0 && line.includes(root)) { unsafe = true; break; } }
        if (unsafe) { continue; }
        if (used > MAX_LOG_BYTES) { lines.push('（日志过长，后续消息已省略）'); break; }
        lines.push(line);
        used += line.length;
      }
    }
    return lines.join('\n') + '\n';
  }

  private static detach(native: CoreNativeModule): void {
    try { native.setEventCallback(null); } catch { /* channel already gone */ }
  }

  private static checkConfig(config: CoreConfig): void {
    if (config.schemaVersion !== '1.0' || config.maxConcurrentJobs !== 1
      || !config.runtimeRoot.endsWith(RUNTIME_SUFFIX)) {
      throw new FileServiceError('INVALID_REQUEST', '核心配置不符合 v1.0 契约。');
    }
    const roots: string[] = [config.runtimeRoot, config.workspaceRoot, config.outputRoot];
    for (const root of roots) {
      if (!root.startsWith('/') || root.split('/').includes('..')) {
        throw new FileServiceError('INVALID_REQUEST', '核心配置目录无效。');
      }
    }
  }

  private static checkRequest(request: RefinementRequest, info: CoreInfo): void {
    if (request.schemaVersion !== '1.0' || request.operation !== OPERATION) {
      throw new FileServiceError('INVALID_REQUEST', '精修请求不符合 v1.0 契约。');
    }
    if (!JOB_ID.test(request.jobId)) { throw new FileServiceError('INVALID_REQUEST', '任务标识无效。'); }
    if (!info.supportedRecipes.includes(request.recipeId)) {
      throw new FileServiceError('UNSUPPORTED_RECIPE', '核心不支持此精修流程。');
    }
    if (!Number.isSafeInteger(request.options.cycleCount) || request.options.cycleCount < 0
      || request.options.cycleCount > 50) {
      throw new FileServiceError('INVALID_REQUEST', 'Max cycles 必须是 0～50 的整数。');
    }
    const name = request.output.projectName;
    if (name.length === 0 || name.length > 104 || !name.endsWith('.gpx') || name.includes('/') || name.includes('\\')) {
      throw new FileServiceError('INVALID_REQUEST', '请填写不含路径的 .gpx 输出文件名。');
    }
  }

  /** The frozen five-shape request binds exactly these five input ids. */
  private static inputFileIds(request: RefinementRequest): string[] {
    const ids: string[] = [];
    for (const histogram of request.inputs.histograms) {
      ids.push(histogram.dataFileId, histogram.instrumentFileId);
    }
    ids.push(request.inputs.phase.fileId);
    for (const id of ids) {
      if (!FILE_ID.test(id)) { throw new FileServiceError('INVALID_REQUEST', '输入文件标识无效。'); }
    }
    if (ids.length < 5) {
      throw new FileServiceError('INVALID_REQUEST', '五阶段请求必须绑定两份数据、两份仪器参数和一个相文件。');
    }
    const unique: string[] = [];
    for (const id of ids) { if (!unique.includes(id)) { unique.push(id); } }
    return unique;
  }

  private static parseEvent(eventJson: string): CoreEvent | undefined {
    const value = JSON.parse(eventJson) as CoreEvent;
    if (value === null || typeof value.jobId !== 'string' || !JOB_ID.test(value.jobId)
      || !Number.isSafeInteger(value.sequence) || value.sequence < 0
      || typeof value.type !== 'string' || value.type.length === 0
      || value.payload === null || value.payload === undefined) {
      return undefined;
    }
    return value;
  }

  private static wrapNative(error: Object): FileServiceError {
    if (error instanceof FileServiceError) { return error; }
    // Native rejections are Error objects carrying the frozen contract's
    // code/retryable; unknown shapes collapse to INTERNAL_ERROR, never to
    // arbitrary exception text (A-side callError keeps the same rule).
    const shape = error as NativeErrorShape;
    const code = typeof shape.code === 'string' && /^[A-Z][A-Z0-9_]{1,63}$/.test(shape.code)
      ? shape.code : 'INTERNAL_ERROR';
    const message = typeof shape.message === 'string' && messageIsSafe(shape.message)
      ? shape.message : '核心调用未完成，请重试。';
    const retryable = shape.retryable === true || code === 'INTERNAL_ERROR';
    return new FileServiceError(code, message, retryable);
  }
}

function messageIsSafe(message: string): boolean {
  return message.length > 0 && message.length <= 512 && !/[\x00-\x08\x0B-\x1F\x7F]/.test(message);
}
