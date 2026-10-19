const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const mockModel = require('../ui-mock/build/test-model/Refinement.js');
const { MockCoreService, newMockRequest } = mockModel;
// Replay the same public-boundary cases against the formal ArkTS implementation.
// The mock service remains test-only and is never copied into app/.
const { RefinementView, receiveEvent, receiveSnapshot, RefinementSession } =
  process.env.GSAS_FORMAL_MODEL ? require(process.env.GSAS_FORMAL_MODEL) : mockModel;

const example = name => JSON.parse(fs.readFileSync(path.join(__dirname, '../contracts/examples', name), 'utf8'));
const data = {
  request: example('refinement-request.json'),
  success: example('core-events-success.json'),
  failed: example('core-events-failed.json'),
  cancelled: example('core-events-cancelled.json')
};
function replay(events) {
  let view = new RefinementView();
  view.jobId = events[0].jobId;
  for (const event of events) view = receiveEvent(view, event);
  return view;
}
function terminal(service) {
  return new Promise(resolve => {
    const off = service.onEvent(event => {
      if (['job.completed', 'job.failed', 'job.cancelled'].includes(event.type)) {
        off(); resolve(event);
      }
    });
  });
}

test('provided examples produce three distinct terminal screens', () => {
  const success = replay(data.success);
  assert.equal(success.state, 'succeeded');
  assert.equal(success.percent, 100);
  assert.equal(success.stage, 'completed');
  assert.equal(success.result.stages.length, 5);
  assert.equal(success.result.stages[4].rwpByHistogram.xray.toFixed(4), '13.1646');
  assert.deepEqual(success.result.artifacts.map(a => a.displayName), ['PbSO4-refined.gpx', 'PbSO4-refined.json']);
  const failed = replay(data.failed);
  assert.equal(failed.state, 'failed');
  assert.equal(failed.message, '仪器参数文件无法识别');
  assert.equal(failed.error.retryable, false);
  assert.equal(failed.result, undefined);
  const cancelled = replay(data.cancelled);
  assert.equal(cancelled.state, 'cancelled');
  assert.equal(cancelled.percent, 35);
  assert.equal(cancelled.result, undefined);
});

test('duplicate, old-job and late events cannot corrupt displayed state', () => {
  let view = new RefinementView();
  view.jobId = data.success[0].jobId;
  view = receiveEvent(view, data.success[0]);
  view = receiveEvent(view, data.success[2]);
  assert.equal(receiveEvent(view, data.success[1]), view);
  assert.equal(receiveEvent(view, data.failed[1]), view);
  view = receiveEvent(view, data.success[3]);
  const late = { ...data.success[2], sequence: 99 };
  assert.equal(receiveEvent(view, late), view);
});

test('mock runs are isolated, single-task, ordered and restartable', { timeout: 2000 }, async () => {
  const service = new MockCoreService(data, 5);
  const events = [];
  const off = service.onEvent(event => events.push(event));
  try {
    const request = newMockRequest(data.request);
    const done = terminal(service);
    await service.startRefinement(request);
    await assert.rejects(service.startRefinement(newMockRequest(data.request)), /BUSY/);
    await done;
    assert.deepEqual(events.map(e => e.sequence), [0, 1, 2, 3]);
    assert.equal(events.filter(e => e.type === 'job.completed').length, 1);
    assert.ok(events.every(e => e.jobId === request.jobId));
    await assert.rejects(service.startRefinement(request), /JOB_ALREADY_EXISTS/);
    const next = newMockRequest(data.request);
    const nextDone = terminal(service);
    await service.startRefinement(next);
    await nextDone;
    assert.notEqual(next.jobId, request.jobId);
    assert.equal(new Set(events.map(e => e.eventId)).size, 8);
    assert.equal(data.request.jobId, 'job_20261012_001');
  } finally { off(); service.dispose(); }
});

test('cancel ack is not terminal; cancelling is visible before cancelled', { timeout: 2000 }, async () => {
  const service = new MockCoreService(data, 10);
  service.setScenario('cancelled');
  const request = newMockRequest(data.request);
  let view = new RefinementView();
  view.jobId = request.jobId;
  const states = [];
  service.onEvent(event => { view = receiveEvent(view, event); states.push(view.state); });
  try {
    const done = terminal(service);
    await service.startRefinement(request);
    const ack = await service.cancelJob(request.jobId);
    assert.equal(ack.requested, true);
    assert.equal(view.state, 'queued');
    assert.equal((await service.getJobSnapshot(request.jobId)).terminal, null);
    await service.cancelJob(request.jobId); // Repeated clicks must not duplicate terminal events.
    await done;
    assert.deepEqual(states, ['queued', 'cancelling', 'cancelled']);
    assert.equal(view.result, undefined);
  } finally { service.dispose(); }
});

test('cancelling a progressed successful run keeps monotonic progress', { timeout: 2000 }, async () => {
  const service = new MockCoreService(data, 10);
  const request = newMockRequest(data.request);
  const events = [];
  service.onEvent(event => {
    events.push(event);
    if (event.type === 'job.progress' && event.payload.percent === 55) {
      service.cancelJob(request.jobId);
    }
  });
  try {
    const done = terminal(service);
    await service.startRefinement(request);
    const end = await done;
    assert.equal(end.type, 'job.cancelled');
    assert.deepEqual(events.filter(e => e.type === 'job.progress').map(e => e.payload.percent), [10, 55, 55]);
    assert.equal(events.find(e => e.payload.state === 'cancelling').payload.stage, 'cells');
    assert.equal(events.filter(e => e.type === 'job.completed').length, 0);
  } finally { service.dispose(); }
});

test('failure replay keeps the non-retryable contract and emits exactly one terminal', { timeout: 2000 }, async () => {
  const service = new MockCoreService(data, 5);
  service.setScenario('failed');
  try {
    const done = terminal(service);
    const request = newMockRequest(data.request);
    await service.startRefinement(request);
    const end = await done;
    assert.equal(end.payload.error.code, 'INVALID_INSTRUMENT_FILE');
    assert.equal(end.payload.error.retryable, false);
    assert.equal((await service.getJobSnapshot(request.jobId)).state, 'failed');
  } finally { service.dispose(); }
});

function deferred() {
  let resolve, reject;
  const promise = new Promise((ok, fail) => { resolve = ok; reject = fail; });
  return { promise, resolve, reject };
}

// Controllable public service boundary: no Python/transport behavior is reimplemented.
function controlledService() {
  let listener = () => {};
  return {
    onEvent(callback) { listener = callback; return () => { listener = () => {}; }; },
    emit(event) { listener(event); },
    async startRefinement(request) { return { jobId: request.jobId, state: 'queued' }; },
    async cancelJob(jobId) { return { jobId, requested: true }; },
    async getJobSnapshot() { throw new Error('snapshot not set for this test'); }
  };
}

test('session sees synchronous events and never replaces completion with a late start response', async () => {
  for (const rejects of [false, true]) {
    const service = controlledService();
    const response = deferred();
    service.startRefinement = () => {
      for (const event of data.success) service.emit(event);
      return response.promise;
    };
    const session = new RefinementSession(service, () => {});
    await session.connect();
    const started = session.start({ ...data.request, jobId: data.success[0].jobId });
    assert.equal(session.view.state, 'succeeded');
    if (rejects) response.reject(new Error('late transport failure'));
    else response.resolve({ jobId: session.view.jobId, state: 'queued' });
    await started;
    assert.equal(session.view.state, 'succeeded');
    assert.equal(session.view.result.stages.length, 5);
    session.disconnect();
  }
});

test('start rejection without events gives a safe error and allows a new request', async () => {
  const service = controlledService();
  service.startRefinement = async () => { throw new Error('private traceback /user/secret'); };
  const session = new RefinementSession(service, () => {});
  await session.connect();
  await session.start(data.request);
  assert.equal(session.view.state, 'failed');
  assert.equal(session.view.error.code, 'INTERNAL_ERROR');
  assert.doesNotMatch(JSON.stringify(session.view), /traceback|secret/);
  service.startRefinement = async request => ({ jobId: request.jobId });
  await session.start(newMockRequest(data.request));
  assert.equal(session.view.state, 'queued');
  assert.equal(session.view.error, undefined);
  session.disconnect();
});

test('snapshot restore preserves newer events and disconnect invalidates pending work', async () => {
  const service = controlledService();
  const response = deferred();
  service.getJobSnapshot = () => response.promise;
  let changes = 0;
  const session = new RefinementSession(service, () => { changes++; });
  const jobId = data.success[0].jobId;
  const connecting = session.connect(jobId);
  service.emit(data.success[2]); // cells, 55%, sequence 2, arrives during snapshot read
  response.resolve({ jobId, state: 'queued', lastSequence: 0, percent: 0, stage: null, terminal: null });
  await connecting;
  assert.equal(session.view.percent, 55);
  assert.equal(session.view.stage, 'cells');

  const pending = deferred();
  service.getJobSnapshot = () => pending.promise;
  const reconnecting = session.connect(jobId);
  session.disconnect();
  const count = changes;
  pending.resolve({ jobId, state: 'succeeded', lastSequence: 3, percent: 100,
    stage: 'completed', terminal: { type: 'job.completed', payload: data.success[3].payload } });
  service.emit(data.success[3]);
  await reconnecting;
  assert.equal(changes, count);
  assert.notEqual(session.view.state, 'succeeded');
});

test('disconnect detaches the page without cancelling the service; reconnect restores a terminal result', async () => {
  const service = new MockCoreService(data, 5);
  const first = new RefinementSession(service, () => {});
  try {
    await first.connect();
    const request = newMockRequest(data.request);
    const done = terminal(service);
    await first.start(request);
    first.disconnect();
    await done;
    assert.equal(first.view.state, 'queued');
    const restored = new RefinementSession(service, () => {});
    await restored.connect(request.jobId);
    assert.equal(restored.view.state, 'succeeded');
    assert.equal(restored.view.percent, 100);
    assert.equal(restored.view.result.stages.length, 5);
    restored.disconnect();
  } finally { first.disconnect(); service.dispose(); }
});

test('cancel ack waits for terminal and a late rejection cannot affect a new job', async () => {
  const service = controlledService();
  const session = new RefinementSession(service, () => {});
  await session.connect();
  await session.start(data.request);
  await session.cancel();
  assert.equal(session.view.state, 'queued');
  assert.equal(session.cancelRequested, true);
  service.emit({ ...data.cancelled[2], jobId: data.request.jobId });
  assert.equal(session.view.state, 'cancelled');
  assert.equal(session.cancelRequested, false);

  await session.start(newMockRequest(data.request));
  const response = deferred();
  service.cancelJob = () => response.promise;
  const cancelling = session.cancel();
  service.emit({ ...data.success[3], jobId: session.view.jobId });
  await session.start(newMockRequest(data.request));
  response.reject(new Error('old cancel rejection'));
  await cancelling;
  assert.equal(session.view.state, 'queued');
  assert.equal(session.cancelRequested, false);
  assert.equal(session.notice, '');
  session.disconnect();
});

test('unconfirmed cancellation remains active and can be retried', async () => {
  const service = controlledService();
  service.cancelJob = async jobId => ({ jobId, requested: false });
  const session = new RefinementSession(service, () => {});
  await session.connect();
  await session.start(data.request);
  await session.cancel();
  assert.equal(session.view.state, 'queued');
  assert.equal(session.cancelRequested, false);
  assert.ok(session.notice);
  session.disconnect();
});

test('snapshot supports null initial stage and interrupted-process error without inventing results', () => {
  const view = new RefinementView();
  view.jobId = data.request.jobId;
  const queued = { jobId: view.jobId, state: 'queued', lastSequence: -1, percent: 0, stage: null, terminal: null };
  const restored = receiveSnapshot(view, queued);
  assert.equal(restored.state, 'queued');
  assert.equal(restored.stage, '');
  assert.equal(receiveSnapshot(restored, { ...queued, jobId: 'job_another_001' }), restored);
  const failed = receiveSnapshot(restored, { ...queued, state: 'failed', lastSequence: 4,
    terminal: { type: 'job.failed', payload: { state: 'failed', error: {
      code: 'PROCESS_INTERRUPTED', message: '任务因进程退出中断', retryable: true
    } } } });
  assert.equal(failed.error.code, 'PROCESS_INTERRUPTED');
  assert.equal(failed.result, undefined);
  assert.equal(receiveSnapshot(failed, { ...queued, lastSequence: 99 }), failed);
});

test('actual Python host bridge events and snapshots produce matching UI terminal states', { timeout: 15000 }, async () => {
  const { execFileSync } = require('node:child_process');
  const captures = JSON.parse(execFileSync(process.env.PYTHON || 'python', [
    path.join(__dirname, 'capture_bridge_ui.py')
  ], { cwd: path.join(__dirname, '..'), encoding: 'utf8', timeout: 10000,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' } }));
  for (const [scenario, capture] of Object.entries(captures)) {
    const live = replay(capture.events);
    const service = controlledService();
    service.getJobSnapshot = async () => capture.snapshot;
    const session = new RefinementSession(service, () => {});
    await session.connect(capture.accepted.jobId);
    const restored = session.view;
    assert.equal(live.state, { success: 'succeeded', failed: 'failed', cancelled: 'cancelled' }[scenario]);
    assert.equal(restored.state, live.state);
    assert.equal(restored.percent, live.percent);
    assert.deepEqual(restored.result, live.result);
    assert.deepEqual(restored.error, live.error);
    assert.equal(restored.sequence, live.sequence);
    // B03: a failure/cancellation shows exactly the registered log token,
    // whether the page reached the terminal by live events or by snapshot.
    assert.deepEqual(restored.terminalArtifacts, live.terminalArtifacts);
    if (scenario !== 'success') {
      assert.deepEqual(live.terminalArtifacts, [{
        fileId: `file_log_${capture.accepted.jobId.slice(4)}`, kind: 'log',
        displayName: 'job-log.txt', mediaType: 'text/plain' }]);
    } else {
      // Both projections show no failure/cancellation logs on success;
      // the formal page normalizes an absent optional field to an empty list.
      assert.deepEqual(live.terminalArtifacts ?? [], []);
    }
    for (const snapshot of capture.snapshots) {
      assert.equal(receiveSnapshot(restored, snapshot), restored); // late snapshots cannot erase terminal
    }
    if (scenario === 'success') {
      assert.equal(restored.result.stages.length, 5);
      // docs/TEST_PLAN.md baseline (B fake core), distinct from M1's measured example.
      assert.equal(restored.result.stages[4].rwpByHistogram.xray, 13.16483);
      assert.deepEqual(restored.result.artifacts.map(a => a.kind).sort(), ['log', 'project', 'result']);
    } else if (scenario === 'failed') {
      assert.equal(restored.error.code, 'INTERNAL_ERROR');
      assert.doesNotMatch(restored.message, /Traceback|simulated GSAS-II/);
    } else {
      assert.equal(capture.acks.length, 1);
      assert.equal(capture.acks[0].requested, true);
      assert.equal(restored.result, undefined);
    }
    session.disconnect();
  }
});
