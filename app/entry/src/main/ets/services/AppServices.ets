import { common } from '@kit.AbilityKit';
import { FileLibrary } from '../contracts/Files';
import { SandboxFileService } from './SandboxFileService';

/** Shared by the Ability and pages; opening twice does not create two queues. */
export class AppServices {
  private static instance: Promise<SandboxFileService> | undefined = undefined;

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
}
