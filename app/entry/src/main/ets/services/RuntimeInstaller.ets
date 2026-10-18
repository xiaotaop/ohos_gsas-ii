// Device-side runtimeRoot unpacking and activation for the payload prepared
// under RUNTIME_PACKAGING §2/§3. The host tooling assembles and audits the
// package but explicitly does not unpack, activate or roll back the runtime
// inside the app sandbox; this file implements that missing half. rawfile is
// the immutable, system-verified copy; the sandbox is the working root. The
// activation marker is written only after every manifest file has re-
// verified, so a failed or interrupted install never brands an incomplete
// tree as ready, and an upgrade with a mismatched id rebuilds from scratch.
import { fileIo as fs, hash } from '@kit.CoreFileKit';
import { util } from '@kit.ArkTS';
import { resourceManager } from '@kit.LocalizationKit';
import { FileServiceError } from '../contracts/Files';

/** One registered file inside rawfile/runtime/manifest.json. */
export class RuntimeFileEntry {
  path: string = '';
  sha256: string = '';
  size: number = 0;
}

export class RuntimeManifestDocument {
  schemaVersion: number = 0;
  runtimeId: string = '';
  files: RuntimeFileEntry[] = [];
}

class ActivationMarker {
  schemaVersion: number = 0;
  runtimeId: string = '';
  activatedAt: string = '';
}

/** Raw-file seam; host tests provide an in-memory source. */
export interface RawFileSource {
  readText(name: string): Promise<string>;
  readBytes(name: string): Promise<Uint8Array>;
}

/** Production source backed by the HAP resource manager. */
export class HapRawFileSource implements RawFileSource {
  private manager: resourceManager.ResourceManager;

  constructor(manager: resourceManager.ResourceManager) {
    this.manager = manager;
  }

  async readBytes(name: string): Promise<Uint8Array> {
    try {
      return await this.manager.getRawFileContent(name);
    } catch (error) {
      throw new FileServiceError('RUNTIME_NOT_PACKAGED', '安装包内没有运行时载荷，请使用装配了运行时的构建。', true);
    }
  }

  async readText(name: string): Promise<string> {
    return util.TextDecoder.create('utf-8').decodeToString(await this.readBytes(name));
  }
}

export class RuntimeInstaller {
  /** Install rawfile/runtime into filesDir/runtime and activate it.
   * Returns the activated runtimeId. Callers serialize invocations.
   */
  static async install(source: RawFileSource, filesDir: string): Promise<string> {
    if (!filesDir.startsWith('/') || filesDir.split('/').includes('..')) {
      throw new FileServiceError('INVALID_REQUEST', '应用文件目录无效。');
    }
    const root = filesDir.replace(/\/$/, '');
    try {
      return await RuntimeInstaller.installInside(source, root);
    } catch (error) {
      try {
        // A clean failure leaves no half-built scratch behind; a crash is
        // covered because the next attempt clears the scratch directory first.
        if (await fs.access(`${root}/runtime-next`)) { await RuntimeInstaller.removeTree(`${root}/runtime-next`); }
      } catch (cleanupError) { /* retried by the next attempt */ }
      if (error instanceof FileServiceError) { throw error; }
      throw new FileServiceError('RUNTIME_UNPACK_FAILED', '运行时装配未完成，请重试。', true);
    }
  }

  /** Runtime id fully unpacked and verified earlier; '' when not activated. */
  static async activatedRuntimeId(filesDir: string): Promise<string> {
    return await RuntimeInstaller.readMarker(`${filesDir.replace(/\/$/, '')}/runtime/.activation`);
  }

  private static async installInside(source: RawFileSource, root: string): Promise<string> {
    let document: RuntimeManifestDocument;
    try {
      const text = await source.readText('runtime/manifest.json');
      document = JSON.parse(text) as RuntimeManifestDocument;
    } catch (error) {
      if (error instanceof FileServiceError) { throw error; }
      throw new FileServiceError('RUNTIME_INVALID_MANIFEST', '运行时装配清单损坏。');
    }
    const entries = RuntimeInstaller.validate(document);
    const runtimeDir = `${root}/runtime`;
    const nextDir = `${root}/runtime-next`;
    const backupDir = `${root}/runtime-previous`;
    if (await fs.access(nextDir)) {
      await RuntimeInstaller.removeTree(nextDir);  // Scratch left by an abandoned attempt.
    }
    if ((await fs.access(runtimeDir)) && (await fs.access(backupDir))) {
      // A completed swap whose stale backup never got cleaned.
      await RuntimeInstaller.removeTree(backupDir);
    }
    const previous = await RuntimeInstaller.readMarker(`${runtimeDir}/.activation`);
    if (previous === document.runtimeId) {
      // Bytes were fully verified when this id was activated; the rawfile
      // copy is immutable, so re-hashing the whole tree on every start is
      // the only cost we can skip safely.
      return document.runtimeId;
    }
    if (await RuntimeInstaller.recoverSwap(backupDir, runtimeDir, document.runtimeId)) {
      return document.runtimeId;
    }
    await RuntimeInstaller.mkdirp(nextDir);
    for (const entry of entries) {
      await RuntimeInstaller.unpack(source, entry, `${nextDir}/${entry.path}`);
    }
    // Verify the staged tree in full before the live root is touched at all:
    // the activation marker must never describe a partially copied directory.
    for (const entry of entries) {
      if (!(await RuntimeInstaller.verifiedFile(`${nextDir}/${entry.path}`, entry.sha256, entry.size))) {
        throw new FileServiceError('RUNTIME_UNPACK_FAILED', `运行时装配校验失败：${entry.path}`, true);
      }
    }
    await RuntimeInstaller.writeMarker(`${nextDir}/.activation`, document.runtimeId);
    // Publish by directory swap: the previously activated tree only leaves
    // place once the new tree is complete, verified, and carrying its own
    // activation marker. Rollback is activating an older id again.
    if (await fs.access(runtimeDir)) { await fs.rename(runtimeDir, backupDir); }
    await fs.rename(nextDir, runtimeDir);
    if (await fs.access(backupDir)) { await RuntimeInstaller.removeTree(backupDir); }
    return document.runtimeId;
  }

  /** Finish an interrupted directory swap after a crash between renames.
   * Returns true when the restored tree is already activated for this id.
   */
  private static async recoverSwap(backupDir: string, runtimeDir: string, runtimeId: string): Promise<boolean> {
    if (await fs.access(runtimeDir)) { return false; }
    if (!(await fs.access(backupDir))) { return false; }
    await fs.rename(backupDir, runtimeDir);
    return (await RuntimeInstaller.readMarker(`${runtimeDir}/.activation`)) === runtimeId;
  }

  private static validate(document: RuntimeManifestDocument): RuntimeFileEntry[] {
    if (document.schemaVersion !== 1 || typeof document.runtimeId !== 'string'
      || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/.test(document.runtimeId)
      || !Array.isArray(document.files) || document.files.length === 0) {
      throw new FileServiceError('RUNTIME_INVALID_MANIFEST', '运行时装配清单无效。');
    }
    const seen = new Set<string>();
    for (const entry of document.files) {
      if (!entry || typeof entry.path !== 'string' || typeof entry.sha256 !== 'string'
        || !Number.isSafeInteger(entry.size) || entry.size <= 0) {
        throw new FileServiceError('RUNTIME_INVALID_MANIFEST', '运行时装配清单条目无效。');
      }
      if (!/^[0-9a-f]{64}$/.test(entry.sha256)) {
        throw new FileServiceError('RUNTIME_INVALID_MANIFEST', '运行时装配清单哈希无效。');
      }
      if (entry.path.startsWith('/')) {
        throw new FileServiceError('RUNTIME_INVALID_MANIFEST', `运行时装配清单路径无效：${entry.path}`);
      }
      for (const part of entry.path.split('/')) {
        if (part.length === 0 || part === '.' || part === '..' || part.length > 180
          || /[\/\\\x00-\x1F\x7F]/.test(part)) {
          throw new FileServiceError('RUNTIME_INVALID_MANIFEST', `运行时装配清单路径无效：${entry.path}`);
        }
      }
      const lowered = entry.path.toLowerCase();
      if (seen.has(lowered)) {
        throw new FileServiceError('RUNTIME_INVALID_MANIFEST', `运行时装配清单路径重复：${entry.path}`);
      }
      seen.add(lowered);
    }
    return document.files.slice();
  }

  private static async unpack(source: RawFileSource, entry: RuntimeFileEntry, destination: string): Promise<void> {
    const bytes = await source.readBytes(`runtime/${entry.path}`);
    if (bytes.byteLength !== entry.size) {
      throw new FileServiceError('RUNTIME_UNPACK_FAILED', `运行时载荷大小不符：${entry.path}`, true);
    }
    await RuntimeInstaller.mkdirp(destination.substring(0, destination.lastIndexOf('/')));
    const tmp = `${destination}.tmp-${util.generateRandomUUID()}`;
    let file: fs.File | undefined = undefined;
    try {
      file = await fs.open(tmp, fs.OpenMode.CREATE | fs.OpenMode.WRITE_ONLY | fs.OpenMode.NOFOLLOW);
      const written = await fs.write(file.fd, bytes.slice(0).buffer);
      if (written !== entry.size) {
        throw new FileServiceError('RUNTIME_UNPACK_FAILED', `运行时装配写入未完成：${entry.path}`, true);
      }
      await fs.fsync(file.fd);
      await fs.close(file);
      file = undefined;
      // Verify before publishing; a mismatched temp never lands on the name
      // the interpreter reads.
      if (!(await RuntimeInstaller.verifiedFile(tmp, entry.sha256, entry.size))) {
        throw new FileServiceError('RUNTIME_UNPACK_FAILED', `运行时载荷校验失败：${entry.path}`, true);
      }
      await fs.rename(tmp, destination);
    } catch (error) {
      if (file) {
        try { await fs.close(file); } catch (closeError) { /* already closed */ }
      }
      try { if (await fs.access(tmp)) { await fs.unlink(tmp); } } catch (cleanupError) { /* best effort */ }
      if (error instanceof FileServiceError) { throw error; }
      throw new FileServiceError('RUNTIME_UNPACK_FAILED', `运行时装配写入失败：${entry.path}`, true);
    }
  }

  private static async verifiedFile(path: string, sha256: string, size: number): Promise<boolean> {
    try {
      const stat = await fs.lstat(path);
      if (!stat.isFile() || stat.size !== size) { return false; }
      return (await hash.hash(path, 'sha256')).toLowerCase() === sha256;
    } catch (error) { return false; }
  }

  private static async mkdirp(path: string): Promise<void> {
    if (await fs.access(path)) { return; }
    const parent = path.substring(0, path.lastIndexOf('/'));
    if (parent.length > 0 && parent !== path) { await RuntimeInstaller.mkdirp(parent); }
    try {
      await fs.mkdir(path);
    } catch (error) {
      if (!(await fs.access(path))) { throw error as Error; }  // Another writer may have won the race.
    }
  }

  private static async readMarker(path: string): Promise<string> {
    try {
      if (!(await fs.access(path))) { return ''; }
      const record = JSON.parse(await fs.readText(path)) as ActivationMarker;
      if (record.schemaVersion === 1 && typeof record.runtimeId === 'string'
        && /^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/.test(record.runtimeId)) {
        return record.runtimeId;
      }
      return '';
    } catch (error) {
      return '';  // A corrupt marker simply means "not activated".
    }
  }

  private static async writeMarker(path: string, runtimeId: string): Promise<void> {
    const record = new ActivationMarker();
    record.schemaVersion = 1;
    record.runtimeId = runtimeId;
    record.activatedAt = new Date().toISOString();
    const tmp = `${path}.tmp-${util.generateRandomUUID()}`;
    const file = await fs.open(tmp, fs.OpenMode.CREATE | fs.OpenMode.WRITE_ONLY
      | fs.OpenMode.TRUNC | fs.OpenMode.NOFOLLOW);
    try {
      const bytes = new util.TextEncoder().encodeInto(JSON.stringify(record));
      await fs.write(file.fd, bytes.buffer);
      await fs.fsync(file.fd);
    } finally {
      await fs.close(file);
    }
    await fs.rename(tmp, path);
  }

  private static async removeTree(path: string): Promise<void> {
    const stat = await fs.lstat(path);
    if (stat.isDirectory()) {
      for (const name of await fs.listFile(path)) {
        await RuntimeInstaller.removeTree(`${path}/${name}`);
      }
      await fs.rmdir(path);
    } else {
      await fs.unlink(path);
    }
  }
}
