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
const { prepareRefinementRequest, RefinementSession, RefinementView, receiveSnapshot } = require(process.env.GSAS_FORMAL_MODEL);
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
