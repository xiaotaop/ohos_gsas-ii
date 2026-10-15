import { UIAbility, ConfigurationConstant } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { AppServices } from '../services/AppServices';

export default class EntryAbility extends UIAbility {
  onCreate(): void {
    AppServices.nativeFiles(this.context).catch((): void => {
      hilog.error(0, 'GSASPC', 'File service initialization failed; page can retry');
    });
    try {
      this.context.getApplicationContext().setColorMode(ConfigurationConstant.ColorMode.COLOR_MODE_LIGHT);
    } catch {
      hilog.warn(0, 'GSASPC', 'Could not set color mode');
    }
  }

  onWindowStageCreate(stage: window.WindowStage): void {
    try {
      stage.loadContent('pages/Index', (error) => {
        if (error.code) { hilog.error(0, 'GSASPC', 'Could not load application page'); }
      });
    } catch {
      hilog.error(0, 'GSASPC', 'Could not create application window');
    }
  }
}
