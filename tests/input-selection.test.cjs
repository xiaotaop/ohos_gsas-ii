'use strict';
// Executes the actual ArkTS input model. Device/ArkTS validation is separate.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require(process.env.GSAS_TYPESCRIPT_PATH || 'typescript');
const root = path.join(__dirname, '../app/entry/src/main/ets');
const modules = new Map();
function load(filename) {
  if (modules.has(filename)) return modules.get(filename).exports;
  const module = { exports: {} };
  modules.set(filename, module);
  const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    fileName: filename, compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS }
  }).outputText;
  const localRequire = name => {
    assert.ok(name.startsWith('.'), `unexpected platform dependency: ${name}`);
    return load(path.resolve(path.dirname(filename), name + '.ets'));
  };
  vm.runInThisContext(`(function(require,module,exports){${code}\n})`, { filename })(localRequire, module, module.exports);
  return module.exports;
}
const { InputSelection, InputSlot, INPUT_SLOTS, draftScope } = load(path.join(root, 'model/RefinementInputs.ets'));
const { FileRole, FileServiceError } = load(path.join(root, 'contracts/Files.ets'));
const files = INPUT_SLOTS.map((slot, index) => ({
  fileId: `file_explicit_${index}`, displayName: 'same-name.dat', role: slot.role, size: 12, sha256: 'A'.repeat(64)
}));
function filled() {
  const selection = new InputSelection();
  INPUT_SLOTS.forEach((slot, index) => selection.select(slot.id, files[index]));
  return selection;
}
const library = { getFile: async id => files.find(file => file.fileId === id) };

test('five explicit associations yield the frozen inputs shape without guessing from file names or roles', async () => {
  const selection = filled();
  assert.deepEqual(await selection.verify(library), {
    histograms: [
      { id: 'xray', role: 'xray', dataFileId: 'file_explicit_0', instrumentFileId: 'file_explicit_1', formatHint: 'GSAS powder' },
      { id: 'neutron', role: 'neutron', dataFileId: 'file_explicit_2', instrumentFileId: 'file_explicit_3', formatHint: 'GSAS powder' }
    ],
    phase: { id: 'phase', name: 'Selected phase', fileId: 'file_explicit_4' }
  });
  const saved = JSON.parse(selection.serialize());
  assert.deepEqual(Object.keys(saved).sort(), ['bindings', 'version']);
  assert.ok(saved.bindings.every(binding => Object.keys(binding).sort().join(',') === 'fileId,slot'));
  const reopened = new InputSelection();
  assert.equal(reopened.restore(selection.serialize(), files), 0);
  assert.deepEqual(await reopened.verify(library), await selection.verify(library));
});

test('reselection leaves old files intact; deletion removes only the stale association on restore', () => {
  const selection = filled();
  const old = selection.serialize();
  selection.select(InputSlot.XRAY_DATA, files[2]);
  assert.equal(selection.entries().find(item => item.slot === InputSlot.XRAY_DATA).fileId, files[2].fileId);
  assert.equal(files.length, 5);
  const reopened = new InputSelection();
  assert.equal(reopened.restore(old, files.filter(file => file.fileId !== files[1].fileId)), 1);
  assert.equal(reopened.entries().length, 4);
  assert.ok(reopened.entries().some(item => item.slot === InputSlot.NEUTRON_INSTRUMENT));
  assert.throws(() => selection.select(InputSlot.PHASE, files[0]), error => error.code === 'INVALID_REQUEST');
});

test('malformed persisted data does not partially replace existing selections or accept paths', () => {
  const selection = filled();
  const before = selection.serialize();
  for (const input of ['null', '{}', '{', '{"version":2,"bindings":[]}', JSON.stringify({ version: 1, bindings: [
    { slot: InputSlot.XRAY_DATA, fileId: 'file_explicit_0' }, { slot: InputSlot.PHASE, fileId: '/private/data/file.cif' }
  ] }), JSON.stringify({ version: 1, bindings: [
    { slot: InputSlot.XRAY_DATA, fileId: 'file_explicit_0' }, { slot: InputSlot.XRAY_DATA, fileId: 'file_explicit_2' }
  ] })]) {
    assert.throws(() => selection.restore(input, files), error => error.code === 'INVALID_REQUEST');
    assert.equal(selection.serialize(), before);
  }
  const changedRoles = files.map(file => ({ ...file }));
  changedRoles[0].role = FileRole.PROJECT;
  assert.equal(selection.restore(before, changedRoles), 1);
});

test('preparation requires every slot and real getFile verification propagates hash/missing-file errors', async () => {
  const selection = filled();
  const checked = [];
  await selection.verify({ getFile: async id => { checked.push(id); return library.getFile(id); } });
  assert.deepEqual(checked, files.map(file => file.fileId));
  for (const code of ['FILE_HASH_MISMATCH', 'FILE_NOT_FOUND']) {
    await assert.rejects(selection.verify({ getFile: async () => { throw new FileServiceError(code, '输入不可用'); } }),
      error => error.code === code);
  }
  selection.clear(InputSlot.PHASE);
  await assert.rejects(selection.verify(library), error => error.code === 'INVALID_REQUEST');
});

test('selection changes during asynchronous checks cannot mix input generations', async () => {
  const selection = filled();
  let release;
  const wait = new Promise(resolve => { release = resolve; });
  const prepared = selection.verify({ getFile: async id => { await wait; return library.getFile(id); } });
  selection.select(InputSlot.XRAY_DATA, files[2]);
  release();
  assert.equal((await prepared).histograms[0].dataFileId, files[0].fileId);
  assert.equal((await selection.verify(library)).histograms[0].dataFileId, files[2].fileId);
});

test('notebook is application-local; comments follow powder file identity, not unrelated inputs or slots', () => {
  const selection = filled();
  const original = selection.entries();
  assert.equal(draftScope('Notebook', []), 'Notebook|local-v1');
  assert.equal(draftScope('Notebook', original), 'Notebook|local-v1');
  assert.equal(draftScope('xray:Comments', []), '');
  assert.equal(draftScope('xray:Comments', original), 'Comments|file_explicit_0');
  assert.equal(draftScope('neutron:Comments', original), 'Comments|file_explicit_2');
  selection.clear(InputSlot.PHASE); selection.clear(InputSlot.XRAY_INSTRUMENT);
  assert.equal(draftScope('xray:Comments', selection.entries()), 'Comments|file_explicit_0');
  selection.select(InputSlot.XRAY_DATA, files[2]);
  assert.equal(draftScope('xray:Comments', selection.entries()), 'Comments|file_explicit_2');
  selection.select(InputSlot.XRAY_DATA, files[0]);
  assert.equal(draftScope('xray:Comments', selection.entries()), 'Comments|file_explicit_0');
  assert.equal(draftScope('Controls', original),
    'Controls|neutron-data=file_explicit_2|neutron-instrument=file_explicit_3|phase=file_explicit_4|xray-data=file_explicit_0|xray-instrument=file_explicit_1');
  assert.equal(draftScope('Controls', original.slice().reverse()), draftScope('Controls', original));
});
