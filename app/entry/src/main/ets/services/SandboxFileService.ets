import { fileIo as fs, fileUri, hash } from '@kit.CoreFileKit';
import { util } from '@kit.ArkTS';
import { openExclusive } from 'libgsas_fileio.so';
import { BusinessError } from '@kit.BasicServicesKit';
import { AppFile, ArtifactKind, CoreConfig, FileRole, FileService, FileServiceError } from '../contracts/Files';

class FileRecord {
  version: number = 1;
  fileId: string = '';
  displayName: string = '';
  role: FileRole = FileRole.POWDER_DATA;
  size: number = 0;
  sha256: string = '';
  origin: string = 'import';
  jobId: string = '';
  deleting: boolean = false;
}

class JobLease {
  jobId: string = '';
  fileIds: string[] = [];
}

/** Application-owned singleton. Public metadata never contains a path/URI.
 * Mutations and reads share a queue: import/delete/export cannot race each
 * other. File IO and SHA-256 use the platform's asynchronous APIs.
 */
export class SandboxFileService implements FileService {
  private root: string;
  private records: Map<string, FileRecord> = new Map();
  private leases: Map<string, JobLease> = new Map();
  private interrupted: string[] = [];
  private queue: Promise<void> = Promise.resolve();

  private constructor(filesDir: string) {
    this.root = filesDir.replace(/\/$/, '');
  }

  static async open(filesDir: string): Promise<SandboxFileService> {
    if (!filesDir.startsWith('/') || filesDir.split('/').includes('..')) {
      throw new FileServiceError('INVALID_REQUEST', '应用文件目录无效。');
    }
    const service = new SandboxFileService(filesDir);
    await service.initialize();
    return service;
  }

  getCoreConfig(): CoreConfig {
    return {
      schemaVersion: '1.0', runtimeRoot: `${this.root}/runtime`,
      workspaceRoot: `${this.root}/jobs`, outputRoot: `${this.root}/outputs`,
      maxConcurrentJobs: 1, logLevel: 'info'
    };
  }

  listInterruptedJobs(): string[] {
    return this.interrupted.slice();
  }

  private serial<T>(operation: () => Promise<T>): Promise<T> {
    const result = this.queue.then(async (): Promise<T> => {
      try { return await operation(); }
      catch (error) {
        if (error instanceof FileServiceError) { throw error; }
        throw new FileServiceError('INTERNAL_ERROR', '文件操作未完成，请重试。', true);
      }
    });
    this.queue = result.then((): void => {}, (): void => {});
    return result;
  }

  private checkId(id: string, prefix: string): void {
    const pattern = prefix === 'file' ? /^file_[A-Za-z0-9_-]{8,64}$/ : /^job_[A-Za-z0-9_-]{8,64}$/;
    if (typeof id !== 'string' || !pattern.test(id)) {
      throw new FileServiceError('INVALID_REQUEST', '文件或任务标识无效。');
    }
  }

  private checkName(name: string): void {
    if (typeof name !== 'string' || name.length === 0 || name.length > 180 ||
      name === '.' || name === '..' || /[\/\\\x00-\x1F\x7F]/.test(name)) {
      throw new FileServiceError('INVALID_REQUEST', '文件名不受支持。');
    }
  }

  private checkRole(role: FileRole): void {
    if (![FileRole.POWDER_DATA, FileRole.INSTRUMENT, FileRole.PHASE,
      FileRole.PROJECT, FileRole.RESULT, FileRole.LOG].includes(role)) {
      throw new FileServiceError('INVALID_REQUEST', '文件角色无效。');
    }
  }

  private checkInput(name: string, role: FileRole): void {
    this.checkRole(role);
    const lower = name.toLowerCase();
    if ((role === FileRole.POWDER_DATA && !/\.(xra|cwn|xye|xy|dat|raw|txt)$/.test(lower)) ||
      (role === FileRole.INSTRUMENT && !/\.(prm|instprm)$/.test(lower)) ||
      (role === FileRole.PHASE && !lower.endsWith('.cif')) ||
      ![FileRole.POWDER_DATA, FileRole.INSTRUMENT, FileRole.PHASE].includes(role)) {
      throw new FileServiceError('UNSUPPORTED_FILE', '文件扩展名与所选用途不匹配。');
    }
  }

  private missing(error: Object): boolean {
    return (error as BusinessError).code === 13900002;
  }

  /** Check every application-controlled component, including directories.
   * lstat does not follow links; paths are always derived from validated IDs.
   */
  private async safePath(relative: string): Promise<string> {
    const parts = relative.split('/');
    let path = this.root;
    const rootStat = await fs.lstat(path);
    if (rootStat.isSymbolicLink() || !rootStat.isDirectory()) {
      throw new FileServiceError('INVALID_REQUEST', '应用目录不安全。');
    }
    for (const part of parts) {
      this.checkName(part);
      path += `/${part}`;
      const stat = await fs.lstat(path);
      if (stat.isSymbolicLink()) {
        throw new FileServiceError('INVALID_REQUEST', '不允许使用符号链接。');
      }
    }
    return path;
  }

  private async ensureDir(relative: string): Promise<void> {
    let prefix = '';
    for (const part of relative.split('/')) {
      this.checkName(part);
      prefix = prefix.length > 0 ? `${prefix}/${part}` : part;
      let exists = false;
      try {
        const path = await this.safePath(prefix);
        if (!(await fs.lstat(path)).isDirectory()) {
          throw new FileServiceError('INVALID_REQUEST', '应用目录被文件占用。');
        }
        exists = true;
      } catch (error) {
        if (!this.missing(error)) { throw error as Error; }
      }
      if (!exists) { await fs.mkdir(`${this.root}/${prefix}`); }
    }
  }

  private async initialize(): Promise<void> {
    for (const dir of ['imports', 'runtime', 'jobs', 'outputs', 'metadata', 'metadata/files', 'metadata/leases', 'staging']) {
      await this.ensureDir(dir);
    }
    const names = await fs.listFile(`${this.root}/metadata/files`);
    for (const name of names) {
      if (!name.endsWith('.json')) { continue; }
      const record = JSON.parse(await fs.readText(await this.safePath(`metadata/files/${name}`))) as FileRecord;
      this.validateRecord(record);
      if (name !== `${record.fileId}.json`) {
        throw new FileServiceError('INVALID_REQUEST', '文件目录索引损坏。');
      }
      if (record.deleting === true) { await this.eraseRecord(record); }
      else { this.records.set(record.fileId, record); }
    }
    // A persisted lease indicates an interrupted process. B consumes these
    // job IDs, emits PROCESS_INTERRUPTED and calls finishJob; never resume.
    for (const name of await fs.listFile(`${this.root}/metadata/leases`)) {
      if (!name.endsWith('.json')) { continue; }
      const lease = JSON.parse(await fs.readText(await this.safePath(`metadata/leases/${name}`))) as JobLease;
      this.checkId(lease.jobId, 'job');
      if (name !== `${lease.jobId}.json` || !Array.isArray(lease.fileIds)) {
        throw new FileServiceError('INVALID_REQUEST', '任务文件索引损坏。');
      }
      for (const id of lease.fileIds) { this.checkId(id, 'file'); }
      this.leases.set(lease.jobId, lease);
      this.interrupted.push(lease.jobId);
      await this.cleanWorkspace(lease.jobId);
    }
    // Only private staging data is disposable; outputs and logs are retained.
    for (const name of await fs.listFile(`${this.root}/staging`)) {
      this.checkId(name, 'file');
      await this.removeTree(`staging/${name}`);
    }
    // Interrupted imports can have complete bytes but no published metadata.
    // Only orphan input copies are removed, never unregistered core outputs.
    for (const name of await fs.listFile(`${this.root}/imports`)) {
      this.checkId(name, 'file');
      if (!this.records.has(name)) { await this.removeTree(`imports/${name}`); }
    }
  }

  private validateRecord(record: FileRecord): void {
    // Early version-1 catalogs predate the deletion recovery marker.
    // An absent marker means an ordinary record; other types are corrupt.
    if (record.deleting === undefined) { record.deleting = false; }
    this.checkId(record.fileId, 'file');
    this.checkName(record.displayName);
    this.checkRole(record.role);
    if (record.version !== 1 || typeof record.deleting !== 'boolean' || !Number.isSafeInteger(record.size) || record.size < 0 ||
      typeof record.sha256 !== 'string' || !/^[A-F0-9]{64}$/.test(record.sha256)) {
      throw new FileServiceError('INVALID_REQUEST', '文件索引损坏。');
    }
    if (record.origin === 'output') { this.checkId(record.jobId, 'job'); }
    else if (record.origin !== 'import' || record.jobId !== '') {
      throw new FileServiceError('INVALID_REQUEST', '文件索引来源无效。');
    }
  }

  private relative(record: FileRecord): string {
    return record.origin === 'import' ? `imports/${record.fileId}/${record.displayName}` :
      `outputs/${record.jobId}/${record.displayName}`;
  }

  private appFile(record: FileRecord): AppFile {
    return { fileId: record.fileId, displayName: record.displayName, role: record.role,
      size: record.size, sha256: record.sha256 };
  }

  private async verified(fileId: string): Promise<FileRecord> {
    this.checkId(fileId, 'file');
    const record = this.records.get(fileId);
    if (!record) { throw new FileServiceError('FILE_NOT_FOUND', '文件未登记或已删除。'); }
    this.validateRecord(record);
    let path = '';
    try { path = await this.safePath(this.relative(record)); }
    catch (error) {
      if (this.missing(error)) { throw new FileServiceError('FILE_NOT_FOUND', '文件已不存在。'); }
      throw error as Error;
    }
    const stat = await fs.lstat(path);
    if (!stat.isFile()) { throw new FileServiceError('INVALID_REQUEST', '登记内容不是普通文件。'); }
    if (stat.size !== record.size || (await hash.hash(path, 'sha256')).toUpperCase() !== record.sha256) {
      throw new FileServiceError('FILE_HASH_MISMATCH', '文件内容已变化，请重新导入。');
    }
    return record;
  }

  private async writeAtomic(relative: string, text: string): Promise<void> {
    const parent = relative.substring(0, relative.lastIndexOf('/'));
    await this.safePath(parent);
    const tmp = `${this.root}/${relative}.tmp-${util.generateRandomUUID()}`;
    try {
      const file = await fs.open(tmp, fs.OpenMode.CREATE | fs.OpenMode.WRITE_ONLY | fs.OpenMode.NOFOLLOW);
      try {
        const bytes = new util.TextEncoder().encodeInto(text);
        let written = 0;
        while (written < bytes.length) {
          const count = await fs.write(file.fd, bytes.slice(written).buffer);
          if (count === 0) { throw new FileServiceError('OUTPUT_WRITE_FAILED', '文件索引写入未完成。', true); }
          written += count;
        }
        await fs.fsync(file.fd);
      } finally { await fs.close(file); }
      await fs.rename(tmp, `${this.root}/${relative}`);
    }
    finally { if (await fs.access(tmp)) { await fs.unlink(tmp); } }
  }

  private async register(record: FileRecord): Promise<AppFile> {
    await this.writeAtomic(`metadata/files/${record.fileId}.json`, JSON.stringify(record));
    this.records.set(record.fileId, record);
    return this.appFile(record);
  }

  importFile(sourceUri: string, role: FileRole): Promise<AppFile> {
    return this.serial(async (): Promise<AppFile> => {
      if (!sourceUri.startsWith('file://')) {
        throw new FileServiceError('INVALID_REQUEST', '请选择系统文件选择器提供的文件。');
      }
      const name = new fileUri.FileUri(sourceUri).name;
      this.checkName(name);
      this.checkInput(name, role);
      const id = `file_${util.generateRandomUUID().replace(/-/g, '')}`;
      await this.ensureDir(`staging/${id}`);
      const destination = `${this.root}/staging/${id}/${name}`;
      try {
        const source = await fs.open(sourceUri, fs.OpenMode.READ_ONLY);
        try {
          if (!(await fs.stat(source.fd)).isFile()) {
            throw new FileServiceError('UNSUPPORTED_FILE', '只能导入普通文件。');
          }
          await fs.copyFile(source.fd, destination);
        } finally { await fs.close(source); }
        const record = new FileRecord();
        record.fileId = id; record.displayName = name; record.role = role;
        record.size = (await fs.lstat(destination)).size;
        record.sha256 = (await hash.hash(destination, 'sha256')).toUpperCase();
        // Publish complete bytes before publishing metadata. Directory has one
        // payload only, preserving the Python FileCatalog input invariant.
        await fs.rename(`${this.root}/staging/${id}`, `${this.root}/imports/${id}`);
        return await this.register(record);
      } catch (error) {
        if (await fs.access(`${this.root}/staging/${id}`)) { await this.removeTree(`staging/${id}`); }
        if (error instanceof FileServiceError) { throw error; }
        throw new FileServiceError('OUTPUT_WRITE_FAILED', '文件导入未完成，请重新选择。', true);
      }
    });
  }

  getFile(fileId: string): Promise<AppFile> {
    return this.serial(async (): Promise<AppFile> => this.appFile(await this.verified(fileId)));
  }

  listFiles(): Promise<AppFile[]> {
    return this.serial(async (): Promise<AppFile[]> => {
      const result: AppFile[] = [];
      for (const record of this.records.values()) { result.push(this.appFile(record)); }
      return result;
    });
  }

  /** Native/B-only API: do not hand this capability to a page. */
  resolveInputFile(fileId: string): Promise<string> {
    return this.serial(async (): Promise<string> => {
      const record = await this.verified(fileId);
      if (record.origin !== 'import') { throw new FileServiceError('INVALID_REQUEST', '该文件不是输入文件。'); }
      return this.safePath(this.relative(record));
    });
  }

  /** B registers only already-written outputs, without passing arbitrary paths. */
  registerOutput(jobId: string, fileId: string, displayName: string, kind: ArtifactKind): Promise<AppFile> {
    return this.serial(async (): Promise<AppFile> => {
      this.checkId(jobId, 'job'); this.checkId(fileId, 'file'); this.checkName(displayName);
      const existing = this.records.get(fileId);
      const role = kind === 'project' ? FileRole.PROJECT : kind === 'result' ? FileRole.RESULT : FileRole.LOG;
      if (!['project', 'result', 'log'].includes(kind)) { throw new FileServiceError('INVALID_REQUEST', '产物类型无效。'); }
      if (existing) {
        if (existing.origin !== 'output' || existing.jobId !== jobId || existing.displayName !== displayName || existing.role !== role) {
          throw new FileServiceError('INVALID_REQUEST', '产物标识已被其他文件使用。');
        }
        return this.appFile(await this.verified(fileId));
      }
      // One physical output has one owner. Two IDs for the same path would
      // let deleting either registration invalidate the other.
      for (const registered of this.records.values()) {
        if (registered.origin === 'output' && registered.jobId === jobId && registered.displayName === displayName) {
          throw new FileServiceError('INVALID_REQUEST', '该产物文件已经登记。');
        }
      }
      const record = new FileRecord();
      record.fileId = fileId; record.displayName = displayName; record.role = role;
      record.origin = 'output'; record.jobId = jobId;
      const path = await this.safePath(this.relative(record));
      const stat = await fs.lstat(path);
      if (!stat.isFile()) { throw new FileServiceError('INVALID_REQUEST', '产物不是普通文件。'); }
      record.size = stat.size; record.sha256 = (await hash.hash(path, 'sha256')).toUpperCase();
      return this.register(record);
    });
  }

  beginJob(jobId: string, fileIds: string[]): Promise<void> {
    return this.serial(async (): Promise<void> => {
      this.checkId(jobId, 'job');
      if (this.leases.has(jobId)) { throw new FileServiceError('JOB_ALREADY_EXISTS', '任务文件已锁定。'); }
      for (const id of fileIds) {
        const record = await this.verified(id);
        if (record.origin !== 'import') { throw new FileServiceError('INVALID_REQUEST', '任务只能使用导入文件。'); }
      }
      for (const dir of ['input', 'work', 'logs']) { await this.ensureDir(`jobs/${jobId}/${dir}`); }
      await this.ensureDir(`outputs/${jobId}`);
      const lease = new JobLease(); lease.jobId = jobId; lease.fileIds = fileIds.slice();
      await this.writeAtomic(`metadata/leases/${jobId}.json`, JSON.stringify(lease));
      this.leases.set(jobId, lease);
    });
  }

  finishJob(jobId: string): Promise<void> {
    return this.serial(async (): Promise<void> => {
      this.checkId(jobId, 'job');
      await this.cleanWorkspace(jobId);
      const path = `${this.root}/metadata/leases/${jobId}.json`;
      if (await fs.access(path)) { await this.safePath(`metadata/leases/${jobId}.json`); await fs.unlink(path); }
      this.leases.delete(jobId);
      this.interrupted = this.interrupted.filter((id: string): boolean => id !== jobId);
    });
  }

  deleteFile(fileId: string): Promise<void> {
    return this.serial(async (): Promise<void> => {
      this.checkId(fileId, 'file');
      const record = this.records.get(fileId);
      if (!record) { throw new FileServiceError('FILE_NOT_FOUND', '文件未登记或已删除。'); }
      for (const lease of this.leases.values()) {
        if (lease.fileIds.includes(fileId)) { throw new FileServiceError('BUSY', '文件正在被任务使用，结束后再删除。', true); }
      }
      // Persist intent first. A restart can finish deletion after interruption.
      // Do not require the data still to exist or have its original hash.
      record.deleting = true;
      try { await this.writeAtomic(`metadata/files/${fileId}.json`, JSON.stringify(record)); }
      catch (error) { record.deleting = false; throw error as Error; }
      this.records.delete(fileId);
      await this.eraseRecord(record);
    });
  }

  exportFile(fileId: string, destinationUri: string): Promise<void> {
    return this.serial(async (): Promise<void> => {
      const record = await this.verified(fileId);
      if (!destinationUri.startsWith('file://')) { throw new FileServiceError('INVALID_REQUEST', '请选择系统保存位置。'); }
      let target: fs.File | undefined = undefined;
      let descriptor: number = -1;
      try {
        if (destinationUri.startsWith('file://docs/')) {
          // The system save picker reserves an authorized empty document.
          // Opening through its provider preserves the URI permission boundary.
          target = await fs.open(destinationUri, fs.OpenMode.WRITE_ONLY | fs.OpenMode.NOFOLLOW);
          descriptor = target.fd;
          if ((await fs.stat(descriptor)).size !== 0) {
            throw new FileServiceError('OUTPUT_WRITE_FAILED', '目标文件已有内容，请使用新文件名。', true);
          }
        } else {
          // Sandbox targets have no provider reservation. O_EXCL protects
          // existing empty files and concurrent creators atomically.
          descriptor = openExclusive(destinationUri);
        }
        await fs.copyFile(await this.safePath(this.relative(record)), descriptor);
        await fs.fsync(descriptor);
      } catch (error) {
        if (error instanceof FileServiceError) { throw error; }
        throw new FileServiceError('OUTPUT_WRITE_FAILED', '文件导出未完成，请选择新的本地保存位置。', true);
      } finally {
        if (target) { await fs.close(target); }
        else if (descriptor >= 0) { await fs.close(descriptor); }
      }
    });
  }

  private async removeTree(relative: string): Promise<void> {
    const path = await this.safePath(relative);
    const stat = await fs.lstat(path);
    if (stat.isDirectory()) {
      for (const name of await fs.listFile(path)) { await this.removeTree(`${relative}/${name}`); }
      await fs.rmdir(path);
    } else { await fs.unlink(path); }
  }

  private async eraseRecord(record: FileRecord): Promise<void> {
    try { await fs.unlink(await this.safePath(this.relative(record))); }
    catch (error) { if (!this.missing(error)) { throw error as Error; } }
    if (record.origin === 'import') {
      try { await this.removeTree(`imports/${record.fileId}`); }
      catch (error) { if (!this.missing(error)) { throw error as Error; } }
    }
    await fs.unlink(await this.safePath(`metadata/files/${record.fileId}.json`));
  }

  private async cleanWorkspace(jobId: string): Promise<void> {
    // Invoked only after a terminal task or a process restart. Preserve logs
    // and outputs for all outcomes, including interrupted/failed/cancelled.
    for (const child of ['input', 'work']) {
      try { await this.removeTree(`jobs/${jobId}/${child}`); }
      catch (error) { if (!this.missing(error)) { throw error as Error; } }
    }
  }
}
