'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require(process.env.GSAS_TYPESCRIPT_PATH || 'typescript');
// Pure .ets models only. Platform/UI syntax is checked by the real HAP build.
require.extensions['.ets'] = (module, filename) => {
  const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS }
  }).outputText;
  module._compile(code, filename);
};
process.env.GSAS_FORMAL_MODEL = path.resolve(__dirname, '../app/entry/src/main/ets/model/Refinement.ets');
const { prepareRefinementRequest, RefinementSession, RefinementView, receiveSnapshot, receiveEvent, callError } = require(process.env.GSAS_FORMAL_MODEL);
require('./ui-mock.test.cjs');
const example = JSON.parse(fs.readFileSync(path.join(__dirname, '../contracts/examples/refinement-request.json'), 'utf8'));

test('formal request uses explicit settings and an immutable copy of verified inputs', () => {
  const inputs = structuredClone(example.inputs);
  const request = prepareRefinementRequest('job_formal_test_001', inputs, 'PbSO4', '0', 'sample.gpx');
  assert.deepEqual(request, { ...example, jobId: 'job_formal_test_001',
    inputs: { ...example.inputs, phase: { ...example.inputs.phase, name: 'PbSO4' } },
    options: { cycleCount: 0 }, output: { projectName: 'sample.gpx', overwrite: false } });
  inputs.histograms[0].dataFileId = 'file_changed_001'; inputs.phase.name = 'changed';
  assert.notEqual(request.inputs.histograms[0].dataFileId, inputs.histograms[0].dataFileId);
  assert.equal(request.inputs.phase.name, 'PbSO4');
  assert.equal(prepareRefinementRequest('job_formal_test_002', inputs, 'phase', '50', 'a.gpx').options.cycleCount, 50);
});

test('formal request never silently defaults or truncates invalid user input', () => {
  for (const cycles of ['', ' ', '-1', '51', '1.5', '1e1', '0x10', 'Infinity']) {
    assert.throws(() => prepareRefinementRequest('job_formal_test_001', example.inputs, 'PbSO4', cycles, 'x.gpx'));
  }
  for (const name of ['x', '../x.gpx', 'dir\\x.gpx', 'a\nx.gpx', 'a'.repeat(101) + '.gpx']) {
    assert.throws(() => prepareRefinementRequest('job_formal_test_001', example.inputs, 'PbSO4', '3', name));
  }
  for (const phase of ['', ' ', 'a'.repeat(81)]) {
    assert.throws(() => prepareRefinementRequest('job_formal_test_001', example.inputs, phase, '3', 'x.gpx'));
  }
});

test('formal service rejection preserves known codes without displaying raw exception text', async () => {
  for (const code of ['BUSY', 'FILE_NOT_FOUND', 'CORE_NOT_READY', 'PRIVATE_ERROR', '__proto__']) {
    const service = { onEvent: () => () => {},
      startRefinement: async () => { throw { code, message: 'Traceback C:\\private\\secret', detail: '/private/key' }; } };
    const session = new RefinementSession(service, () => {});
    await session.connect(); await session.start(example);
    assert.equal(session.view.error.code, ['PRIVATE_ERROR', '__proto__'].includes(code) ? 'INTERNAL_ERROR' : code);
    assert.doesNotMatch(JSON.stringify(session.view), /Traceback|private|secret/);
    session.disconnect();
  }
});

test('snapshot restoration displays the summary without fabricating event history', () => {
  const view = new RefinementView(); view.jobId = 'job_formal_test_001';
  const restored = receiveSnapshot(view, { jobId: view.jobId, state: 'failed', lastSequence: 3,
    percent: 20, stage: 'reading_files', terminal: { type: 'job.failed', payload: {
      error: { code: 'PROCESS_INTERRUPTED', message: '任务已中断', retryable: true } } } });
  assert.equal(restored.state, 'failed'); assert.equal(restored.message, '任务已中断');
  assert.deepEqual(restored.history, []);
});

test('missing recent snapshot releases the UI for a new task without inventing a failure', async () => {
  const service = { onEvent: () => () => {},
    getJobSnapshot: async () => { throw { code: 'JOB_NOT_FOUND' }; },
    startRefinement: async request => ({ jobId: request.jobId }) };
  const session = new RefinementSession(service, () => {});
  await session.connect('job_missing_recent_01');
  assert.equal(session.view.state, 'idle');
  assert.equal(session.view.error, undefined);
  assert.deepEqual(session.view.history, []);
  assert.match(session.notice, /未找到上次任务/);
  await session.start(example);
  assert.equal(session.view.jobId, example.jobId);
  assert.equal(session.view.state, 'queued');
  session.disconnect();
});

test('a missing snapshot never discards a newer event and other failures remain recoverable', async () => {
  for (const code of ['JOB_NOT_FOUND', 'INTERNAL_ERROR']) {
    for (const emit of [false, true]) {
      let listener;
      const service = { onEvent: callback => { listener = callback; return () => {}; },
        getJobSnapshot: async jobId => {
          if (emit) listener({ jobId, sequence: 2, type: 'job.progress', payload: { state: 'running', percent: 40 } });
          throw { code };
        } };
      const session = new RefinementSession(service, () => {});
      await session.connect('job_restore_race_01');
      assert.equal(session.view.state, emit ? 'running' : code === 'JOB_NOT_FOUND' ? 'idle' : 'queued');
      if (emit) assert.equal(session.view.percent, 40);
      session.disconnect();
    }
  }
});

test('runtime initialization errors use safe UI messages instead of private manifest paths', () => {
  for (const code of ['RUNTIME_NOT_PACKAGED', 'RUNTIME_INVALID_MANIFEST', 'RUNTIME_UNPACK_FAILED']) {
    const error = callError({ code, message: 'Traceback /private/runtime/secret.py' });
    assert.equal(error.code, code);
    assert.doesNotMatch(error.message, /Traceback|private|secret/);
  }
});

test('B03 optional terminal artifacts survive event and snapshot restoration without guessed IDs', () => {
  const log = { fileId: 'file_registered_log_01', kind: 'log', displayName: 'job-log.txt', mediaType: 'text/plain' };
  for (const type of ['job.failed', 'job.cancelled']) {
    for (const artifacts of [undefined, [log]]) {
      const view = new RefinementView(); view.jobId = 'job_terminal_log_01';
      const payload = { error: { code: 'REFINEMENT_FAILED', message: '精修失败', retryable: false }, reason: '用户取消', artifacts };
      const event = receiveEvent(view, { jobId: view.jobId, sequence: 5, type, payload });
      assert.deepEqual(event.terminalArtifacts, artifacts || []);
      const restored = receiveSnapshot(view, { jobId: view.jobId, lastSequence: 5, percent: 50,
        state: type === 'job.failed' ? 'failed' : 'cancelled', stage: null, terminal: { type, payload } });
      assert.deepEqual(restored.terminalArtifacts, artifacts || []);
      assert.deepEqual(restored.history, []);
    }
  }
});

test('starting a new job clears the previous terminal log artifacts', async () => {
  const service = { onEvent: () => () => {}, startRefinement: async request => ({ jobId: request.jobId }) };
  const session = new RefinementSession(service, () => {});
  await session.connect();
  session.view.state = 'failed';
  session.view.terminalArtifacts = [{ fileId: 'file_previous_log_01', kind: 'log', displayName: 'old.log', mediaType: 'text/plain' }];
  await session.start(example);
  assert.deepEqual(session.view.terminalArtifacts, []);
  session.disconnect();
});
