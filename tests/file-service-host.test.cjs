'use strict';

// Exercise the actual ArkTS service on a real POSIX filesystem. Only platform
// IO/URI/hash primitives are adapted. This supplements device tests because
// HarmonyOS API 11+ forbids third-party apps from creating symlink fixtures.
// This is not an ArkTS compiler or a substitute for HarmonyOS device tests.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const { fileURLToPath, pathToFileURL } = require('node:url');
const { test } = require('node:test');
const ts = require(process.env.GSAS_TYPESCRIPT_PATH || 'typescript');
const repo = path.resolve(__dirname, '..');
const modules = new Map();
const asPath = value => {
  if (typeof value !== 'string' || !value.startsWith('file://')) return value;
  const uri = new URL(value);
  if (uri.hostname === 'docs') uri.hostname = '';
  return fileURLToPath(uri);
};
const platformError = error => {
  error.code = { ENOENT: 13900002, EACCES: 13900012, EEXIST: 13900015, ELOOP: 13900033 }[error.code] || 13900042;
  throw error;
};
let beforeExclusiveOpen = undefined;
const io = {
  OpenMode: { READ_ONLY: fs.constants.O_RDONLY, WRITE_ONLY: fs.constants.O_WRONLY,
    CREATE: fs.constants.O_CREAT, TRUNC: fs.constants.O_TRUNC, NOFOLLOW: fs.constants.O_NOFOLLOW },
  lstat: value => fs.promises.lstat(asPath(value)),
  stat: async value => typeof value === 'number' ? fs.fstatSync(value) : fs.promises.stat(asPath(value)),
  mkdir: value => fs.promises.mkdir(value),
  listFile: value => fs.promises.readdir(value),
  readText: value => fs.promises.readFile(value, 'utf8'),
  rename: (from, to) => fs.promises.rename(from, to),
  unlink: value => fs.promises.unlink(value),
  rmdir: value => fs.promises.rm(value, { recursive: true }),
  open: async (value, mode) => {
    try { return { fd: fs.openSync(asPath(value), mode) }; }
    catch (error) {
      throw error;
    }
  },
  close: async file => fs.closeSync(typeof file === 'number' ? file : file.fd),
  fsync: async fd => fs.fsyncSync(fd),
  write: async (fd, bytes) => fs.writeSync(fd, Buffer.from(bytes)),
  access: async value => {
    try { await fs.promises.access(asPath(value)); return true; }
    catch (error) {
      if (error.code !== 'ENOENT') throw error;
      return false;
    }
  },
  copyFile: async (source, destination) => {
    const bytes = typeof source === 'number' ? fs.readFileSync(source) : await fs.promises.readFile(asPath(source));
    if (typeof destination === 'number') {
      fs.writeFileSync(destination, bytes); fs.ftruncateSync(destination, bytes.length);
    } else { await fs.promises.writeFile(asPath(destination), bytes); }
  }
};
for (const key of Object.keys(io)) {
  if (typeof io[key] !== 'function') continue;
  const operation = io[key];
  io[key] = async (...args) => { try { return await operation(...args); } catch (error) { return platformError(error); } };
}
const platform = {
  'libgsas_fileio.so': { openExclusive: uri => {
    if (beforeExclusiveOpen) beforeExclusiveOpen(uri);
    return fs.openSync(asPath(uri), fs.constants.O_WRONLY | fs.constants.O_CREAT | fs.constants.O_EXCL | fs.constants.O_NOFOLLOW | fs.constants.O_CLOEXEC, 0o600);
  } },
  '@kit.CoreFileKit': { fileIo: io,
    fileUri: { FileUri: class { constructor(uri) { this.name = path.basename(fileURLToPath(uri)); } } },
    hash: { hash: async value => crypto.createHash('sha256').update(await fs.promises.readFile(value)).digest('hex').toUpperCase() } },
  '@kit.ArkTS': { util: { generateRandomUUID: crypto.randomUUID,
    TextEncoder: class { encodeInto(text) { return new TextEncoder().encode(text); } } } },
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
const { SandboxFileService } = loadServiceModule(path.join(repo, 'app/entry/src/main/ets/services/SandboxFileService.ets'));
const { FileRole } = loadServiceModule(path.join(repo, 'app/entry/src/main/ets/contracts/Files.ets'));
async function fixture(action) {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'gsas-files-host-'));
  try {
    const root = path.join(base, 'files'); fs.mkdirSync(root);
    const source = path.join(base, 'sample.xra'); fs.writeFileSync(source, 'original bytes\n');
    const service = await SandboxFileService.open(root);
    const file = await service.importFile(pathToFileURL(source).href, FileRole.POWDER_DATA);
    await action({ base, root, source, service, file });
  } finally { fs.rmSync(base, { recursive: true, force: true }); }
}
const rejectsCode = (action, code) => assert.rejects(action, error => error.code === code);

test('a symlink replacing input payload is rejected without changing its external target', () => fixture(async ({ root, source, service, file }) => {
  const payload = await service.resolveInputFile(file.fileId);
  fs.unlinkSync(payload); fs.symlinkSync(source, payload);
  await rejectsCode(() => service.getFile(file.fileId), 'INVALID_REQUEST');
  await rejectsCode(() => service.exportFile(file.fileId, pathToFileURL(path.join(root, 'export.xra')).href), 'INVALID_REQUEST');
  assert.equal(fs.readFileSync(source, 'utf8'), 'original bytes\n');
}));

test('a symlink replacing an input directory cannot escape through read or deletion', () => fixture(async ({ base, root, service, file }) => {
  const external = path.join(base, 'external'); fs.mkdirSync(external);
  fs.writeFileSync(path.join(external, file.displayName), 'keep me');
  const directory = path.join(root, 'imports', file.fileId); fs.rmSync(directory, { recursive: true });
  fs.symlinkSync(external, directory);
  await rejectsCode(() => service.getFile(file.fileId), 'INVALID_REQUEST');
  await rejectsCode(() => service.deleteFile(file.fileId), 'INVALID_REQUEST');
  assert.equal(fs.readFileSync(path.join(external, file.displayName), 'utf8'), 'keep me');
}));

test('root and metadata directory symlinks are rejected on reopen', () => fixture(async ({ base, root }) => {
  const alias = path.join(base, 'root-alias'); fs.symlinkSync(root, alias);
  await rejectsCode(() => SandboxFileService.open(alias), 'INVALID_REQUEST');
  const metadata = path.join(root, 'metadata/files');
  fs.renameSync(metadata, `${metadata}-backup`); fs.symlinkSync(`${metadata}-backup`, metadata);
  await rejectsCode(() => SandboxFileService.open(root), 'INVALID_REQUEST');
}));

test('output symlinks cannot be registered, and a normal output has a single fileId owner', () => fixture(async ({ root, source, service }) => {
  const jobId = 'job_host_check_0001'; await service.beginJob(jobId, []);
  const output = path.join(root, 'outputs', jobId, 'result.json'); fs.symlinkSync(source, output);
  await rejectsCode(() => service.registerOutput(jobId, 'file_host_output_001', 'result.json', 'result'), 'INVALID_REQUEST');
  fs.unlinkSync(output); fs.writeFileSync(output, '{"actual":true}\n');
  const registered = await service.registerOutput(jobId, 'file_host_output_001', 'result.json', 'result');
  await rejectsCode(() => service.registerOutput(jobId, 'file_host_output_002', 'result.json', 'result'), 'INVALID_REQUEST');
  assert.deepEqual(await service.getFile(registered.fileId), registered);
  await service.finishJob(jobId);
}));

test('export rejects existing empty files and symlink destinations', () => fixture(async ({ base, source, service, file }) => {
  const empty = path.join(base, 'empty.xra'); fs.writeFileSync(empty, '');
  await rejectsCode(() => service.exportFile(file.fileId, pathToFileURL(empty).href), 'OUTPUT_WRITE_FAILED');
  assert.equal(fs.statSync(empty).size, 0);
  const link = path.join(base, 'export-link.xra'); fs.symlinkSync(source, link);
  await rejectsCode(() => service.exportFile(file.fileId, pathToFileURL(link).href), 'OUTPUT_WRITE_FAILED');
  assert.equal(fs.readFileSync(source, 'utf8'), 'original bytes\n');
}));

test('invalid deletion marker fails closed on reopen', () => fixture(async ({ root, file }) => {
  const index = path.join(root, 'metadata/files', `${file.fileId}.json`);
  const record = JSON.parse(fs.readFileSync(index, 'utf8')); record.deleting = 'false';
  fs.writeFileSync(index, JSON.stringify(record));
  await rejectsCode(() => SandboxFileService.open(root), 'INVALID_REQUEST');
  assert.ok(fs.existsSync(path.join(root, 'imports', file.fileId, file.displayName)));
}));

// A real external writer acts immediately before the exclusive creation syscall. Keep this
// regression visible until export supports atomic exclusive creation.
test('export preserves an empty destination created concurrently by another writer',
  () => fixture(async ({ base, service, file }) => {
    const destination = path.join(base, 'concurrent.xra');
    const uri = pathToFileURL(destination).href;
    beforeExclusiveOpen = value => { if (value === uri) fs.writeFileSync(destination, ''); };
    try {
      await rejectsCode(() => service.exportFile(file.fileId, uri), 'OUTPUT_WRITE_FAILED');
      assert.equal(fs.statSync(destination).size, 0);
    } finally { beforeExclusiveOpen = undefined; }
  }));

test('version-1 metadata without a deletion marker survives an upgrade', () => fixture(async ({ root, file }) => {
  const index = path.join(root, 'metadata/files', `${file.fileId}.json`);
  const record = JSON.parse(fs.readFileSync(index, 'utf8')); delete record.deleting;
  fs.writeFileSync(index, JSON.stringify(record));
  const reopened = await SandboxFileService.open(root);
  assert.equal((await reopened.getFile(file.fileId)).sha256, file.sha256);
  await reopened.deleteFile(file.fileId);
  await rejectsCode(() => reopened.getFile(file.fileId), 'FILE_NOT_FOUND');
}));

test('a save-picker reserved empty document is filled, while a nonempty document is preserved', () => fixture(async ({ base, service, file }) => {
  const destination = path.join(base, 'reserved.xra'); fs.writeFileSync(destination, '');
  const uri = pathToFileURL(destination).href.replace('file:///', 'file://docs/');
  await service.exportFile(file.fileId, uri);
  assert.equal(fs.readFileSync(destination, 'utf8'), 'original bytes\n');
  await rejectsCode(() => service.exportFile(file.fileId, uri), 'OUTPUT_WRITE_FAILED');
  assert.equal(fs.readFileSync(destination, 'utf8'), 'original bytes\n');
}));
