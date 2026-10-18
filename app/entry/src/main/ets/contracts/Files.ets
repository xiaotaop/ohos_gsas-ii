// Member C implementation types for CORE_API v1.0. Cross-team role choices
// are documented in MEMBER_C_HANDOFF.md; no request/event fields are changed.
export enum FileRole {
  POWDER_DATA = 'powder-data',
  INSTRUMENT = 'instrument-parameters',
  PHASE = 'phase',
  PROJECT = 'project',
  RESULT = 'result',
  LOG = 'log'
}

export interface AppFile {
  fileId: string;
  displayName: string;
  role: FileRole;
  size: number;
  sha256: string;
}

export interface FileService {
  importFile(sourceUri: string, role: FileRole): Promise<AppFile>;
  getFile(fileId: string): Promise<AppFile>;
  deleteFile(fileId: string): Promise<void>;
  exportFile(fileId: string, destinationUri: string): Promise<void>;
}

export interface FileLibrary extends FileService {
  listFiles(): Promise<AppFile[]>;
}

export interface CoreConfig {
  schemaVersion: string;
  runtimeRoot: string;
  workspaceRoot: string;
  outputRoot: string;
  maxConcurrentJobs: number;
  logLevel: string;
}

export type ArtifactKind = 'project' | 'result' | 'log';

export class FileServiceError extends Error {
  code: string;
  retryable: boolean;

  constructor(code: string, message: string, retryable: boolean = false) {
    super(message);
    this.name = 'FileServiceError';
    this.code = code;
    this.retryable = retryable;
  }
}

export function describeFileError(error: Object): string {
  if (error instanceof FileServiceError) {
    return `${error.code}：${error.message}`;
  }
  // Never render platform error messages containing private paths or URIs.
  return 'INTERNAL_ERROR：文件操作未完成，请重试。';
}
