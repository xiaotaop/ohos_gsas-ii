'use strict';

// Exercise the actual ArkTS RuntimeInstaller against a real POSIX filesystem
// with an in-memory rawfile copy. Only platform IO/hash/UUID primitives are
// adapted. This is not an ArkTS compiler or a substitute for HarmonyOS device
// tests.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const ts = require(process.env.GSAS_TYPESCRIPT_PATH || 'typescript');
const repo = path.resolve(__dirname, '..');
// The service guards filesDir.startsWith('/'); on Windows hosts we must keep
// POSIX-style strings (they resolve against the current drive) so the suite
// also runs locally, not only on the Ubuntu CI runner.
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
const { RuntimeInstaller } = loadServiceModule(path.join(repo, 'app/entry/src/main/ets/services/RuntimeInstaller.ets'));

const sha = bytes => crypto.createHash('sha256').update(Buffer.from(bytes)).digest('hex');

class MemorySource {
  constructor(tree) { this.tree = new Map(Object.entries(tree)); this.textReads = 0; this.byteReads = 0; }
  async readText(name) {
    this.textReads += 1;
    const value = this.tree.get(name);
    if (value === undefined) throw new Error(`missing rawfile ${name}`);
    return Buffer.from(value).toString('utf8');
  }
  async readBytes(name) {
    this.byteReads += 1;
    const value = this.tree.get(name);
    if (value === undefined) throw new Error(`missing rawfile ${name}`);
    return new Uint8Array(value);
  }
}

/** Build a rawfile tree plus the manifest.json the generator would ship with it. */
function rawfile(runtimeId, files) {
  const tree = {};
  for (const [rel, bytes] of Object.entries(files)) tree[rel] = bytes;
  const entries = Object.keys(files)
    .filter(rel => rel.startsWith('runtime/') && rel !== 'runtime/manifest.json')
    .map(rel => rel.slice('runtime/'.length))
    .sort()
    .map(rel => ({ path: rel, sha256: sha(files[`runtime/${rel}`]), size: files[`runtime/${rel}`].length }));
  tree['runtime/manifest.json'] = Buffer.from(JSON.stringify({ schemaVersion: 1, runtimeId, files: entries }));
  return new MemorySource(tree);
}

async function fixture(action) {
  fs.mkdirSync('/tmp', { recursive: true });
  const base = fs.mkdtempSync('/tmp/gsas-runtime-host-');
  try {
    const root = posixJoin(base, 'files');
    fs.mkdirSync(root);
    fs.mkdirSync(posixJoin(root, 'runtime'));  // SandboxFileService.initialize creates this.
    await action({ base, root });
  } finally { fs.rmSync(base, { recursive: true, force: true }); }
}
const rejectsCode = (action, code) => assert.rejects(action, error => error.code === code);

test('a fresh payload is unpacked, verified and activated', () => fixture(async ({ root }) => {
  const source = rawfile('test-runtime.1', {
    'runtime/lib/python3.12/encodings/__init__.py': Buffer.from('# stub\n'),
    'runtime/bridge/__init__.py': Buffer.from('# bridge\n')
  });
  assert.equal(await RuntimeInstaller.install(source, root), 'test-runtime.1');
  assert.equal(fs.readFileSync(posixJoin(root, 'runtime/lib/python3.12/encodings/__init__.py'), 'utf8'), '# stub\n');
  const marker = JSON.parse(fs.readFileSync(posixJoin(root, 'runtime/.activation'), 'utf8'));
  assert.equal(marker.runtimeId, 'test-runtime.1');
  assert.equal(marker.schemaVersion, 1);
  assert.equal(await RuntimeInstaller.activatedRuntimeId(root), 'test-runtime.1');
}));

test('a re-identified runtime id is skipped without re-reading payload bytes', () => fixture(async ({ root }) => {
  const source = rawfile('test-runtime.1', { 'runtime/x.py': Buffer.from('x\n') });
  await RuntimeInstaller.install(source, root);
  const reads = source.byteReads;
  assert.equal(await RuntimeInstaller.install(source, root), 'test-runtime.1');
  assert.equal(source.byteReads, reads);
  assert.ok(source.textReads > 0);  // the manifest is still consulted
}));

test('a tampered upgrade leaves the activated runtime byte-identical', () => fixture(async ({ root }) => {
  await RuntimeInstaller.install(rawfile('test-runtime.1', { 'runtime/x.py': Buffer.from('good\n') }), root);
  const source = rawfile('test-runtime.2', { 'runtime/x.py': Buffer.from('good\n') });
  // Manifest claims a hash the payload does not have.
  const document = JSON.parse(source.tree.get('runtime/manifest.json').toString('utf8'));
  document.files[0].sha256 = sha(Buffer.from('evil\n'));
  source.tree.set('runtime/manifest.json', Buffer.from(JSON.stringify(document)));
  await rejectsCode(() => RuntimeInstaller.install(source, root), 'RUNTIME_UNPACK_FAILED');
  assert.equal(fs.readFileSync(posixJoin(root, 'runtime/x.py'), 'utf8'), 'good\n');
  assert.equal(await RuntimeInstaller.activatedRuntimeId(root), 'test-runtime.1');
}));

test('an upgrade swaps whole directories so dropped modules cannot linger', () => fixture(async ({ root }) => {
  await RuntimeInstaller.install(rawfile('test-runtime.1', {
    'runtime/x.py': Buffer.from('v1\n'), 'runtime/removed.py': Buffer.from('gone in v2\n')
  }), root);
  assert.equal(await RuntimeInstaller.install(rawfile('test-runtime.2', { 'runtime/x.py': Buffer.from('v2\n') }), root), 'test-runtime.2');
  assert.equal(fs.readFileSync(posixJoin(root, 'runtime/x.py'), 'utf8'), 'v2\n');
  assert.equal(fs.existsSync(posixJoin(root, 'runtime/removed.py')), false);
  assert.equal(fs.existsSync(posixJoin(root, 'runtime-next')), false);
  assert.equal(fs.existsSync(posixJoin(root, 'runtime-previous')), false);
}));

test('a crash between the swap renames is recovered on next install', () => fixture(async ({ root }) => {
  await RuntimeInstaller.install(rawfile('test-runtime.1', { 'runtime/x.py': Buffer.from('v1\n') }), root);
  // Reproduce the window after rename(runtime -> backup) but before rename(next -> runtime).
  fs.renameSync(posixJoin(root, 'runtime'), posixJoin(root, 'runtime-previous'));
  fs.mkdirSync(posixJoin(root, 'runtime-next'));
  fs.writeFileSync(posixJoin(root, 'runtime-next/stale.py'), 'abandoned attempt\n');
  assert.equal(await RuntimeInstaller.install(rawfile('test-runtime.1', { 'runtime/x.py': Buffer.from('v1\n') }), root), 'test-runtime.1');
  assert.equal(fs.readFileSync(posixJoin(root, 'runtime/x.py'), 'utf8'), 'v1\n');
  assert.equal(fs.existsSync(posixJoin(root, 'runtime-previous')), false);
  assert.equal(fs.existsSync(posixJoin(root, 'runtime-next')), false);
}));

test('a missing payload fails closed and never fakes activation', () => fixture(async ({ root }) => {
  await rejectsCode(() => RuntimeInstaller.install(new MemorySource({}), root), 'RUNTIME_INVALID_MANIFEST');
  assert.equal(await RuntimeInstaller.activatedRuntimeId(root), '');
}));

test('invalid manifests are rejected before any byte is written', () => fixture(async ({ root }) => {
  const cases = {
    'uppercase hash': { schemaVersion: 1, runtimeId: 'x.1',
      files: [{ path: 'a.py', sha256: 'A'.repeat(64), size: 2 }] },
    'traversal path': { schemaVersion: 1, runtimeId: 'x.1',
      files: [{ path: '../escape.py', sha256: 'a'.repeat(64), size: 2 }] },
    'absolute path': { schemaVersion: 1, runtimeId: 'x.1',
      files: [{ path: '/etc/passwd', sha256: 'a'.repeat(64), size: 2 }] },
    'zero size': { schemaVersion: 1, runtimeId: 'x.1',
      files: [{ path: 'a.py', sha256: 'a'.repeat(64), size: 0 }] },
    'bad runtime id': { schemaVersion: 1, runtimeId: 'BAD ID',
      files: [{ path: 'a.py', sha256: 'a'.repeat(64), size: 2 }] },
    'duplicate path': { schemaVersion: 1, runtimeId: 'x.1',
      files: [{ path: 'a.py', sha256: 'a'.repeat(64), size: 2 }, { path: 'A.PY', sha256: 'b'.repeat(64), size: 2 }] },
    'empty file list': { schemaVersion: 1, runtimeId: 'x.1', files: [] }
  };
  for (const [label, document] of Object.entries(cases)) {
    const source = new MemorySource({ 'runtime/manifest.json': Buffer.from(JSON.stringify(document)) });
    await rejectsCode(() => RuntimeInstaller.install(source, root), 'RUNTIME_INVALID_MANIFEST');
    assert.equal(await RuntimeInstaller.activatedRuntimeId(root), '', label);
    assert.deepEqual(fs.readdirSync(posixJoin(root, 'runtime')), [], label);
  }
}));

test('a corrupt marker means not activated and is replaced on success', () => fixture(async ({ root }) => {
  fs.writeFileSync(posixJoin(root, 'runtime/.activation'), 'garbage{');
  assert.equal(await RuntimeInstaller.activatedRuntimeId(root), '');
  assert.equal(await RuntimeInstaller.install(rawfile('test-runtime.1', { 'runtime/x.py': Buffer.from('v1\n') }), root), 'test-runtime.1');
  assert.equal(await RuntimeInstaller.activatedRuntimeId(root), 'test-runtime.1');
}));

test('a manifest entry whose rawfile bytes are missing aborts without activation', () => fixture(async ({ root }) => {
  const source = rawfile('test-runtime.1', { 'runtime/x.py': Buffer.from('v1\n') });
  source.tree.delete('runtime/x.py');
  await rejectsCode(() => RuntimeInstaller.install(source, root), 'RUNTIME_UNPACK_FAILED');
  assert.equal(await RuntimeInstaller.activatedRuntimeId(root), '');
  assert.deepEqual(fs.readdirSync(posixJoin(root, 'runtime')), []);
  assert.equal(fs.existsSync(posixJoin(root, 'runtime-next')), false);
}));

test('install rejects a filesDir escape attempt', async () => {
  await rejectsCode(() => RuntimeInstaller.install(new MemorySource({}), 'relative/dir'), 'INVALID_REQUEST');
  await rejectsCode(() => RuntimeInstaller.install(new MemorySource({}), '/data/../etc'), 'INVALID_REQUEST');
});
