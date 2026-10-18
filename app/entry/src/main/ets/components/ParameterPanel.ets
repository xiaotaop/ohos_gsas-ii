import { preferences } from '@kit.ArkData';
import { common } from '@kit.AbilityKit';
import { util } from '@kit.ArkTS';
import { cryptoFramework } from '@kit.CryptoArchitectureKit';
import { ParameterField, parameterFields, parameterTextLimit, visibleParameters, validateParameters, serializeParameters, restoreParameters } from '../model/ParameterDrafts';

@Extend(Button) function parameterButton() {
  .type(ButtonType.Normal).height(30).fontSize(13).fontColor('#202020').backgroundColor('#EEEEEE')
  .borderRadius(2).border({ width: 1, color: '#B8B8B8' }).padding({ left: 12, right: 12 })
}

@CustomDialog
struct ParameterEditor {
  controller: CustomDialogController;
  panel: string = '';
  scope: string = '';
  fields: ParameterField[] = [];
  save: (fields: ParameterField[]) => Promise<void> = async () => {};
  @State private form: ParameterField[] = [];
  @State private error: string = '';
  @State private saving: boolean = false;
  aboutToAppear(): void {
    this.form = restoreParameters(this.panel, this.scope, serializeParameters(this.panel, this.scope, this.fields));
  }
  private change(key: string, value: string, refine?: boolean): void {
    const next = parameterFields(this.panel);
    for (const item of next) {
      const previous = this.form.find((old: ParameterField): boolean => old.key === item.key);
      item.value = item.key === key ? value : previous?.value ?? '';
      item.refine = item.key === key && refine !== undefined ? refine : previous?.refine ?? false;
    }
    this.form = next; this.error = '';
  }
  private options(item: ParameterField): SelectOption[] {
    const options: SelectOption[] = [{ value: '未设置' }];
    return options.concat(item.choices.map((value: string): SelectOption => ({ value })));
  }
  private async commit(): Promise<void> {
    if (this.saving) { return; }
    this.error = validateParameters(this.panel, this.form);
    if (this.error) { return; }
    this.saving = true;
    try { await this.save(this.form); this.controller.close(); }
    catch { this.error = '草稿保存失败，当前编辑仍保留。请重试或取消。'; }
    finally { this.saving = false; }
  }
  build() {
    Column({ space: 10 }) {
      Text(`${this.panel} — Edit local draft`).fontSize(18).fontWeight(FontWeight.Bold).width('100%')
      Text('仅保存本地草稿；不修改输入文件，不提交精修。空白表示未设置。').fontSize(13).fontColor('#555555').width('100%')
      Scroll() {
        Column({ space: 10 }) {
          ForEach(visibleParameters(this.panel, this.form), (item: ParameterField) => {
            Column({ space: 4 }) {
              Text(item.label).fontSize(13).width('100%')
              Row({ space: 8 }) {
                if (item.multiline) {
                  TextArea({ text: item.value, placeholder: '记录实验说明、操作备注或待办事项…' })
                    .fontSize(14).height(240).layoutWeight(1).maxLength(parameterTextLimit(item))
                    .enabled(!this.saving).id(`parameter-${item.key}`).accessibilityText(item.label)
                    .onChange((value: string) => { this.change(item.key, value); })
                } else if (item.choices.length > 0) {
                  Select(this.options(item)).selected(item.choices.indexOf(item.value) + 1).value(item.value || '未设置')
                    .font({ size: 14 }).height(32).layoutWeight(1).enabled(!this.saving)
                    .onSelect((index: number) => { this.change(item.key, index === 0 ? '' : item.choices[index - 1]); })
                } else {
                  TextInput({ text: item.value, placeholder: '未设置' }).fontSize(14).height(32).layoutWeight(1)
                    .borderRadius(2).maxLength(parameterTextLimit(item)).enabled(!this.saving).id(`parameter-${item.key}`)
                    .onChange((value: string) => { this.change(item.key, value); })
                }
                if (item.refinable) {
                  Checkbox({ name: item.key }).select(item.refine).enabled(!this.saving)
                    .onChange((value: boolean) => { this.change(item.key, item.value, value); })
                  Text('Refine?').fontSize(13)
                }
              }.width('100%')
            }.width('100%')
          }, (item: ParameterField) => item.key)
        }.width('100%').padding({ right: 12 })
      }.layoutWeight(1).width('100%').align(Alignment.TopStart)
      if (this.error) { Text(this.error).fontSize(13).fontColor('#B3261E').width('100%').id('parameter-error') }
      Flex({ wrap: FlexWrap.Wrap, justifyContent: FlexAlign.End }) {
        Button('Clear form').parameterButton().enabled(!this.saving).margin({ right: 12, bottom: 8 })
          .onClick(() => { this.form = parameterFields(this.panel); this.error = '表单已清空，保存后生效；Cancel 可保留原草稿。'; })
        Button('Cancel').parameterButton().enabled(!this.saving).onClick(() => { this.controller.close(); })
          .margin({ right: 12, bottom: 8 })
        Button(this.saving ? 'Saving...' : 'Save local draft').parameterButton().enabled(!this.saving)
          .id('parameter-save').onClick(() => { this.commit(); })
          .margin({ bottom: 8 })
      }.width('100%')
    }.padding(20).width(620).constraintSize({ maxWidth: '90%' }).height('80%').backgroundColor('#F4F4F4')
      .border({ width: 1, color: '#A0A0A0' }).borderRadius(4)
  }
}

@Component
export struct ParameterPanel {
  @Prop @Watch('load') panel: string = 'Controls';
  @Prop @Watch('load') scope: string = '';
  @State private fields: ParameterField[] = [];
  @State private message: string = '';
  @State private loaded: boolean = false;
  private settings: preferences.Preferences | undefined = undefined;
  private editor: CustomDialogController | undefined = undefined;
  private generation: number = 0;
  private storageKey: string = '';
  aboutToAppear(): void { this.load(); }
  aboutToDisappear(): void { this.generation++; this.editor?.close(); }
  private async load(): Promise<void> {
    const generation = ++this.generation;
    const scope = this.scope; const panel = this.panel;
    this.editor?.close(); this.settings = undefined;
    this.loaded = false; this.fields = parameterFields(panel); this.message = '';
    try {
      const context = this.getUIContext().getHostContext() as common.UIAbilityContext;
      const settings = await preferences.getPreferences(context, { name: 'parameter-drafts-v1' });
      // Preferences keys are limited to 80 characters. Keep the exact scope in
      // the record for identity validation, and use a 70-character SHA-256 key.
      const md = cryptoFramework.createMd('SHA256');
      await md.update({ data: new util.TextEncoder().encodeInto(scope) });
      const digest = await md.digest();
      const key = 'draft-' + Array.from(digest.data).map((byte: number): string => byte.toString(16).padStart(2, '0')).join('');
      let json = String(await settings.get(key, ''));
      // Preserve any short-key draft saved by the earlier editor work in progress.
      if (!json && scope.length <= 80) { json = String(await settings.get(scope, '')); }
      const fields = restoreParameters(panel, scope, json);
      if (this.generation !== generation || this.scope !== scope || this.panel !== panel) { return; }
      this.settings = settings; this.storageKey = key; this.fields = fields; this.loaded = true;
      this.message = json ? '已恢复本地草稿。尚未用于精修。' :
        (panel === 'Notebook' || panel === 'Comments' ? '尚无本地记录。' : '尚无本地草稿；参数值未从输入文件解析。');
    } catch {
      if (this.generation === generation) { this.message = '草稿无法读取；原记录保留。请重试，不自动覆盖。'; }
    }
  }
  private edit(): void {
    if (!this.loaded) { return; }
    const generation = this.generation;
    const scope = this.scope; const panel = this.panel;
    const settings = this.settings;
    const key = this.storageKey;
    this.editor = new CustomDialogController({
      builder: ParameterEditor({ panel, scope, fields: this.fields, save: async (fields: ParameterField[]) => {
        if (!settings || this.generation !== generation) { throw new Error('Draft context changed.'); }
        const json = serializeParameters(panel, scope, fields);
        await settings.put(key, json); await settings.flush();
        if (this.generation !== generation) { return; }
        this.fields = restoreParameters(panel, scope, json); this.message = '本地草稿已保存；未修改文件或启动精修。';
      } }), autoCancel: false, customStyle: true, alignment: DialogAlignment.Center
    });
    this.editor.open();
  }
  private explain(title: string, message: string): void {
    this.getUIContext().showAlertDialog({ title, message, confirm: { value: 'OK', action: () => {} } });
  }
  private groups(): string[] {
    const result: string[] = [];
    for (const item of visibleParameters(this.panel, this.fields)) { if (!result.includes(item.group)) { result.push(item.group); } }
    return result;
  }
  build() {
    Column({ space: 10 }) {
      Text(this.panel === 'Limits' ? 'Data range to be used in fits' : this.panel === 'Controls' ? 'Refinement Controls' : this.panel)
        .fontSize(16).fontWeight(FontWeight.Bold).width('100%')
      Text(this.message).fontSize(13).fontColor('#555555').width('100%')
      Text(this.panel === 'Notebook' ? '应用本地笔记 · 更换输入不影响记录；未写入 GPX 工程' :
        this.panel === 'Comments' ? '此粉末文件的本地备注 · 不代表文件原有注释，不改写输入文件' :
        '本地参数草稿 · 未连接科学解析与精修服务').fontSize(13).fontColor('#805400').width('100%')
      Row({ space: 8 }) {
        Button('Edit local draft...').parameterButton().enabled(this.loaded).id('edit-parameter-draft').onClick(() => { this.edit(); })
        Button('Help').parameterButton().onClick(() => {
          this.explain(`${this.panel} — draft scope`, this.panel === 'Notebook' ?
            'Notebook 是当前应用的本地笔记，更换输入后仍保留。它不是 GPX 工程笔记；卸载前请自行留存需要的文字。取消编辑不保存。' :
            this.panel === 'Comments' ? '备注绑定已导入粉末文件的 fileId。切换到其他文件会显示其他备注，换回原文件可恢复；同名的新导入副本视为另一文件。原文件中的注释尚未解析。取消编辑不保存。' :
            '这些字段参考原版布局与选项。草稿按当前输入文件关联隔离并保存在本机，取消编辑不保存。当前不会读写 GPX、改写输入或提交计算。');
        })
      }.width('100%')
      if (!this.loaded) { Button('Retry').parameterButton().onClick(() => { this.load(); }) }
      if (this.panel === 'Limits') {
        Text('Original Tmin / Tmax: —（等待数据解析；当前单位与原始范围未知）').fontSize(13).width('100%')
      }
      ForEach(this.groups(), (group: string) => {
        Divider().margin({ top: 8 })
        Text(group).fontSize(14).fontWeight(FontWeight.Bold).width('100%')
        ForEach(visibleParameters(this.panel, this.fields).filter((item: ParameterField): boolean => item.group === group), (item: ParameterField) => {
          if (item.multiline) {
            Text(item.value || '暂无记录').fontSize(14).width('100%').copyOption(CopyOptions.LocalDevice)
              .id('local-notes-text').padding({ top: 8, bottom: 8 })
          } else {
          Row({ space: 10 }) {
            Text(item.label).fontSize(13).width('48%')
            Text(item.value || '—').fontSize(13).layoutWeight(1)
            if (item.refinable) { Checkbox().select(item.refine).enabled(false) }
          }.width('100%').constraintSize({ minHeight: 28 })
          }
        }, (item: ParameterField) => item.key)
      })
      if (this.panel === 'Controls') {
        Divider().margin({ top: 10 })
        Text('Sequential Settings').fontSize(14).fontWeight(FontWeight.Bold).width('100%')
        Text('Select datasets to switch to sequential refinement').fontSize(13).width('100%')
        Button('Select datasets').parameterButton().onClick(() => {
          this.explain('No Histograms', 'No histograms in use found for a sequential fit.\n输入文件虽已关联，尚未解析并关联到相；当前不能选择可用于顺序精修的数据集。');
        })
      }
      if (this.panel === 'Limits') {
        Text('Excluded regions:').fontSize(14).fontWeight(FontWeight.Bold).width('100%')
        Text('From                         To                         Delete?').fontSize(13).width('100%')
        Button('Add excluded region...').parameterButton().onClick(() => {
          this.explain('Excluded regions unavailable', '尚无解析后的原始数据范围和单位，不能校验排除区间；接入解析后开放原版范围编辑。');
        })
      }
      if (this.panel === 'Background') {
        Text('Debye scattering / Background peaks / Fixed background').fontSize(13).width('100%')
        Text('这些高级背景项尚未接入数据结构，不能编辑或拟合。').fontSize(13).fontColor('#555555').width('100%')
      }
      if (this.panel === 'Instrument Parameters' || this.panel === 'Sample Parameters') {
        Text(this.panel === 'Instrument Parameters' ? '模板由用户明确选择，不从 X 射线/中子用途推断 CW/TOF。当前覆盖单波长 CW 与 TOF 的常用字段。' : '当前样品页是 CW 几何草稿；TOF/能量色散及自由参数待解析接口支持。').fontSize(13).fontColor('#555555').width('100%')
      }
    }.alignItems(HorizontalAlign.Start).width('100%')
  }
}
