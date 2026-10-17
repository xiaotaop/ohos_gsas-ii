import { common } from '@kit.AbilityKit';
import { fileIo as fs, fileUri, hash } from '@kit.CoreFileKit';
import { util } from '@kit.ArkTS';
import { BusinessError } from '@kit.BasicServicesKit';
import { AppFile, FileRole, FileServiceError } from '../contracts/Files';
import { SandboxFileService } from '../services/SandboxFileService';

export class FileCheckReport {
  passed: number = 0;
  failed: number = 0;
  lines: string[] = [];
  skipped: number = 0;
}

class Fixture {
  name: string;
  role: FileRole;
  sha256: string;
  constructor(name: string, role: FileRole, sha256: string) {
    this.name = name; this.role = role; this.sha256 = sha256;
  }
}

const FIXTURES: Fixture[] = [
  new Fixture('PBSO4.XRA', FileRole.POWDER_DATA, 'CA2DA02FC7E17D2FC912DE22A979F8101BA6140F2E8104F9D3AA64F030CA58BB'),
  new Fixture('INST_XRY.PRM', FileRole.INSTRUMENT, 'E59413059BC3B12A51F1C6EEBC5D581470320D05A31F11A41DBB32E16D1D16B9'),
  new Fixture('PBSO4.CWN', FileRole.POWDER_DATA, '59462BA6D7C72C9800B0B6BF41903F9933ED5AC5ADAB101D27022D5D25CF18BA'),
  new Fixture('inst_d1a.prm', FileRole.INSTRUMENT, 'A1031174A9B509F889377752F5C095A1DAD49A25FB0A72C057F184F7B321FCEA'),
  new Fixture('PbSO4-Wyckoff.cif', FileRole.PHASE, '22CBA0B64FB6BF89178FE828FDF63570BFFEBED1485313E78C50C2918A47A970')
];

function assertCheck(condition: boolean, message: string): void {
  if (!condition) { throw new Error(message); }
}

async function expectCode(action: () => Promise<void>, code: string): Promise<void> {
  try { await action(); }
  catch (error) {
    if (error instanceof FileServiceError && error.code === code) { return; }
    const actual = error instanceof FileServiceError ? error.code : `${(error as BusinessError).code}`;
    throw new Error(`Expected ${code}, got ${actual}`);
  }
  throw new Error(`Missing ${code}`);
}

async function writeBytes(path: string, bytes: Uint8Array): Promise<void> {
  const file = await fs.open(path, fs.OpenMode.WRITE_ONLY | fs.OpenMode.CREATE | fs.OpenMode.TRUNC);
  try {
    let written = 0;
    while (written < bytes.length) {
      const count = await fs.write(file.fd, bytes.slice(written).buffer);
      assertCheck(count > 0, 'short write'); written += count;
    }
  } finally { await fs.close(file); }
}

// Platform checks use an isolated cache directory, never the user catalog.
export async function runFileServiceChecks(context: common.UIAbilityContext): Promise<FileCheckReport> {
  const report = new FileCheckReport();
  const base = `${context.cacheDir}/file-check-${util.generateRandomUUID()}`;
  await fs.mkdir(base); await fs.mkdir(`${base}/sources`); await fs.mkdir(`${base}/files`);
  const root = `${base}/files`;
  let service = await SandboxFileService.open(root);
  const imported: AppFile[] = [];
  const check = async (name: string, action: () => Promise<void>): Promise<void> => {
    const skippedBefore = report.skipped;
    try {
      await action();
      if (report.skipped === skippedBefore) { report.passed++; report.lines.push(`PASS ${name}`); }
    }
    catch (error) {
      report.failed++;
      const code = (error as BusinessError).code;
      report.lines.push(`FAIL ${name}: ${code ? code : (error as Error).message}`);
    }
  };
  try {
    for (const fixture of FIXTURES) {
      await check(`导入及 SHA-256 ${fixture.name}`, async (): Promise<void> => {
        const bytes = await context.resourceManager.getRawFileContent(`fixtures/${fixture.name}`);
        const source = `${base}/sources/${fixture.name}`; await writeBytes(source, bytes);
        const file = await service.importFile(fileUri.getUriFromPath(source), fixture.role);
        assertCheck(file.sha256 === fixture.sha256 && file.size === bytes.length, 'fixture integrity');
        assertCheck((await fs.listFile(`${root}/imports/${file.fileId}`)).length === 1, 'Python directory layout');
        imported.push(file);
      });
    }
    if (imported.length !== 5) { return report; }
    const first = imported[0];
    await check('重建服务后恢复 fileId 和元数据', async (): Promise<void> => {
      service = await SandboxFileService.open(root);
      assertCheck((await service.listFiles()).length === 5, 'restore count');
      assertCheck((await service.getFile(first.fileId)).sha256 === first.sha256, 'restore hash');
      assertCheck(service.getCoreConfig().workspaceRoot === `${root}/jobs`, 'core config');
    });
    await check('未知 fileId 与路径逃逸被拒绝', async (): Promise<void> => {
      await expectCode(async (): Promise<void> => { await service.getFile('file_missing_00000001'); }, 'FILE_NOT_FOUND');
      await expectCode(async (): Promise<void> => { await service.getFile('file_../../outside'); }, 'INVALID_REQUEST');
      await expectCode(async (): Promise<void> => { await service.registerOutput('job_check_00001', 'file_check_00001', '../outside', 'log'); }, 'INVALID_REQUEST');
    });
    await check('格式不匹配不产生文件登记', async (): Promise<void> => {
      await expectCode(async (): Promise<void> => { await service.importFile(fileUri.getUriFromPath(`${base}/sources/PBSO4.XRA`), FileRole.PHASE); }, 'UNSUPPORTED_FILE');
      assertCheck((await service.listFiles()).length === 5, 'unexpected registry entry');
    });
    await check('并发导入使用独立 ID 和串行持久化', async (): Promise<void> => {
      const uri = fileUri.getUriFromPath(`${base}/sources/PBSO4.XRA`);
      const copies = await Promise.all([service.importFile(uri, FileRole.POWDER_DATA), service.importFile(uri, FileRole.POWDER_DATA)]);
      assertCheck(copies[0].fileId !== copies[1].fileId, 'duplicate ID');
      await service.deleteFile(copies[0].fileId); await service.deleteFile(copies[1].fileId);
    });
    await check('任务引用保护与进程中断租约恢复', async (): Promise<void> => {
      await service.beginJob('job_check_00001', [first.fileId]);
      await expectCode(async (): Promise<void> => { await service.deleteFile(first.fileId); }, 'BUSY');
      service = await SandboxFileService.open(root);
      assertCheck(service.listInterruptedJobs().includes('job_check_00001'), 'lost interrupted lease');
      await expectCode(async (): Promise<void> => { await service.deleteFile(first.fileId); }, 'BUSY');
      await service.finishJob('job_check_00001');
      assertCheck(service.listInterruptedJobs().length === 0, 'lease not released');
      assertCheck(!(await fs.access(`${root}/jobs/job_check_00001/work`)), 'workspace not cleaned');
      assertCheck(await fs.access(`${root}/jobs/job_check_00001/logs`), 'logs removed');
    });
    await check('导出真实字节、拒绝覆盖已有文件', async (): Promise<void> => {
      const path = `${base}/exported.xra`; const uri = fileUri.getUriFromPath(path);
      await service.exportFile(first.fileId, uri);
      assertCheck((await hash.hash(path, 'sha256')) === first.sha256, 'export hash');
      await expectCode(async (): Promise<void> => { await service.exportFile(first.fileId, uri); }, 'OUTPUT_WRITE_FAILED');
      assertCheck((await hash.hash(path, 'sha256')) === first.sha256, 'overwritten destination');
    });
    await check('已有空文件通过 URI 导出时也不覆盖', async (): Promise<void> => {
      const path = `${base}/existing-empty.xra`;
      await writeBytes(path, new Uint8Array(0));
      await expectCode(async (): Promise<void> => {
        await service.exportFile(first.fileId, fileUri.getUriFromPath(path));
      }, 'OUTPUT_WRITE_FAILED');
      assertCheck((await fs.stat(path)).size === 0, 'empty destination overwritten');
    });
    await check('真实 JSON 产物登记、查询和导出', async (): Promise<void> => {
      const bytes = new util.TextEncoder().encodeInto('{"fileServiceCheck":true}\n');
      await writeBytes(`${root}/outputs/job_check_00001/check.json`, bytes);
      const file = await service.registerOutput('job_check_00001', 'file_out_check_00001_json', 'check.json', 'result');
      assertCheck(file.role === FileRole.RESULT && file.size === bytes.length, 'output metadata');
      const again = await service.registerOutput('job_check_00001', file.fileId, 'check.json', 'result');
      assertCheck(again.sha256 === file.sha256, 'registration not idempotent');
      await service.exportFile(file.fileId, fileUri.getUriFromPath(`${base}/check.json`));
      assertCheck((await hash.hash(`${base}/check.json`, 'sha256')) === file.sha256, 'output export');
    });
    await check('同一产物路径拒绝使用不同 fileId 重复登记', async (): Promise<void> => {
      await expectCode(async (): Promise<void> => {
        await service.registerOutput('job_check_00001', 'file_out_alias_check_01', 'check.json', 'result');
      }, 'INVALID_REQUEST');
      const original = await service.getFile('file_out_check_00001_json');
      assertCheck(original.role === FileRole.RESULT, 'original output invalidated');
    });
    await check('符号链接输入文件被拒绝', async (): Promise<void> => {
      const path = await service.resolveInputFile(imported[1].fileId); const backup = `${path}.backup`;
      await fs.rename(path, backup);
      try { await fs.symlink(`${base}/sources/INST_XRY.PRM`, path); }
      catch (error) {
        await fs.rename(backup, path);
        if ((error as BusinessError).code === 13900012) {
          report.skipped++;
          report.lines.push('SKIP 符号链接创建：API 11 起禁止第三方应用创建；需宿主真实文件系统补验');
          return;
        }
        throw error as Error;
      }
      try { await expectCode(async (): Promise<void> => { await service.getFile(imported[1].fileId); }, 'INVALID_REQUEST'); }
      finally { await fs.unlink(path); await fs.rename(backup, path); }
    });
    await check('内容变化被检出', async (): Promise<void> => {
      const path = await service.resolveInputFile(imported[2].fileId);
      await writeBytes(path, new util.TextEncoder().encodeInto('changed'));
      await expectCode(async (): Promise<void> => { await service.getFile(imported[2].fileId); }, 'FILE_HASH_MISMATCH');
    });
    await check('删除中断标记在重建时完成清理', async (): Promise<void> => {
      const copy = await service.importFile(fileUri.getUriFromPath(`${base}/sources/PBSO4.XRA`), FileRole.POWDER_DATA);
      const path = `${root}/metadata/files/${copy.fileId}.json`;
      const text = await fs.readText(path);
      assertCheck(text.includes('"deleting":false'), 'missing deletion marker');
      await writeBytes(path, new util.TextEncoder().encodeInto(text.replace('"deleting":false', '"deleting":true')));
      service = await SandboxFileService.open(root);
      await expectCode(async (): Promise<void> => { await service.getFile(copy.fileId); }, 'FILE_NOT_FOUND');
      assertCheck(!(await fs.access(`${root}/imports/${copy.fileId}`)), 'deletion left input bytes');
    });
    await check('未登记的导入与暂存副本在重建时清理', async (): Promise<void> => {
      await fs.mkdir(`${root}/staging/file_orphan_check_01`);
      await fs.mkdir(`${root}/imports/file_orphan_check_02`);
      await writeBytes(`${root}/imports/file_orphan_check_02/orphan.txt`, new util.TextEncoder().encodeInto('orphan'));
      service = await SandboxFileService.open(root);
      assertCheck(!(await fs.access(`${root}/staging/file_orphan_check_01`)), 'staging not cleaned');
      assertCheck(!(await fs.access(`${root}/imports/file_orphan_check_02`)), 'orphan input not cleaned');
      assertCheck(await fs.access(`${root}/outputs/job_check_00001/check.json`), 'outputs removed');
    });
    await check('删除后查询与重建均保持删除状态', async (): Promise<void> => {
      await service.deleteFile(first.fileId);
      await expectCode(async (): Promise<void> => { await service.getFile(first.fileId); }, 'FILE_NOT_FOUND');
      service = await SandboxFileService.open(root);
      await expectCode(async (): Promise<void> => { await service.getFile(first.fileId); }, 'FILE_NOT_FOUND');
    });
  } finally { await fs.rmdir(base); }
  return report;
}
