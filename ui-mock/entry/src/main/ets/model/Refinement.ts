// UI-facing v1.0 structures, sourced from docs/CORE_API.md and contracts/*.json.
// FileRole and JobSnapshot are local projections pending B/C's shared type module.
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
export interface JobSnapshot {
  jobId: string; state: string; sequence: number; percent: number; stage: string;
  terminalEvent?: CoreEvent;
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
  const next = new RefinementView();
  next.jobId = view.jobId;
  next.state = view.state;
  next.sequence = event.sequence;
  next.percent = view.percent;
  next.stage = view.stage;
  next.message = view.message;
  next.result = view.result;
  next.error = view.error;
  next.history = view.history.slice();
  const p = event.payload;
  if (event.type === 'job.accepted') {
    next.state = 'queued'; next.message = '任务已接受，等待开始';
  } else if (event.type === 'job.progress') {
    next.state = p.state || next.state;
    next.percent = Math.max(next.percent, p.percent || 0);
    next.stage = p.stage || '';
    next.message = p.message || stageLabel(next.stage);
  } else if (event.type === 'job.log') {
    next.history.push(p.message || '');
    return next;
  } else if (event.type === 'job.completed') {
    next.state = 'succeeded'; next.percent = 100; next.result = p.result;
    next.stage = 'completed';
    next.message = '五阶段精修已完成';
  } else if (event.type === 'job.failed') {
    next.state = 'failed'; next.error = p.error;
    next.message = p.error ? p.error.message : '任务执行失败';
  } else if (event.type === 'job.cancelled') {
    next.state = 'cancelled'; next.message = p.reason || '任务已取消';
  }
  next.history.push(next.message);
  return next;
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
    event.sequence = previous ? previous.sequence + 1 : 0;
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
      jobId: event.jobId, sequence: event.sequence, state,
      percent: event.type === 'job.completed' ? 100 :
        (event.payload.percent === undefined ? (previous ? previous.percent : 0) : event.payload.percent),
      stage: event.type === 'job.completed' ? 'completed' :
        (event.payload.stage || (previous ? previous.stage : ''))
    };
    if (isTerminal(state)) {
      snapshot.terminalEvent = event;
      this.activeId = '';
      this.clearTimers();
    }
    this.snapshots.set(event.jobId, snapshot);
    this.listeners.slice().forEach(listener => listener(event));
  }
}
