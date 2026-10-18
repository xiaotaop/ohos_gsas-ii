const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require(process.env.GSAS_TYPESCRIPT_PATH || 'typescript');
const source = fs.readFileSync('app/entry/src/main/ets/model/ParameterDrafts.ets', 'utf8');
const output = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS } }).outputText;
const model = { exports: {} };
vm.runInThisContext(`(function(exports){${output}\n})`)(model.exports);
const { parameterFields, visibleParameters, validateParameters, serializeParameters, restoreParameters } = model.exports;
function set(fields, key, value, refine = false) { const f = fields.find(f => f.key === key); f.value = value; f.refine = refine; }
const keys = (panel, fields) => visibleParameters(panel, fields).map(f => f.key);

test('no fabricated initial values, refinement flags or implicit instrument type', () => {
  for (const panel of ['Controls', 'Limits', 'Background', 'Instrument Parameters', 'Sample Parameters']) {
    const fields = parameterFields(panel);
    assert.ok(fields.every(f => f.value === '' && !f.refine));
    assert.equal(validateParameters(panel, fields), '');
  }
  assert.deepEqual(keys('Instrument Parameters', parameterFields('Instrument Parameters')), ['type']);
});
test('upstream refinement methods select the correct controls and numeric bounds', () => {
  const fields = parameterFields('Controls'); set(fields, 'method', 'analytic Hessian');
  assert.ok(keys('Controls', fields).includes('lambda')); assert.ok(!keys('Controls', fields).includes('shift'));
  set(fields, 'method', 'Hessian SVD'); assert.ok(!keys('Controls', fields).includes('lambda'));
  set(fields, 'method', 'numeric'); assert.ok(keys('Controls', fields).includes('shift')); assert.ok(!keys('Controls', fields).includes('cycles'));
  for (const bad of ['NaN', 'Infinity', '0x10', '1e-10', '2']) { set(fields, 'delta', bad); assert.notEqual(validateParameters('Controls', fields), ''); }
  set(fields, 'delta', '1e-9'); set(fields, 'shift', '100'); assert.equal(validateParameters('Controls', fields), '');
});
test('range drafts reject incomplete and reversed ranges', () => {
  const fields = parameterFields('Limits'); set(fields, 'lower', '10');
  assert.notEqual(validateParameters('Limits', fields), ''); set(fields, 'upper', '5');
  assert.notEqual(validateParameters('Limits', fields), ''); set(fields, 'upper', '80');
  assert.equal(validateParameters('Limits', fields), '');
});
test('background coefficient count and refine flag validation', () => {
  const fields = parameterFields('Background'); set(fields, 'count', '3');
  assert.deepEqual(keys('Background', fields), ['function', 'count', 'b0', 'b1', 'b2']);
  set(fields, 'function', '', true); assert.notEqual(validateParameters('Background', fields), '');
  set(fields, 'function', 'chebyschev-1', true); set(fields, 'b0', '100'); set(fields, 'b1', '-2.5');
  assert.equal(validateParameters('Background', fields), '');
});
test('CW and TOF are explicit templates; sample geometry changes its fields', () => {
  const fields = parameterFields('Instrument Parameters'); set(fields, 'type', 'PNT');
  assert.ok(keys('Instrument Parameters', fields).includes('difC')); assert.ok(!keys('Instrument Parameters', fields).includes('Lam'));
  set(fields, 'type', 'PNC'); assert.ok(keys('Instrument Parameters', fields).includes('Lam')); assert.ok(!keys('Instrument Parameters', fields).includes('Polariz.'));
  const sample = parameterFields('Sample Parameters'); set(sample, 'geometry', 'Bragg-Brentano');
  assert.ok(keys('Sample Parameters', sample).includes('Transparency')); assert.ok(!keys('Sample Parameters', sample).includes('Absorption'));
});
test('saved draft round trips without changing original fields; different input scope is rejected', () => {
  const original = parameterFields('Controls'); const fields = parameterFields('Controls');
  set(fields, 'method', 'analytic Hessian'); set(fields, 'cycles', '5');
  const json = serializeParameters('Controls', 'Controls|file_source_a', fields);
  const reopened = restoreParameters('Controls', 'Controls|file_source_a', json);
  assert.equal(reopened.find(f => f.key === 'cycles').value, '5');
  assert.ok(original.every(f => f.value === '')); // cancelling an editor leaves its source intact
  assert.throws(() => restoreParameters('Controls', 'Controls|file_source_b', json));
  assert.ok(!json.includes('recipe') && !json.includes('cycleCount'));
});
test('corrupt persisted drafts cannot replace descriptor bounds or smuggle unknown fields', () => {
  const fields = parameterFields('Controls'); set(fields, 'delta', '0.001');
  const valid = JSON.parse(serializeParameters('Controls', 'c', fields));
  for (const change of [r => r.version = 2, r => r.fields.push(r.fields[0]), r => r.fields[0].key = 'path',
    r => { const f = r.fields.find(f => f.key === 'delta'); f.min = -100; f.value = '-1'; }]) {
    const record = JSON.parse(JSON.stringify(valid)); change(record);
    assert.throws(() => restoreParameters('Controls', 'c', JSON.stringify(record)));
  }
});

test('hidden method and instrument drafts survive save and reopening', () => {
  const controls = parameterFields('Controls');
  set(controls, 'method', 'analytic Hessian'); set(controls, 'cycles', '5'); set(controls, 'lambda', '-2');
  set(controls, 'method', 'numeric'); set(controls, 'shift', '0.5');
  const reopened = restoreParameters('Controls', 'c', serializeParameters('Controls', 'c', controls));
  set(reopened, 'method', 'analytic Hessian');
  assert.equal(reopened.find(f => f.key === 'cycles').value, '5');
  assert.equal(reopened.find(f => f.key === 'lambda').value, '-2');
  const instrument = parameterFields('Instrument Parameters');
  set(instrument, 'type', 'PNT'); set(instrument, 'difC', '1234', true);
  set(instrument, 'type', 'PXC'); set(instrument, 'Lam', '1.5406');
  const saved = restoreParameters('Instrument Parameters', 'i', serializeParameters('Instrument Parameters', 'i', instrument));
  assert.equal(saved.find(f => f.key === 'difC').value, '1234');
  assert.equal(saved.find(f => f.key === 'difC').refine, true);
});

test('whitespace-only limits are empty, hidden invalid data and mismatched panel are rejected', () => {
  const limits = parameterFields('Limits'); set(limits, 'lower', ' '); set(limits, 'upper', '  ');
  assert.equal(validateParameters('Limits', limits), '');
  set(limits, 'upper', '20'); assert.notEqual(validateParameters('Limits', limits), '');
  const controls = parameterFields('Controls'); set(controls, 'method', 'numeric'); set(controls, 'cycles', '99');
  assert.throws(() => serializeParameters('Controls', 'c', controls));
  const json = serializeParameters('Limits', 'c', parameterFields('Limits'));
  assert.throws(() => restoreParameters('Controls', 'c', json));
});

test('all 36 background coefficients fit Preferences string limit without persisting descriptors', () => {
  const fields = parameterFields('Background'); set(fields, 'function', 'chebyschev'); set(fields, 'count', '36');
  for (let i = 0; i < 36; i++) set(fields, `b${i}`, '0.' + '1'.repeat(62));
  const scope = 'xray:Background|' + 'file_'.padEnd(69, 'a').repeat(5);
  const json = serializeParameters('Background', scope, fields);
  assert.ok(json.length < 8192);
  assert.deepEqual(Object.keys(JSON.parse(json).fields[0]).sort(), ['key', 'refine', 'value']);
  assert.equal(restoreParameters('Background', scope, json).find(f => f.key === 'b35').value, '0.' + '1'.repeat(62));
});
