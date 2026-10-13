import { UIAbility, ConfigurationConstant } from '@kit.AbilityKit';
import { window } from '@kit.ArkUI';
import { hilog } from '@kit.PerformanceAnalysisKit';

export default class EntryAbility extends UIAbility {
  onCreate(): void {
    try {
      this.context.getApplicationContext().setColorMode(ConfigurationConstant.ColorMode.COLOR_MODE_LIGHT);
    } catch {
      hilog.warn(0, 'UiMock', 'Could not set demo color mode');
    }
  }

  onWindowStageCreate(stage: window.WindowStage): void {
    try {
      stage.loadContent('pages/Index', (error) => {
        if (error.code) { hilog.error(0, 'UiMock', 'Could not load demo page'); }
      });
    } catch {
      hilog.error(0, 'UiMock', 'Could not create demo window');
    }
  }
}
