const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {
  RefinementView, receiveEvent, MockCoreService, newMockRequest
} = require('../ui-mock/build/test-model/Refinement.js');

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
    assert.equal((await service.getJobSnapshot(request.jobId)).terminalEvent, undefined);
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
