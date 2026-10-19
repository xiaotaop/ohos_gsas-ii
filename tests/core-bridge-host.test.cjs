'use strict';

// Exercise the actual ArkTS CoreBridgeService against fake native/file-service
// seams and a real filesystem for the runtime install and the user log. This
// is not an ArkTS compiler and no substitute for HarmonyOS device tests, but
// it does pin the MEMBER_C_HANDOFF §5 call order that device integration
// otherwise discovers late.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const ts = require(process.env.GSAS_TYPESCRIPT_PATH || 'typescript');
const repo = path.resolve(__dirname, '..');
// The facade and installer guard absolute POSIX roots; keep the Windows host
// on the cwd-drive mapping so the suite also runs locally, not only on CI.
const posixJoin = (...parts) => parts.join('/');
const modules = new Map();
const platformError = error => {
  error.code = { ENOENT: 13900002, EACCES: 13900012, EEXIST: 13900015, ELOOP: 13900033 }[error.code] || 13900042;
  throw error;
};
const io = {
  OpenMode: { READ_ONLY: fs.constants.O_RDONLY, WRITE_ONLY: fs.constants.O_WRONLY,
    CREATE: fs.constants.O_CREAT, TRUNC: fs.constants.O_TRUNC, NOFOLLOW: fs.constants.O_NOFOLLOW },
  lstat: value => fs.promises.lstat(value),
  mkdir: value => fs.promises.mkdir(value),
  listFile: value => fs.promises.readdir(value),
  readText: value => fs.promises.readFile(value, 'utf8'),
  rename: (from, to) => fs.promises.rename(from, to),
  unlink: value => fs.promises.unlink(value),
  rmdir: value => fs.promises.rm(value, { recursive: true }),
  open: async (value, mode) => ({ fd: fs.openSync(value, mode) }),
  close: async file => fs.closeSync(typeof file === 'number' ? file : file.fd),
  fsync: async fd => fs.fsyncSync(fd),
  write: async (fd, bytes) => fs.writeSync(fd, Buffer.from(bytes)),
  access: async value => {
    try { await fs.promises.access(value); return true; }
    catch (error) {
      if (error.code !== 'ENOENT') throw error;
      return false;
    }
  }
};
for (const key of Object.keys(io)) {
  if (typeof io[key] !== 'function') continue;
  const operation = io[key];
  io[key] = async (...args) => { try { return await operation(...args); } catch (error) { return platformError(error); } };
}
const platform = {
  '@kit.CoreFileKit': { fileIo: io,
    hash: { hash: async value => crypto.createHash('sha256').update(await fs.promises.readFile(value)).digest('hex').toUpperCase() } },
  '@kit.ArkTS': { util: { generateRandomUUID: crypto.randomUUID,
    TextEncoder: class { encodeInto(text) { return new TextEncoder().encode(text); } } } },
  '@kit.LocalizationKit': {},
  '@kit.BasicServicesKit': {}
};
function loadServiceModule(filename) {
  if (modules.has(filename)) return modules.get(filename).exports;
  const module = { exports: {} }; modules.set(filename, module);
  const source = fs.readFileSync(filename, 'utf8');
  const compiled = ts.transpileModule(source, { fileName: filename,
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText;
  const requireModule = id => {
    if (platform[id]) return platform[id];
    if (id.startsWith('.')) return loadServiceModule(path.resolve(path.dirname(filename), `${id}.ets`));
    throw new Error(`Unexpected import: ${id}`);
  };
  vm.runInThisContext(`(function(require,module,exports){${compiled}\n})`, { filename })(requireModule, module, module.exports);
  return module.exports;
}
const { CoreBridgeService } = loadServiceModule(path.join(repo, 'app/entry/src/main/ets/services/CoreBridgeService.ets'));
const { RefinementSession } = loadServiceModule(path.join(repo, 'app/entry/src/main/ets/model/Refinement.ets'));

const sha = bytes => crypto.createHash('sha256').update(Buffer.from(bytes)).digest('hex');

class MemorySource {
  constructor(tree) { this.tree = new Map(Object.entries(tree)); }
  async readText(name) {
    const value = this.tree.get(name);
    if (value === undefined) throw new Error(`missing rawfile ${name}`);
    return Buffer.from(value).toString('utf8');
  }
  async readBytes(name) {
    const value = this.tree.get(name);
    if (value === undefined) throw new Error(`missing rawfile ${name}`);
    return new Uint8Array(value);
  }
}

function runtimeSource() {
  const files = { 'runtime/lib/python3.12/encodings/__init__.py': Buffer.from('# stub\n') };
  const entries = Object.keys(files).map(rel => ({ path: rel.slice('runtime/'.length),
    sha256: sha(files[rel]), size: files[rel].length }));
  const tree = { ...files, 'runtime/manifest.json': Buffer.from(JSON.stringify(
    { schemaVersion: 1, runtimeId: 'bridge-test.1', files: entries })) };
  return new MemorySource(tree);
}

// The native seam behaves like napi_core.cpp: JSON strings across, rejections
// are Error objects carrying the contract's code/retryable.
class FakeNative {
  constructor() {
    this.callback = null; this.configJson = null;
    this.calls = { acquire: [], release: [], start: [], cancel: [], snapshot: [], init: 0, shutdown: 0 };
    this.fail = {}; this.ack = JSON.stringify({ requested: true }); this.snapshots = {};
    this.ledger = {};  // mirrors napi_core.cpp's record_event for emitted events
    this.info = { schemaVersion: '1.0', ready: true, pythonVersion: '3.12.9',
      gsasCommit: '2b4aba1bc44de63a3da9d4495944c3b99e389399', supportedRecipes: ['powder-five-stage-v1'] };
  }
  setEventCallback(callback) { this.callback = callback; }
  async initializeCore(configJson) {
    this.calls.init += 1;
    if (this.fail.initializeCore) throw this.fail.initializeCore;
    this.configJson = configJson;
    return JSON.stringify(this.info);
  }
  acquireJob(jobId) { this.calls.acquire.push(jobId); if (this.fail.acquireJob) throw this.fail.acquireJob; }
  releaseJob(jobId) { this.calls.release.push(jobId); }
  startAcquiredJob(requestJson) {
    this.calls.start.push(requestJson);
    if (this.fail.startAcquiredJob) throw this.fail.startAcquiredJob;
    const jobId = JSON.parse(requestJson).jobId;
    return JSON.stringify({ schemaVersion: '1.0', jobId, state: 'queued', acceptedAt: '2026-10-18T00:00:00Z' });
  }
  cancelJob(jobId) { this.calls.cancel.push(jobId); if (this.fail.cancelJob) throw this.fail.cancelJob; return this.ack; }
  getJobSnapshot(jobId) {
    this.calls.snapshot.push(jobId);
    if (this.snapshots[jobId]) return this.snapshots[jobId];
    if (this.ledger[jobId]) return JSON.stringify(this.ledger[jobId]);
    const error = new Error('未找到此任务。'); error.code = 'JOB_NOT_FOUND'; error.retryable = false; throw error;
  }
  async shutdownCore() { this.calls.shutdown += 1; }
  emit(event) {
    const full = { schemaVersion: '1.0', eventId: `evt_${event.sequence}`,
      timestamp: '2026-10-18T00:00:00Z', ...event };
    let snapshot = this.ledger[full.jobId];
    if (!snapshot) {
      snapshot = { jobId: full.jobId, state: 'queued', lastSequence: -1, percent: 0, stage: null, terminal: null };
      this.ledger[full.jobId] = snapshot;
    }
    const terminalMap = { 'job.completed': 'succeeded', 'job.cancelled': 'cancelled', 'job.failed': 'failed' };
    if (Object.prototype.hasOwnProperty.call(terminalMap, full.type)) {
      if (!snapshot.terminal) {  // exactly one terminal, like the native ledger
        snapshot.terminal = { type: full.type, payload: full.payload };
        snapshot.state = terminalMap[full.type];
      }
    } else if (full.type === 'job.progress') {
      snapshot.state = full.payload.state;
      snapshot.percent = full.payload.percent;
      snapshot.stage = full.payload.stage;
    } else if (full.type === 'job.accepted') {
      snapshot.state = 'queued';
    }
    snapshot.lastSequence = full.sequence;
    this.callback(JSON.stringify(full));
  }
}

// Stands in for the parts of SandboxFileService the facade calls; register
// only files that really exist under outputs/<jobId>, like the real service.
class FakeFiles {
  constructor(root) {
    this.root = root; this.leases = new Map(); this.finished = []; this.registered = [];
    this.interrupted = []; this.sequence = []; this.failRegister = false;
    this.config = { schemaVersion: '1.0', runtimeRoot: posixJoin(root, 'runtime'),
      workspaceRoot: posixJoin(root, 'jobs'), outputRoot: posixJoin(root, 'outputs'),
      maxConcurrentJobs: 1, logLevel: 'info' };
  }
  getCoreConfig() { return { ...this.config }; }  // fresh object per call, like the real service
  listInterruptedJobs() { return this.interrupted.slice(); }
  async beginJob(jobId, fileIds) {
    this.sequence.push(`begin:${jobId}`);
    if (this.leases.has(jobId)) { const error = new Error('租约已存在。'); error.code = 'JOB_ALREADY_EXISTS'; throw error; }
    this.leases.set(jobId, fileIds.slice());
    fs.mkdirSync(posixJoin(this.root, 'outputs', jobId), { recursive: true });
  }
  async finishJob(jobId) { this.sequence.push(`finish:${jobId}`); this.finished.push(jobId); this.leases.delete(jobId); }
  async registerOutput(jobId, fileId, displayName, kind) {
    if (this.failRegister) { const error = new Error('登记服务不可用。'); error.code = 'INTERNAL_ERROR'; throw error; }
    const location = posixJoin(this.root, 'outputs', jobId, displayName);
    if (!fs.existsSync(location)) { const error = new Error('产物尚未写出。'); error.code = 'INVALID_REQUEST'; throw error; }
    this.sequence.push(`register:${displayName}`);
    this.registered.push({ jobId, fileId, displayName, kind });
    return { fileId, displayName, role: kind, size: 1, sha256: 'A'.repeat(64) };
  }
}

function makeFixture(action, options = {}) {
  // Drive-relative POSIX spelling keeps the production root checks intact on
  // Windows while confining test writes to this checkout's ignored build area.
  const temp = path.join(repo, 'app/build/host-tests').replace(/\\/g, '/').replace(/^[A-Za-z]:/, '');
  fs.mkdirSync(temp, { recursive: true });
  const base = fs.mkdtempSync(`${temp}/gsas-bridge-host-`);
  const root = posixJoin(base, 'files');
  fs.mkdirSync(root);
  const native = new FakeNative();
  const files = new FakeFiles(root);
  const store = { value: '', async load() { return store.value; }, async save(jobId) { store.value = jobId; } };
  files.interrupted = options.interrupted ?? [];
  const core = new CoreBridgeService({ native, files, runtime: runtimeSource(), jobs: store });
  return (async () => {
    try { await action({ core, native, files, store, root }); }
    finally { fs.rmSync(base, { recursive: true, force: true }); }
  })();
}

const JOB = 'job_0123456789abcdef';
const request = (jobId = JOB) => ({
  schemaVersion: '1.0', jobId, operation: 'powder-refinement', recipeId: 'powder-five-stage-v1',
  inputs: { histograms: [
    { id: 'xray', role: 'xray', dataFileId: 'file_xray_data_0001', instrumentFileId: 'file_xray_inst_0002', formatHint: 'GSAS powder' },
    { id: 'neutron', role: 'neutron', dataFileId: 'file_neut_data_0003', instrumentFileId: 'file_neut_inst_0004', formatHint: 'GSAS powder' }],
  phase: { id: 'phase', name: 'PbSO4', fileId: 'file_phase_cif_0005' } },
  options: { cycleCount: 1 }, output: { projectName: 'PbSO4-refined.gpx', overwrite: false }
});
const event = (type, jobId, sequence, payload) => ({ type, jobId, sequence, payload });

test('initialize unpacks runtime, boots once and is idempotent', () => makeFixture(async ({ core, native, files, root }) => {
  const info = await core.initialize(files.getCoreConfig());
  assert.equal(info.ready, true);
  assert.equal(native.configJson, JSON.stringify(files.getCoreConfig()));
  assert.equal(fs.readFileSync(posixJoin(root, 'runtime/lib/python3.12/encodings/__init__.py'), 'utf8'), '# stub\n');
  assert.equal(fs.readFileSync(posixJoin(root, 'runtime/.activation'), 'utf8').includes('bridge-test.1'), true);
  assert.equal(typeof native.callback, 'function');
  await core.initialize(files.getCoreConfig());
  assert.equal(native.calls.init, 1);
  const other = files.getCoreConfig();
  other.runtimeRoot = posixJoin(root, 'elsewhere/runtime');
  await assert.rejects(core.initialize(other), error => error.code === 'CORE_ALREADY_INITIALIZED');
}));

test('initialize marks interrupted leases and their snapshots synthesize PROCESS_INTERRUPTED', () => makeFixture(async ({ core, native, files }) => {
  files.interrupted = [JOB];
  await core.initialize(files.getCoreConfig());
  assert.deepEqual(files.finished, [JOB]);
  assert.equal(native.calls.snapshot.length, 0);
  const snapshot = await core.getJobSnapshot(JOB);
  assert.equal(snapshot.state, 'failed');
  assert.equal(snapshot.lastSequence, 0);
  assert.equal(snapshot.terminal.type, 'job.failed');
  assert.equal(snapshot.terminal.payload.error.code, 'PROCESS_INTERRUPTED');
}));

test('startRefinement runs acquire, beginJob and start in the mandated order', () => makeFixture(async ({ core, native, files, store }) => {
  await core.initialize(files.getCoreConfig());
  const accepted = await core.startRefinement(request());
  assert.equal(accepted.jobId, JOB);
  assert.equal(accepted.state, 'queued');
  assert.deepEqual(native.calls.acquire, [JOB]);
  assert.deepEqual(native.calls.start, [JSON.stringify(request())]);
  assert.deepEqual(files.leases.get(JOB), ['file_xray_data_0001', 'file_xray_inst_0002',
    'file_neut_data_0003', 'file_neut_inst_0004', 'file_phase_cif_0005']);
  assert.equal(store.value, JOB);
}));

test('a synchronous rejection closes both gates and maps the contract code', () => makeFixture(async ({ core, native, files }) => {
  await core.initialize(files.getCoreConfig());
  const error = new Error('已有任务运行，请等待该任务结束。');
  error.code = 'BUSY'; error.retryable = true;
  native.fail.startAcquiredJob = error;
  await assert.rejects(core.startRefinement(request()), rejected =>
    rejected.code === 'BUSY' && rejected.retryable === true);
  assert.deepEqual(native.calls.release, [JOB]);
  assert.deepEqual(files.finished, [JOB]);
  assert.equal(files.leases.has(JOB), false);
}));

test('an acquire failure never reaches the file service', () => makeFixture(async ({ core, native, files }) => {
  await core.initialize(files.getCoreConfig());
  const error = new Error('任务编号重复，请重新提交。');
  error.code = 'JOB_ALREADY_EXISTS'; error.retryable = false;
  native.fail.acquireJob = error;
  await assert.rejects(core.startRefinement(request()), rejected => rejected.code === 'JOB_ALREADY_EXISTS');
  assert.deepEqual(files.sequence, []);
  assert.deepEqual(native.calls.release, []);
}));

test('job.completed registers real artifacts before the page is delivered the event', () => makeFixture(async ({ core, native, files, root }) => {
  await core.initialize(files.getCoreConfig());
  const delivered = [];
  core.onEvent(event => delivered.push(event));
  await core.startRefinement(request());
  fs.writeFileSync(posixJoin(root, 'outputs', JOB, 'PbSO4-refined.gpx'), 'gpx-bytes\n');
  native.emit(event('job.completed', JOB, 3, { result: { artifacts: [
    { fileId: 'file_out_x_gpx', kind: 'project', displayName: 'PbSO4-refined.gpx', mediaType: 'application/octet-stream' },
    { fileId: 'not-a-file-id', kind: 'result', displayName: 'ghost.out', mediaType: 'text/plain' },
    { fileId: 'file_out_missing_01', kind: 'result', displayName: 'never-written.out', mediaType: 'text/plain' }] } }));
  await core.flushEvents();
  assert.equal(delivered.length, 1);
  const artifacts = delivered[0].payload.result.artifacts;
  assert.deepEqual(artifacts.map(item => item.fileId), ['file_out_x_gpx']);
  assert.deepEqual(files.registered, [{ jobId: JOB, fileId: 'file_out_x_gpx', displayName: 'PbSO4-refined.gpx', kind: 'project' }]);
  assert.deepEqual(files.sequence.filter(step => step.startsWith('register') || step.startsWith('deliver')),
    ['register:PbSO4-refined.gpx']);
  assert.equal(files.sequence.indexOf(`finish:${JOB}`), files.sequence.length - 1);
  assert.deepEqual(native.calls.release, []);
}));

test('a failed terminal writes the sanitized user log, registers it, then finishes', () => makeFixture(async ({ core, native, files, root, store }) => {
  await core.initialize(files.getCoreConfig());
  const delivered = [];
  core.onEvent(event => delivered.push(event));
  await core.startRefinement(request());
  native.emit(event('job.log', JOB, 1, { level: 'info', message: '阶段 saving 开始' }));
  native.emit(event('job.log', JOB, 2, { level: 'info', message: `内部路径 ${root}/outputs 不得出现在日志` }));
  native.emit(event('job.failed', JOB, 3, { error: { code: 'REFINEMENT_FAILED', message: '精修失败，请检查输入。', retryable: false } }));
  await core.flushEvents();
  assert.equal(delivered.length, 3);
  const log = fs.readFileSync(posixJoin(root, 'outputs', JOB, 'job-log.txt'), 'utf8');
  assert.ok(log.includes('REFINEMENT_FAILED'));
  assert.ok(log.includes('阶段 saving 开始'));
  assert.equal(log.includes(root), false);
  assert.deepEqual(files.registered, [{ jobId: JOB, fileId: `file_log_${JOB.slice(4)}`, displayName: 'job-log.txt', kind: 'log' }]);
  assert.equal(store.value, JOB);
  assert.deepEqual(files.finished, [JOB]);
  assert.deepEqual(native.calls.release, []);
}));

test('B03: the failed terminal event carries the registered log artifact', () => makeFixture(async ({ core, native, files, root }) => {
  await core.initialize(files.getCoreConfig());
  const delivered = [];
  core.onEvent(event => delivered.push(event));
  await core.startRefinement(request());
  native.emit(event('job.failed', JOB, 1, { error: { code: 'REFINEMENT_FAILED', message: '精修失败，请检查输入。', retryable: false } }));
  await core.flushEvents();
  const failed = delivered[0];
  assert.equal(failed.type, 'job.failed');
  assert.deepEqual(failed.payload.artifacts, [
    { fileId: `file_log_${JOB.slice(4)}`, kind: 'log', displayName: 'job-log.txt', mediaType: 'text/plain' }]);
  // Consistency evidence: the snapshot answers with exactly the payload the page received,
  // its artifact token is the one the file service registered, and the sidecar on disk says the same.
  const snapshot = await core.getJobSnapshot(JOB);
  assert.deepEqual(snapshot.terminal.payload, failed.payload);
  assert.equal(snapshot.terminal.payload.artifacts[0].fileId, files.registered[0].fileId);
  const persisted = JSON.parse(fs.readFileSync(posixJoin(root, 'outputs', JOB, 'core', 'terminal-snapshot.json'), 'utf8'));
  assert.deepEqual(persisted.terminal.payload.artifacts, failed.payload.artifacts);
  assert.equal(persisted.state, 'failed');
}));

test('B03: an incomplete log registration delivers the terminal without artifacts', () => makeFixture(async ({ core, native, files, root }) => {
  await core.initialize(files.getCoreConfig());
  const delivered = [];
  core.onEvent(event => delivered.push(event));
  await core.startRefinement(request());
  files.failRegister = true;  // the log file is written but the registry rejects
  native.emit(event('job.failed', JOB, 1, { error: { code: 'REFINEMENT_FAILED', message: '精修失败，请检查输入。', retryable: false } }));
  await core.flushEvents();
  assert.ok(fs.existsSync(posixJoin(root, 'outputs', JOB, 'job-log.txt')));
  assert.deepEqual(files.registered, []);
  assert.equal(delivered[0].type, 'job.failed');
  assert.equal(delivered[0].payload.artifacts, undefined);
  const snapshot = await core.getJobSnapshot(JOB);
  assert.equal(snapshot.terminal.payload.artifacts, undefined);
  assert.deepEqual(files.finished, [JOB]);
}));

test('one-histogram requests accepted by the frozen contract bind all three inputs', () => makeFixture(async ({ core, native, files }) => {
  await core.initialize(files.getCoreConfig());
  const single = request('job_single_histogram_01');
  single.inputs.histograms = [single.inputs.histograms[0]];
  await core.startRefinement(single);
  assert.deepEqual(files.leases.get(single.jobId), [
    'file_xray_data_0001', 'file_xray_inst_0002', 'file_phase_cif_0005'
  ]);
  assert.deepEqual(native.calls.acquire, [single.jobId]);
}));

test('a cancelled terminal records the reason in the user log', () => makeFixture(async ({ core, native, files, root }) => {
  await core.initialize(files.getCoreConfig());
  const delivered = [];
  core.onEvent(event => delivered.push(event));
  await core.startRefinement(request());
  native.emit(event('job.cancelled', JOB, 4, { reason: '用户请求取消' }));
  await core.flushEvents();
  const log = fs.readFileSync(posixJoin(root, 'outputs', JOB, 'job-log.txt'), 'utf8');
  assert.ok(log.includes('状态: 已取消'));
  assert.ok(log.includes('用户请求取消'));
  assert.equal(log.includes(root), false);
  assert.deepEqual(delivered[0].payload.artifacts, [
    { fileId: `file_log_${JOB.slice(4)}`, kind: 'log', displayName: 'job-log.txt', mediaType: 'text/plain' }]);
  assert.deepEqual((await core.getJobSnapshot(JOB)).terminal.payload, delivered[0].payload);
}));

test('terminal snapshots recover across a process restart', () => makeFixture(async ({ core, native, files, root, store }) => {
  await core.initialize(files.getCoreConfig());
  const delivered = [];
  core.onEvent(event => delivered.push(event));
  await core.startRefinement(request());
  fs.writeFileSync(posixJoin(root, 'outputs', JOB, 'PbSO4-refined.gpx'), 'gpx-bytes\n');
  native.emit(event('job.completed', JOB, 3, { result: { artifacts: [
    { fileId: 'file_out_x_gpx', kind: 'project', displayName: 'PbSO4-refined.gpx', mediaType: 'application/octet-stream' }] } }));
  await core.flushEvents();
  assert.deepEqual(files.finished, [JOB]);

  // New "process": empty native ledger and empty in-memory views; only the
  // filesystem and the persisted job id survive, like a real restart.
  const native2 = new FakeNative();
  const files2 = new FakeFiles(root);
  const store2 = { value: store.value, async load() { return store2.value; }, async save(jobId) { store2.value = jobId; } };
  const core2 = new CoreBridgeService({ native: native2, files: files2, runtime: runtimeSource(), jobs: store2 });
  await core2.initialize(files2.getCoreConfig());
  assert.equal(await core2.restoreJobId(), JOB);
  const recovered = await core2.getJobSnapshot(JOB);
  assert.equal(native2.calls.snapshot.length, 1);  // the ledger really was gone
  assert.equal(recovered.state, 'succeeded');
  assert.deepEqual(recovered.terminal.payload.result.artifacts.map(a => a.fileId), ['file_out_x_gpx']);
  assert.deepEqual(recovered.terminal.payload, delivered[0].payload);
}));

test('a recovered failed terminal keeps its registered log artifact across restart', () => makeFixture(async ({ core, native, files, root, store }) => {
  await core.initialize(files.getCoreConfig());
  const delivered = [];
  core.onEvent(event => delivered.push(event));
  await core.startRefinement(request());
  native.emit(event('job.failed', JOB, 1, { error: { code: 'REFINEMENT_FAILED', message: '精修失败，请检查输入。', retryable: false } }));
  await core.flushEvents();
  const registeredFileId = files.registered[0].fileId;

  const native2 = new FakeNative();
  const files2 = new FakeFiles(root);
  const store2 = { value: store.value, async load() { return store2.value; }, async save(jobId) { store2.value = jobId; } };
  const core2 = new CoreBridgeService({ native: native2, files: files2, runtime: runtimeSource(), jobs: store2 });
  await core2.initialize(files2.getCoreConfig());
  const recovered = await core2.getJobSnapshot(JOB);
  assert.deepEqual(recovered.terminal.payload, delivered[0].payload);
  assert.equal(recovered.terminal.payload.artifacts[0].fileId, registeredFileId);
}));

test('an interrupted job stays PROCESS_INTERRUPTED across repeated restarts', () => makeFixture(async ({ files, root }) => {
  // The lease directory survives the crash — listInterruptedJobs only ever
  // reports jobs whose outputs/<jobId> exists from the previous process.
  fs.mkdirSync(posixJoin(root, 'outputs', JOB), { recursive: true });
  const native1 = new FakeNative();
  const store1 = { value: JOB, async load() { return store1.value; }, async save(jobId) { store1.value = jobId; } };
  const core1 = new CoreBridgeService({ native: native1, files, runtime: runtimeSource(), jobs: store1 });
  files.interrupted = [JOB];
  await core1.initialize(files.getCoreConfig());
  assert.deepEqual(files.finished, [JOB]);

  // Second process: the lease is already released, so only the persisted
  // synthesized view answers — still PROCESS_INTERRUPTED, never a live job.
  const files2 = new FakeFiles(root);
  const native2 = new FakeNative();
  const core2 = new CoreBridgeService({ native: native2, files: files2, runtime: runtimeSource(), jobs: store1 });
  await core2.initialize(files2.getCoreConfig());
  const snapshot = await core2.getJobSnapshot(JOB);
  assert.equal(snapshot.state, 'failed');
  assert.equal(snapshot.lastSequence, 0);
  assert.equal(snapshot.terminal.type, 'job.failed');
  assert.equal(snapshot.terminal.payload.error.code, 'PROCESS_INTERRUPTED');
  assert.equal(snapshot.terminal.payload.error.retryable, true);
  assert.equal(snapshot.terminal.payload.artifacts, undefined);
}));

test('a missing or malformed persisted snapshot degrades to JOB_NOT_FOUND, never a fake result', () => makeFixture(async ({ core, native, files, root }) => {
  await core.initialize(files.getCoreConfig());
  await core.startRefinement(request());
  native.emit(event('job.failed', JOB, 1, { error: { code: 'REFINEMENT_FAILED', message: '精修失败，请检查输入。', retryable: false } }));
  await core.flushEvents();
  const sidecar = posixJoin(root, 'outputs', JOB, 'core', 'terminal-snapshot.json');
  fs.writeFileSync(sidecar, '{"jobId":"broken');

  const native2 = new FakeNative();
  const files2 = new FakeFiles(root);
  const core2 = new CoreBridgeService({ native: native2, files: files2, runtime: runtimeSource(), jobs: { value: JOB, async load() { return JOB; }, async save() {} } });
  await core2.initialize(files2.getCoreConfig());
  await assert.rejects(core2.getJobSnapshot(JOB), error => error.code === 'JOB_NOT_FOUND');

  // A path-derived fileId (not a registration token) is rejected the same way.
  fs.writeFileSync(sidecar, JSON.stringify({ jobId: JOB, state: 'failed', lastSequence: 1, percent: 0, stage: null,
    terminal: { type: 'job.failed', payload: { error: { code: 'REFINEMENT_FAILED', message: 'x', retryable: false },
      artifacts: [{ fileId: 'file_log_../escape', kind: 'log', displayName: 'job-log.txt', mediaType: 'text/plain' }] } } }));
  await assert.rejects(core2.getJobSnapshot(JOB), error => error.code === 'JOB_NOT_FOUND');
}));

test('cancelJob forwards the ack and getJobSnapshot passes the native snapshot', () => makeFixture(async ({ core, native, files }) => {
  await core.initialize(files.getCoreConfig());
  native.ack = JSON.stringify({ requested: true });
  const ack = await core.cancelJob(JOB);
  assert.deepEqual(ack, { schemaVersion: '1.0', jobId: JOB, requested: true });
  const snapshot = { jobId: JOB, state: 'running', lastSequence: 2, percent: 40, stage: 'cells', terminal: null };
  native.snapshots[JOB] = JSON.stringify(snapshot);
  assert.deepEqual(await core.getJobSnapshot(JOB), snapshot);
}));

test('native JOB_NOT_FOUND rejections surface as contract errors, unknown shapes do not leak', () => makeFixture(async ({ core, files }) => {
  await core.initialize(files.getCoreConfig());
  await assert.rejects(core.getJobSnapshot('job_doesnotexist_1'), error => error.code === 'JOB_NOT_FOUND');
  await assert.rejects(core.getJobSnapshot('bogus'), error => error.code === 'INVALID_REQUEST');
}));

test('calls before initialization are rejected CORE_NOT_READY without touching native', () => makeFixture(async ({ core, native, files }) => {
  files.interrupted = [JOB];  // interruption only answers snapshots, it is not a live core
  await assert.rejects(core.startRefinement(request()), error => error.code === 'CORE_NOT_READY');
  await assert.rejects(core.cancelJob(JOB), error => error.code === 'CORE_NOT_READY');
  await assert.rejects(core.getJobSnapshot(JOB), error => error.code === 'CORE_NOT_READY');
  assert.deepEqual(files.sequence, []);
  assert.equal(native.calls.start.length, 0);
}));

test('malformed events are dropped; listener errors do not stop other listeners', () => makeFixture(async ({ core, native, files }) => {
  await core.initialize(files.getCoreConfig());
  const seen = [];
  core.onEvent(() => { throw new Error('listener must be swallowed'); });
  const unsubscribe = core.onEvent(event => seen.push(event.type));
  native.callback('{not json');
  native.callback(JSON.stringify(event('job.log', 'not-a-job-id', 0, {})));
  native.emit(event('job.accepted', JOB, 0, { state: 'queued' }));
  await core.flushEvents();
  assert.deepEqual(seen, ['job.accepted']);
  unsubscribe();
  native.emit(event('job.progress', JOB, 1, { state: 'running', percent: 10, stage: 'reading_files' }));
  await core.flushEvents();
  assert.deepEqual(seen, ['job.accepted']);
}));

test('unsupported recipe and oversize cycle counts are rejected before the gate', () => makeFixture(async ({ core, native, files }) => {
  await core.initialize(files.getCoreConfig());
  const bad = request();
  bad.recipeId = 'unknown-recipe';
  await assert.rejects(core.startRefinement(bad), error => error.code === 'UNSUPPORTED_RECIPE');
  const cycles = request();
  cycles.options.cycleCount = 99;
  await assert.rejects(core.startRefinement(cycles), error => error.code === 'INVALID_REQUEST');
  assert.deepEqual(native.calls.acquire, []);
}));

test('shutdown stops the worker and closes the facade', () => makeFixture(async ({ core, native, files }) => {
  await core.initialize(files.getCoreConfig());
  await core.shutdown();
  assert.equal(native.calls.shutdown, 1);
  assert.equal(native.callback, null);
  await assert.rejects(core.startRefinement(request()), error => error.code === 'CORE_NOT_READY');
  const restored = await core.restoreJobId();
  assert.equal(restored, '');
}));

test('A session consumes B facade events, cancellation ack and registered results', () => makeFixture(async ({ core, native, files, root }) => {
  await core.initialize(files.getCoreConfig());
  const session = new RefinementSession(core, () => {});
  await session.connect();
  await session.start(request());
  native.emit(event('job.progress', JOB, 1, { state: 'running', percent: 30, stage: 'cells' }));
  await core.flushEvents();
  assert.equal(session.view.state, 'running');
  assert.equal(session.view.percent, 30);
  await session.cancel();
  assert.equal(session.cancelRequested, true);
  assert.equal(session.view.state, 'running'); // ACK is not a terminal.
  fs.writeFileSync(posixJoin(root, 'outputs', JOB, 'PbSO4-refined.gpx'), 'host-test-only\n');
  native.emit(event('job.completed', JOB, 2, { result: { artifacts: [
    { fileId: 'file_result_project_01', displayName: 'PbSO4-refined.gpx', kind: 'project', mediaType: 'application/octet-stream' }
  ] } }));
  await core.flushEvents();
  assert.equal(session.view.state, 'succeeded'); // Natural completion can win cancellation.
  assert.equal(session.cancelRequested, false);
  assert.equal(session.view.result.artifacts[0].fileId, files.registered[0].fileId);
  session.disconnect();
}));

test('A session restores B interrupted records and tolerates expired recent IDs', () => makeFixture(async ({ core, files, store }) => {
  files.interrupted = [JOB]; store.value = JOB;
  await core.initialize(files.getCoreConfig());
  const session = new RefinementSession(core, () => {});
  await session.connect(await core.restoreJobId());
  assert.equal(session.view.state, 'failed');
  assert.equal(session.view.error.code, 'PROCESS_INTERRUPTED');
  assert.deepEqual(session.view.history, []);
  store.value = 'job_expired_recent_01';
  await session.connect(await core.restoreJobId());
  assert.equal(session.view.state, 'idle');
  assert.equal(session.view.error, undefined);
  session.disconnect();
}));

for (const state of ['failed', 'cancelled']) {
  for (const registrationFails of [false, true]) {
    test(`A session displays and restores B ${state} logs with registration failure=${registrationFails}`, () => makeFixture(async ({ core, native, files, root, store }) => {
      files.failRegister = registrationFails;
      const register = files.registerOutput.bind(files);
      // A must consume the returned token even if it differs from B's proposal.
      files.registerOutput = async (...args) => ({ ...await register(...args), fileId: 'file_registered_by_service_01' });
      await core.initialize(files.getCoreConfig());
      const session = new RefinementSession(core, () => {});
      await session.connect();
      await session.start(request());
      if (state === 'cancelled') await session.cancel();
      const payload = state === 'failed'
        ? { error: { code: 'REFINEMENT_FAILED', message: '精修失败，请检查输入。', retryable: false } }
        : { reason: '用户取消' };
      native.emit(event(`job.${state}`, JOB, 1, payload));
      await core.flushEvents();
      assert.equal(session.view.state, state);
      assert.equal(session.cancelRequested, false);
      const expectedIds = registrationFails ? [] : ['file_registered_by_service_01'];
      assert.deepEqual(session.view.terminalArtifacts.map(a => a.fileId), expectedIds);
      const delivered = structuredClone(session.view.terminalArtifacts);
      session.disconnect();

      const files2 = new FakeFiles(root);
      const core2 = new CoreBridgeService({ native: new FakeNative(), files: files2, runtime: runtimeSource(), jobs: store });
      await core2.initialize(files2.getCoreConfig());
      const restored = new RefinementSession(core2, () => {});
      await restored.connect(await core2.restoreJobId());
      assert.equal(restored.view.state, state);
      assert.deepEqual(restored.view.terminalArtifacts, delivered);
      assert.deepEqual(restored.view.history, []);
      await restored.start(request('job_after_restore_01'));
      assert.equal(restored.view.state, 'queued');
      assert.deepEqual(restored.view.terminalArtifacts, []);
      restored.disconnect();
    }));
  }
}
