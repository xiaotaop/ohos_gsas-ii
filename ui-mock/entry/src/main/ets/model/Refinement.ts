// UI-facing v1.0 structures, sourced from docs/CORE_API.md and contracts/*.json.
// FileRole remains pending. Snapshot mirrors bridge/service.py for host integration;
// it is a local projection, not an approved replacement for B/C's shared types.
export interface HistogramInput {
  id: string; role: string; dataFileId: string; instrumentFileId: string; formatHint: string;
}
export interface PhaseInput { id: string; name: string; fileId: string; }
export interface RefinementInputs { histograms: HistogramInput[]; phase: PhaseInput; }
export interface RefinementOptions { cycleCount: number; validateAgainstBaseline?: boolean; }
export interface RefinementOutput { projectName: string; overwrite: boolean; }
export interface RefinementRequest {
  schemaVersion: string; jobId: string; operation: string; recipeId: string;
  inputs: RefinementInputs; options: RefinementOptions; output: RefinementOutput;
}
export interface CoreConfig {
  schemaVersion: string; runtimeRoot: string; workspaceRoot: string;
  outputRoot: string; maxConcurrentJobs: number; logLevel: string;
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
export interface AppFile { fileId: string; displayName: string; role: string; size: number; sha256: string; }
export interface FileService {
  importFile(sourceUri: string, role: string): Promise<AppFile>;
  getFile(fileId: string): Promise<AppFile>;
  deleteFile(fileId: string): Promise<void>;
  exportFile(fileId: string, destinationUri: string): Promise<void>;
}
export interface MockData {
  request: RefinementRequest; success: CoreEvent[]; failed: CoreEvent[]; cancelled: CoreEvent[];
}

export const STAGE_LABELS: Record<string, string> = {
  preparing: '准备任务', reading_files: '读取文件', before_fitting: '初始拟合',
  scale_and_background: '比例与背景', cells: '晶胞参数',
  microstrain_displacement_atoms: '微应变、位移与原子参数',
  preferred_orientation: '择优取向', saving: '保存结果', completed: '完成'
};
export function stageLabel(stage: string): string { return STAGE_LABELS[stage] || stage; }
export function isActive(state: string): boolean {
  return ['queued', 'validating', 'running', 'saving', 'cancelling'].includes(state);
}
export function isTerminal(state: string): boolean {
  return ['succeeded', 'failed', 'cancelled'].includes(state);
}

export class RefinementView {
  jobId: string = '';
  state: string = 'idle';
  sequence: number = -1;
  percent: number = 0;
  stage: string = '';
  message: string = '选择一种演示场景，查看完整的任务状态变化。';
  history: string[] = [];
  result?: RefinementResult;
  error?: CoreError;
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
    next.message = p.error ? p.error.message : '任务执行失败';
  } else if (type === 'job.cancelled') {
    next.state = 'cancelled'; next.message = p.reason || '任务已取消';
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
    return applyPayload(next, snapshot.lastSequence, snapshot.terminal.type, snapshot.terminal.payload);
  }
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
    } catch {
      if (generation !== this.generation || this.view.jobId !== jobId) { return; }
      this.notice = '无法读取任务快照，请重新连接或等待后续事件。';
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
    } catch {
      if (generation !== this.generation || this.view.jobId !== request.jobId) { return; }
      if (this.view.sequence < 0) {
        this.view = applyPayload(this.view, -1, 'job.failed', {
          error: { code: 'INTERNAL_ERROR', message: '任务未能启动，请稍后重试。', retryable: true }
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

let requestNumber = 0;
export function newMockRequest(template: RefinementRequest): RefinementRequest {
  const request = JSON.parse(JSON.stringify(template)) as RefinementRequest;
  request.jobId = `job_mock_${Date.now()}_${++requestNumber}`;
  return request;
}

// Replays the checked-in payloads. No Python, filesystem or real computation is invoked.
export class MockCoreService implements CoreService {
  private listeners: ((event: CoreEvent) => void)[] = [];
  private snapshots: Map<string, JobSnapshot> = new Map();
  private activeId: string = '';
  private scenario: string = 'success';
  private timers: ReturnType<typeof setTimeout>[] = [];
  private cancelling: boolean = false;
  private lastProgress?: EventPayload;
  private configJson: string = '';
  private data: MockData;
  private delayMs: number;

  constructor(data: MockData, delayMs: number = 1000) {
    this.data = data; this.delayMs = delayMs;
  }

  setScenario(scenario: string): void {
    if (this.activeId) { throw new Error('BUSY'); }
    if (!['success', 'failed', 'cancelled'].includes(scenario)) { throw new Error('INVALID_REQUEST'); }
    this.scenario = scenario;
  }

  async initialize(config: CoreConfig): Promise<CoreInfo> {
    const value = JSON.stringify(config);
    if (this.configJson && value !== this.configJson) { throw new Error('CORE_ALREADY_INITIALIZED'); }
    this.configJson = value;
    return {
      schemaVersion: '1.0', ready: true, pythonVersion: 'mock (no Python)',
      gsasCommit: '2b4aba1bc44de63a3da9d4495944c3b99e389399',
      supportedRecipes: ['powder-five-stage-v1']
    };
  }

  onEvent(listener: (event: CoreEvent) => void): () => void {
    this.listeners.push(listener);
    return () => { this.listeners = this.listeners.filter(item => item !== listener); };
  }

  async startRefinement(request: RefinementRequest): Promise<JobAccepted> {
    if (this.activeId) { throw new Error('BUSY'); }
    if (this.snapshots.has(request.jobId)) { throw new Error('JOB_ALREADY_EXISTS'); }
    if (request.recipeId !== 'powder-five-stage-v1') { throw new Error('UNSUPPORTED_RECIPE'); }
    this.activeId = request.jobId;
    this.cancelling = false;
    this.lastProgress = undefined;
    const events = this.scenario === 'failed' ? this.data.failed :
      (this.scenario === 'cancelled' ? this.data.cancelled : this.data.success);
    this.emit(events[0]);
    // Cancellation replay pauses after accepted until the user requests cancellation.
    if (this.scenario !== 'cancelled') {
      events.slice(1).forEach((event, index) => {
        this.timers.push(setTimeout(() => this.emit(event), this.delayMs * (index + 1)));
      });
    }
    return { schemaVersion: '1.0', jobId: request.jobId, state: 'queued', acceptedAt: new Date().toISOString() };
  }

  async cancelJob(jobId: string): Promise<CancelAck> {
    if (jobId !== this.activeId) { throw new Error('JOB_NOT_FOUND'); }
    if (!this.cancelling) {
      this.cancelling = true;
      this.clearTimers();
      // Ack alone is not a terminal event; progress and terminal are delivered later.
      this.timers.push(setTimeout(() => this.emit(this.data.cancelled[1]), this.delayMs));
      this.timers.push(setTimeout(() => this.emit(this.data.cancelled[2]), this.delayMs * 2));
    }
    return { schemaVersion: '1.0', jobId, requested: true };
  }

  async getJobSnapshot(jobId: string): Promise<JobSnapshot> {
    const snapshot = this.snapshots.get(jobId);
    if (!snapshot) { throw new Error('JOB_NOT_FOUND'); }
    return JSON.parse(JSON.stringify(snapshot)) as JobSnapshot;
  }

  dispose(): void { this.clearTimers(); this.listeners = []; this.activeId = ''; }

  private clearTimers(): void {
    this.timers.forEach(timer => clearTimeout(timer)); this.timers = [];
  }

  private emit(template: CoreEvent): void {
    if (!this.activeId) { return; }
    const previous = this.snapshots.get(this.activeId);
    const event = JSON.parse(JSON.stringify(template)) as CoreEvent;
    event.jobId = this.activeId;
    event.sequence = previous ? previous.lastSequence + 1 : 0;
    event.eventId = `evt_${this.activeId}_${event.sequence}`;
    event.timestamp = new Date().toISOString();
    if (event.type === 'job.progress') {
      if (event.payload.state === 'cancelling' && this.lastProgress) {
        event.payload.stage = this.lastProgress.stage;
        event.payload.stageIndex = this.lastProgress.stageIndex;
        event.payload.stageCount = this.lastProgress.stageCount;
      }
      event.payload.percent = Math.max(previous ? previous.percent : 0, event.payload.percent || 0);
      this.lastProgress = event.payload;
    }
    const state = event.payload.state || (previous ? previous.state : 'queued');
    const snapshot: JobSnapshot = {
      jobId: event.jobId, lastSequence: event.sequence, state, terminal: null,
      percent: event.type === 'job.completed' ? 100 :
        (event.payload.percent === undefined ? (previous ? previous.percent : 0) : event.payload.percent),
      stage: event.type === 'job.completed' ? 'completed' :
        (event.payload.stage || (previous ? previous.stage : ''))
    };
    if (isTerminal(state)) {
      snapshot.terminal = { type: event.type, payload: event.payload };
      this.activeId = '';
      this.clearTimers();
    }
    this.snapshots.set(event.jobId, snapshot);
    this.listeners.slice().forEach(listener => listener(event));
  }
}
