import { AppFile, FileRole, FileService, FileServiceError } from '../contracts/Files';

export enum InputSlot {
  XRAY_DATA = 'xray-data', XRAY_INSTRUMENT = 'xray-instrument',
  NEUTRON_DATA = 'neutron-data', NEUTRON_INSTRUMENT = 'neutron-instrument', PHASE = 'phase'
}

export interface InputSlotInfo { id: InputSlot; label: string; role: FileRole; }
export const INPUT_SLOTS: InputSlotInfo[] = [
  { id: InputSlot.XRAY_DATA, label: 'X 射线粉末数据', role: FileRole.POWDER_DATA },
  { id: InputSlot.XRAY_INSTRUMENT, label: 'X 射线仪器参数', role: FileRole.INSTRUMENT },
  { id: InputSlot.NEUTRON_DATA, label: '中子粉末数据', role: FileRole.POWDER_DATA },
  { id: InputSlot.NEUTRON_INSTRUMENT, label: '中子仪器参数', role: FileRole.INSTRUMENT },
  { id: InputSlot.PHASE, label: 'CIF 相文件', role: FileRole.PHASE }
];
export interface InputBinding { slot: InputSlot; fileId: string; }
interface SavedBindings { version: number; bindings: InputBinding[]; }
// The frozen request's inputs only; no new request fields or default cycle count.
export interface HistogramInput {
  id: string; role: string; dataFileId: string; instrumentFileId: string; formatHint: string;
}
export interface PhaseInput { id: string; name: string; fileId: string; }
export interface RefinementInputs { histograms: HistogramInput[]; phase: PhaseInput; }

// UI associations are independent of C's persistent file library. Reselecting
// never deletes imported files; shared powder-data roles never imply xray/neutron.
export class InputSelection {
  private bindings: InputBinding[] = [];

  entries(): InputBinding[] {
    return this.bindings.map((item: InputBinding): InputBinding => ({ slot: item.slot, fileId: item.fileId }));
  }

  select(slot: InputSlot, file: AppFile): void {
    const info = INPUT_SLOTS.find((item: InputSlotInfo): boolean => item.id === slot);
    if (!info || info.role !== file.role || !/^file_[A-Za-z0-9_-]{8,64}$/.test(file.fileId)) {
      throw new FileServiceError('INVALID_REQUEST', '文件角色与此输入位置不符。');
    }
    this.clear(slot);
    this.bindings.push({ slot, fileId: file.fileId });
  }

  clear(slot: InputSlot): void {
    this.bindings = this.bindings.filter((item: InputBinding): boolean => item.slot !== slot);
  }

  serialize(): string {
    const saved: SavedBindings = { version: 1, bindings: this.entries() };
    return JSON.stringify(saved);
  }

  restore(json: string, files: AppFile[]): number {
    let saved: SavedBindings;
    try { saved = JSON.parse(json) as SavedBindings; }
    catch { throw new FileServiceError('INVALID_REQUEST', '输入关联记录无法读取，请重新选择。'); }
    if (!saved || saved.version !== 1 || !Array.isArray(saved.bindings) || saved.bindings.length > 5) {
      throw new FileServiceError('INVALID_REQUEST', '输入关联记录无效，请重新选择。');
    }
    const restored = new InputSelection();
    let removed = 0;
    const seen: InputSlot[] = [];
    for (const binding of saved.bindings) {
      if (!binding || typeof binding.slot !== 'string' || typeof binding.fileId !== 'string' ||
        !INPUT_SLOTS.some((item: InputSlotInfo): boolean => item.id === binding.slot) ||
        seen.includes(binding.slot) || !/^file_[A-Za-z0-9_-]{8,64}$/.test(binding.fileId)) {
        throw new FileServiceError('INVALID_REQUEST', '输入关联记录无效，请重新选择。');
      }
      seen.push(binding.slot);
      const file = files.find((item: AppFile): boolean => item.fileId === binding.fileId);
      const info = INPUT_SLOTS.find((item: InputSlotInfo): boolean => item.id === binding.slot);
      if (!file || !info || file.role !== info.role) { removed++; continue; }
      restored.select(binding.slot, file);
    }
    this.bindings = restored.entries();
    return removed;
  }

  async verify(files: FileService): Promise<RefinementInputs> {
    // Capture associations before awaiting; later edits cannot mix two input sets.
    const bindings = this.entries();
    for (const info of INPUT_SLOTS) {
      const binding = bindings.find((item: InputBinding): boolean => item.slot === info.id);
      if (!binding) { throw new FileServiceError('INVALID_REQUEST', `请选择${info.label}。`); }
      const file = await files.getFile(binding.fileId); // verifies existence and hash, not just list metadata
      if (file.fileId !== binding.fileId || file.role !== info.role) {
        throw new FileServiceError('INVALID_REQUEST', `${info.label}的文件角色不符，请重新选择。`);
      }
    }
    return {
      histograms: [
        { id: 'xray', role: 'xray', dataFileId: this.boundId(bindings, InputSlot.XRAY_DATA),
          instrumentFileId: this.boundId(bindings, InputSlot.XRAY_INSTRUMENT), formatHint: 'GSAS powder' },
        { id: 'neutron', role: 'neutron', dataFileId: this.boundId(bindings, InputSlot.NEUTRON_DATA),
          instrumentFileId: this.boundId(bindings, InputSlot.NEUTRON_INSTRUMENT), formatHint: 'GSAS powder' }
      ],
      phase: { id: 'phase', name: 'Selected phase', fileId: this.boundId(bindings, InputSlot.PHASE) }
    };
  }

  private boundId(bindings: InputBinding[], slot: InputSlot): string {
    const binding = bindings.find((item: InputBinding): boolean => item.slot === slot);
    if (!binding) { throw new FileServiceError('INVALID_REQUEST', '输入关联不完整。'); }
    return binding.fileId;
  }
}
