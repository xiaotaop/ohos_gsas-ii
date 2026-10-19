// A-side v1.1 UI projection (B-confirmed shared snapshot/error types; the
// v1.1 addition is the optional registered `artifacts` on failed/cancelled
// terminal payloads — B03).
import { CoreConfig, FileServiceError } from '../contracts/Files';
import { RefinementInputs } from './RefinementInputs';

export interface RefinementOptions { cycleCount: number; validateAgainstBaseline?: boolean; }
export interface RefinementOutput { projectName: string; overwrite: boolean; }
export interface RefinementRequest {
  schemaVersion: string; jobId: string; operation: string; recipeId: string;
  inputs: RefinementInputs; options: RefinementOptions; output: RefinementOutput;
}
export interface CoreInfo {
  schemaVersion: string; ready: boolean; pythonVersion: string;
  gsasCommit: string; supportedRecipes: string[];
}
export interface JobAccepted { schemaVersion: string; jobId: string; state: string; acceptedAt: string; }
export interface CancelAck { schemaVersion: string; jobId: string; requested: boolean; }
export interface CoreError { code: string; message: string; retryable: boolean; detail?: string; }
export interface StageResult { name: string; rwpByHistogram: Record<string, number>; }
export interface Artifact { fileId: string; kind: string; displayName: string; mediaType: string; }
export interface Validation { performed: boolean; passed: boolean | null; }
export interface RefinementResult {
  recipeId: string; upstreamCommit: string; elapsedSeconds: number; stages: StageResult[];
  preferredOrientation?: Record<string, number>; validation?: Validation; artifacts: Artifact[];
}
export interface EventPayload {
  state?: string; stage?: string; stageIndex?: number; stageCount?: number; percent?: number;
  message?: string; level?: string; source?: string; result?: RefinementResult;
  error?: CoreError; reason?: string;
  // B03: present only on failed/cancelled terminals whose sanitized log was
  // registered before the terminal event; every entry has kind 'log'.
  artifacts?: Artifact[];
}
export interface CoreEvent {
  schemaVersion: string; eventId: string; jobId: string; sequence: number;
  timestamp: string; type: string; payload: EventPayload;
}
export interface TerminalSummary { type: string; payload: EventPayload; }
export interface JobSnapshot {
  jobId: string; state: string; lastSequence: number; percent: number; stage: string | null;
  terminal: TerminalSummary | null;
}
export interface CoreService {
  initialize(config: CoreConfig): Promise<CoreInfo>;
  startRefinement(request: RefinementRequest): Promise<JobAccepted>;
  cancelJob(jobId: string): Promise<CancelAck>;
  getJobSnapshot(jobId: string): Promise<JobSnapshot>;
  onEvent(listener: (event: CoreEvent) => void): () => void;
}
export const STAGE_LABELS: Record<string, string> = {
  'preparing': '准备任务', 'reading_files': '读取文件', 'before_fitting': '初始拟合',
  'scale_and_background': '比例与背景', 'cells': '晶胞参数',
  'microstrain_displacement_atoms': '微应变、位移与原子参数',
  'preferred_orientation': '择优取向', 'saving': '保存结果', 'completed': '完成'
};
export function stageLabel(stage: string): string { return STAGE_LABELS[stage] || stage; }
export function isActive(state: string): boolean {
  return ['queued', 'validating', 'running', 'saving', 'cancelling'].includes(state);
}
export function isTerminal(state: string): boolean {
  return ['succeeded', 'failed', 'cancelled'].includes(state);
}

// Explicit per-run inputs. ParameterPanel drafts are not a recipe or its defaults.
export function prepareRefinementRequest(jobId: string, inputs: RefinementInputs,
  phaseName: string, cycles: string, projectName: string): RefinementRequest {
  if (!/^job_[A-Za-z0-9_-]{8,64}$/.test(jobId) || !/^\d{1,2}$/.test(cycles.trim()) || Number(cycles) > 50) {
    throw new FileServiceError('INVALID_REQUEST', 'Max cycles 必须明确填写为 0～50 的整数。');
  }
  const name = projectName.trim(); const phase = phaseName.trim();
  if (!/^[^/\\\\]{1,100}\.gpx$/.test(name) || /[\x00-\x1f]/.test(name) || !phase || phase.length > 80) {
    throw new FileServiceError('INVALID_REQUEST', '请填写相名及不含路径的 .gpx 输出文件名（扩展名前最多 100 字符）。');
  }
  const frozen = JSON.parse(JSON.stringify(inputs)) as RefinementInputs;
  frozen.phase.name = phase;
  return { 'schemaVersion': '1.0', jobId, 'operation': 'powder-refinement', 'recipeId': 'powder-five-stage-v1',
    inputs: frozen, options: { cycleCount: Number(cycles) }, output: { projectName: name, overwrite: false } };
}

function callError(error: Object): CoreError {
  // Error and plain Promise rejection shapes are not yet shared by B/C. Preserve
  // known codes using local safe text, never arbitrary exception messages/detail.
  const candidate = error as CoreError;
  const messages: Record<string, string> = {
    'INVALID_REQUEST': '精修请求无效，请检查输入和参数。', 'UNSUPPORTED_SCHEMA': '核心接口版本不匹配。',
    'UNSUPPORTED_RECIPE': '核心不支持此精修流程。', 'JOB_ALREADY_EXISTS': '任务编号重复，请重新提交。',
    'CORE_NOT_READY': '计算核心尚未就绪，请稍后重试。', 'CORE_ALREADY_INITIALIZED': '核心初始化配置不一致。',
    'BUSY': '已有任务运行，请等待该任务结束。', 'FILE_NOT_FOUND': '输入文件不存在，请重新选择。',
    'FILE_HASH_MISMATCH': '输入文件已变化，请重新导入。', 'UNSUPPORTED_FILE': '不支持此文件格式。',
    'INVALID_INSTRUMENT_FILE': '仪器参数文件无法读取。', 'INVALID_PHASE_FILE': '相文件无法读取。',
    'REFINEMENT_FAILED': '精修失败，请检查输入。', 'OUTPUT_WRITE_FAILED': '无法保存结果，请检查可用空间。',
    'JOB_NOT_FOUND': '未找到此任务。', 'PROCESS_INTERRUPTED': '上次任务因进程退出而中断。',
    'INTERNAL_ERROR': '任务未能启动，请稍后重试。'
  };
  const code = candidate && typeof candidate.code === 'string' && Object.keys(messages).includes(candidate.code) ? candidate.code : 'INTERNAL_ERROR';
  return { code, message: messages[code], retryable: ['CORE_NOT_READY', 'BUSY', 'OUTPUT_WRITE_FAILED', 'PROCESS_INTERRUPTED', 'INTERNAL_ERROR'].includes(code) };
}

export class RefinementView {
  jobId: string = '';
  state: string = 'idle';
  sequence: number = -1;
  percent: number = 0;
  stage: string = '';
  message: string = '请选择输入文件并填写本次精修设置。';
  history: string[] = [];
  result?: RefinementResult;
  error?: CoreError;
  // Registered log artifacts carried by a failed/cancelled terminal payload
  // (B03). Only these entries may be exported; the view never synthesizes a
  // fileId from names, paths or history.
  terminalArtifacts?: Artifact[];
}

// Pure UI transition; old jobs, duplicate events and post-terminal events cannot change the screen.
export function receiveEvent(view: RefinementView, event: CoreEvent): RefinementView {
  if (event.jobId !== view.jobId || event.sequence <= view.sequence || isTerminal(view.state)) {
    return view;
  }
  return applyPayload(view, event.sequence, event.type, event.payload);
}

function applyPayload(view: RefinementView, sequence: number, type: string, p: EventPayload): RefinementView {
  const next = new RefinementView();
  next.jobId = view.jobId;
  next.state = view.state;
  next.sequence = sequence;
  next.percent = view.percent;
  next.stage = view.stage;
  next.message = view.message;
  next.result = view.result;
  next.error = view.error;
  next.terminalArtifacts = view.terminalArtifacts;
  next.history = view.history.slice();
  if (type === 'job.accepted') {
    next.state = 'queued'; next.message = '任务已接受，等待开始';
  } else if (type === 'job.progress') {
    next.state = p.state || next.state;
    next.percent = Math.max(next.percent, p.percent || 0);
    next.stage = p.stage || '';
    next.message = p.message || stageLabel(next.stage);
  } else if (type === 'job.log') {
    next.history.push(p.message || '');
    return next;
  } else if (type === 'job.completed') {
    next.state = 'succeeded'; next.percent = 100; next.result = p.result;
    next.stage = 'completed';
    next.message = '五阶段精修已完成';
  } else if (type === 'job.failed') {
    next.state = 'failed'; next.error = p.error;
    next.terminalArtifacts = Array.isArray(p.artifacts) ? p.artifacts.slice() : undefined;
    next.message = p.error ? p.error.message : '任务执行失败';
  } else if (type === 'job.cancelled') {
    next.state = 'cancelled'; next.message = p.reason || '任务已取消';
    next.terminalArtifacts = Array.isArray(p.artifacts) ? p.artifacts.slice() : undefined;
  }
  next.history.push(next.message);
  return next;
}

// Subscribe first, then merge a snapshot: an older response must not erase newer events.
// Snapshots have no eventId/timestamp; do not fabricate a CoreEvent for restoration.
export function receiveSnapshot(view: RefinementView, snapshot: JobSnapshot): RefinementView {
  if (snapshot.jobId !== view.jobId || snapshot.lastSequence < view.sequence || isTerminal(view.state)) {
    return view;
  }
  if (snapshot.lastSequence === view.sequence && view.sequence >= 0) { return view; }
  const next = applyPayload(view, snapshot.lastSequence, 'job.progress', {
    state: snapshot.state, percent: snapshot.percent, stage: snapshot.stage || '',
    message: snapshot.stage ? stageLabel(snapshot.stage) : '等待执行'
  });
  if (snapshot.terminal) {
    const terminal = applyPayload(next, snapshot.lastSequence, snapshot.terminal.type, snapshot.terminal.payload);
    terminal.history = view.history.slice();
    return terminal;
  }
  next.history = view.history.slice();
  return next;
}

// Page-owned observation/commands; the injected CoreService remains application-owned.
// initialize/config, active-job discovery and process persistence belong to B/C.
export class RefinementSession {
  view: RefinementView = new RefinementView();
  cancelRequested: boolean = false;
  notice: string = '';
  private unsubscribe?: () => void;
  private generation: number = 0;
  private core: CoreService;
  private changed: () => void;

  constructor(core: CoreService, changed: () => void) {
    this.core = core; this.changed = changed;
  }

  async connect(jobId: string = ''): Promise<void> {
    this.disconnect();
    const generation = this.generation;
    this.view = new RefinementView();
    this.view.jobId = jobId;
    if (jobId) {
      this.view.state = 'queued';
      this.view.message = '正在恢复任务状态';
    }
    this.cancelRequested = false;
    this.notice = '';
    this.unsubscribe = this.core.onEvent((event: CoreEvent) => {
      if (generation !== this.generation) { return; }
      this.view = receiveEvent(this.view, event);
      if (!isActive(this.view.state)) { this.cancelRequested = false; }
      this.changed();
    });
    this.changed();
    if (!jobId) { return; }
    try {
      const snapshot = await this.core.getJobSnapshot(jobId);
      if (generation !== this.generation || this.view.jobId !== jobId) { return; }
      this.view = receiveSnapshot(this.view, snapshot);
      this.cancelRequested = isActive(this.view.state) &&
        (this.cancelRequested || this.view.state === 'cancelling');
    } catch (error) {
      if (generation !== this.generation || this.view.jobId !== jobId) { return; }
      // §4.2: an unknown or already-released historic jobId degrades to a
      // neutral notice; the page must never claim PROCESS_INTERRUPTED or any
      // other state from this failure.
      if ((error as CoreError).code === 'JOB_NOT_FOUND') {
        this.view = new RefinementView();
        this.notice = '该任务编号没有可用记录（旧进程任务或已清理），请提交新任务。';
      } else {
        this.notice = '无法读取任务快照，请重新连接或等待后续事件。';
      }
    }
    this.changed();
  }

  disconnect(): void {
    this.generation++;
    if (this.unsubscribe) { this.unsubscribe(); this.unsubscribe = undefined; }
  }

  async start(request: RefinementRequest): Promise<void> {
    if (!this.unsubscribe || isActive(this.view.state)) { return; }
    const generation = this.generation;
    this.view = new RefinementView();
    this.view.jobId = request.jobId;
    this.view.state = 'queued';
    this.view.message = '正在提交任务';
    this.cancelRequested = false;
    this.notice = '';
    this.changed();
    try {
      const accepted = await this.core.startRefinement(request);
      if (generation !== this.generation || this.view.jobId !== request.jobId) { return; }
      if (accepted.jobId !== request.jobId) {
        this.notice = '服务返回了不同的任务 ID，请核对核心接口。';
        this.changed();
      }
      // Accepted is not a new state: events may already have completed the job.
    } catch (error) {
      if (generation !== this.generation || this.view.jobId !== request.jobId) { return; }
      if (this.view.sequence < 0) {
        this.view = applyPayload(this.view, -1, 'job.failed', {
          error: callError(error)
        });
      } else if (isActive(this.view.state)) {
        this.notice = '启动响应异常，继续等待已接收任务的状态。';
      }
      this.changed();
    }
  }

  async cancel(): Promise<void> {
    if (!this.unsubscribe || !isActive(this.view.state) || this.cancelRequested) { return; }
    const generation = this.generation;
    const jobId = this.view.jobId;
    this.cancelRequested = true;
    this.notice = '';
    this.changed();
    try {
      const ack = await this.core.cancelJob(jobId);
      if (generation !== this.generation || this.view.jobId !== jobId || !isActive(this.view.state)) { return; }
      if (!ack.requested || ack.jobId !== jobId) {
        this.cancelRequested = false;
        this.notice = '服务未确认取消请求，请重试或等待任务结束。';
      }
    } catch {
      if (generation !== this.generation || this.view.jobId !== jobId || !isActive(this.view.state)) { return; }
      this.cancelRequested = false;
      this.notice = '取消请求未能送达，请重试或等待任务结束。';
    }
    this.changed();
  }
}
