import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import { acquireJob, cancelJob, getJobSnapshot, initializeCore, releaseJob, setEventCallback,
  shutdownCore, startAcquiredJob } from 'libgsas_core.so';
import { FileLibrary } from '../contracts/Files';
import { CoreBridgeService, CoreNativeModule, JobIdStore } from './CoreBridgeService';
import { HapRawFileSource } from './RuntimeInstaller';
import { SandboxFileService } from './SandboxFileService';

/** Shared by the Ability and pages; opening twice does not create two queues. */
export class AppServices {
  private static instance: Promise<SandboxFileService> | undefined = undefined;
  private static coreInstance: Promise<CoreBridgeService> | undefined = undefined;

  static files(context: common.UIAbilityContext): Promise<FileLibrary> {
    return AppServices.nativeFiles(context);
  }

  static nativeFiles(context: common.UIAbilityContext): Promise<SandboxFileService> {
    if (!AppServices.instance) {
      AppServices.instance = SandboxFileService.open(context.filesDir).catch((error: Object): never => {
        AppServices.instance = undefined;
        throw error as Error;
      });
    }
    return AppServices.instance;
  }

  /** The application-owned core facade; creating it does not initialize the
   * core — the page must await initialize() before injecting it as ready. */
  static core(context: common.UIAbilityContext, files: SandboxFileService): Promise<CoreBridgeService> {
    if (!AppServices.coreInstance) {
      AppServices.coreInstance = AppServices.buildCore(context, files).catch((error: Object): never => {
        AppServices.coreInstance = undefined;
        throw error as Error;
      });
    }
    return AppServices.coreInstance;
  }

  private static async buildCore(context: common.UIAbilityContext,
    files: SandboxFileService): Promise<CoreBridgeService> {
    const store = await PreferencesJobIdStore.open(context);
    return new CoreBridgeService({ native: new LibGsasCoreModule(), files,
      runtime: new HapRawFileSource(context.resourceManager), jobs: store });
  }
}

/** Bound methods of the process-lifetime N-API module (see napi_core.cpp). */
class LibGsasCoreModule implements CoreNativeModule {
  setEventCallback(callback: ((eventJson: string) => void) | null): void {
    setEventCallback(callback);
  }

  initializeCore(configJson: string): Promise<string> {
    return initializeCore(configJson);
  }

  acquireJob(jobId: string): void {
    acquireJob(jobId);
  }

  releaseJob(jobId: string): void {
    releaseJob(jobId);
  }

  startAcquiredJob(requestJson: string): string {
    return startAcquiredJob(requestJson);
  }

  cancelJob(jobId: string): string {
    return cancelJob(jobId);
  }

  getJobSnapshot(jobId: string): string {
    return getJobSnapshot(jobId);
  }

  shutdownCore(): Promise<void> {
    return shutdownCore();
  }
}

/** Persists the active/recent job id for snapshot restoration after reload. */
class PreferencesJobIdStore implements JobIdStore {
  private prefs: preferences.Preferences;

  constructor(prefs: preferences.Preferences) {
    this.prefs = prefs;
  }

  static async open(context: common.UIAbilityContext): Promise<PreferencesJobIdStore> {
    const prefs = await preferences.getPreferences(context, { name: 'core-bridge' });
    return new PreferencesJobIdStore(prefs);
  }

  async load(): Promise<string> {
    return String(await this.prefs.get('activeJobId', ''));
  }

  async save(jobId: string): Promise<void> {
    await this.prefs.put('activeJobId', jobId);
    await this.prefs.flush();
  }
}
