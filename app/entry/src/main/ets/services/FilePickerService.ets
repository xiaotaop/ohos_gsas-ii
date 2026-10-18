import { common } from '@kit.AbilityKit';
import { picker } from '@kit.CoreFileKit';
import { AppFile, FileRole, FileService } from '../contracts/Files';

/** Selection cancellation is a normal undefined/false result, not an error.
 * No URI is retained after the FileService has copied the selected bytes.
 */
export class FilePickerService {
  private context: common.UIAbilityContext;
  private files: FileService;

  constructor(context: common.UIAbilityContext, files: FileService) {
    this.context = context;
    this.files = files;
  }

  async selectAndImport(role: FileRole): Promise<AppFile | undefined> {
    const options = new picker.DocumentSelectOptions();
    options.maxSelectNumber = 1;
    options.fileSuffixFilters = role === FileRole.POWDER_DATA ? ['粉末数据|.xra,.cwn,.xye,.xy,.dat,.raw,.txt'] :
      role === FileRole.INSTRUMENT ? ['仪器参数|.prm,.instprm'] : ['相文件|.cif'];
    const uris = await new picker.DocumentViewPicker(this.context).select(options);
    if (uris.length === 0) { return undefined; }
    return this.files.importFile(uris[0], role);
  }

  async selectAndExport(fileId: string): Promise<boolean> {
    const file = await this.files.getFile(fileId);
    const options = new picker.DocumentSaveOptions();
    options.newFileNames = [file.displayName];
    const uris = await new picker.DocumentViewPicker(this.context).save(options);
    if (uris.length === 0) { return false; }
    await this.files.exportFile(fileId, uris[0]);
    return true;
  }
}
