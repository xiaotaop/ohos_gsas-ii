// UI-only drafts. These records are never CoreService requests or parsed file values.
// Labels/choices: pinned GSAS-II dataGUI.UpdateControls and pwdGUI parameter panels.
export interface ParameterField {
  key: string; label: string; group: string; value: string; choices: string[];
  numeric: boolean; min: number; max: number; refinable: boolean; refine: boolean;
}
export interface SavedParameterField { key: string; value: string; refine: boolean; }
export interface ParameterRecord { version: number; panel?: string; scope: string; fields: SavedParameterField[]; }

function field(key: string, label: string, group: string, choices: string[] = [],
  numeric: boolean = true, min: number = -Infinity, max: number = Infinity, refinable: boolean = false): ParameterField {
  return { key, label, group, value: '', choices, numeric, min, max, refinable, refine: false };
}
export function parameterValue(fields: ParameterField[], key: string): string {
  return fields.find((item: ParameterField): boolean => item.key === key)?.value ?? '';
}
export function parameterFields(panel: string): ParameterField[] {
  if (panel === 'Controls') {
    return [
      field('method', 'Refinement type', 'Refinement Controls', ['analytic Jacobian', 'numeric', 'analytic Hessian', 'Hessian SVD'], false),
      field('delta', 'Min delta-M/M', 'Refinement Controls', [], true, 1e-9, 1),
      field('cycles', 'Max cycles', 'Refinement Controls', ['0', '1', '2', '3', '5', '10', '15', '20']),
      field('lambda', 'Initial lambda = 10**', 'Refinement Controls', ['-3', '-2', '-1', '0', '1', '2', '3', '4']),
      field('svd', 'SVD zero tolerance', 'Refinement Controls', [], true, 1e-9, .01),
      field('shift', 'Initial shift factor', 'Refinement Controls', [], true, 1e-5, 100),
      field('author', 'CIF Author (last, first)', 'Global Settings', [], false)
    ];
  }
  if (panel === 'Limits') {
    return [field('lower', 'New Tmin', 'Data range to be used in fits'),
      field('upper', 'New Tmax', 'Data range to be used in fits')];
  }
  if (panel === 'Background') {
    const result: ParameterField[] = [
      field('function', 'Background function', 'Background', ['chebyschev', 'chebyschev-1', 'cosine', 'Q^2 power series', 'Q^-2 power series', 'lin interpolate', 'inv interpolate', 'log interpolate'], false, -Infinity, Infinity, true),
      field('count', 'Number of coeff.', 'Background', Array.from({ length: 36 }, (_v: Object, i: number): string => String(i + 1)))
    ];
    for (let i = 0; i < 36; i++) { result.push(field(`b${i}`, `Coefficient ${i}`, 'Background coefficients')); }
    return result;
  }
  if (panel === 'Instrument Parameters') {
    const result: ParameterField[] = [field('type', 'Histogram Type (manual template)', 'Instrument settings', ['PXC', 'PNC', 'PNT'], false)];
    for (const name of ['Lam', 'Zero', 'Polariz.', 'U', 'V', 'W', 'X', 'Y', 'Z', 'SH/L', 'difC', 'difA', 'difB', 'alpha', 'beta-0', 'beta-1', 'beta-q', 'sig-0', 'sig-1', 'sig-2', 'sig-q']) {
      result.push(field(name, name, 'Name / Value / Refine?', [], true, name === 'SH/L' ? .002 : -Infinity, Infinity, true));
    }
    return result;
  }
  if (panel === 'Sample Parameters') {
    const result: ParameterField[] = [field('name', 'Instrument Name', 'Sample Parameters', [], false),
      field('geometry', 'Diffractometer type', 'Sample Parameters', ['Debye-Scherrer', 'Bragg-Brentano'], false)];
    const keys: string[] = ['Scale', 'Gonio. radius', 'DisplaceX', 'DisplaceY', 'Absorption', 'Shift', 'Transparency', 'SurfRoughA', 'SurfRoughB', 'Omega', 'Chi', 'Phi', 'Azimuth', 'Time', 'Temperature', 'Pressure'];
    const labels: string[] = ['Histogram scale factor', 'Goniometer radius (mm)', 'Sample X displ. perp. to beam (µm)', 'Sample Y displ. || to beam (µm)', 'Sample absorption (µ·r)', 'Sample displacement (µm)', 'Sample transparency (1/µeff, cm)', 'Surface roughness A', 'Surface roughness B', 'Goniometer omega', 'Goniometer chi', 'Goniometer phi', 'Detector azimuth', 'Clock time (s)', 'Sample temperature (K)', 'Sample pressure (MPa)'];
    keys.forEach((key: string, i: number) => { result.push(field(key, labels[i], 'Sample parameters', [], true, -Infinity, Infinity, i === 0 || (i >= 2 && i <= 8))); });
    return result;
  }
  return [];
}
export function visibleParameters(panel: string, fields: ParameterField[]): ParameterField[] {
  return fields.filter((item: ParameterField): boolean => {
    if (panel === 'Controls') {
      const method = parameterValue(fields, 'method');
      if (['cycles', 'lambda', 'svd', 'shift'].includes(item.key) && !method) { return false; }
      if (item.key === 'shift') { return !method.includes('Hessian'); }
      if (['cycles', 'svd'].includes(item.key)) { return method.includes('Hessian'); }
      if (item.key === 'lambda') { return method === 'analytic Hessian'; }
    }
    if (panel === 'Background' && /^b[0-9]+$/.test(item.key)) { return Number(item.key.slice(1)) < Number(parameterValue(fields, 'count')); }
    if (panel === 'Instrument Parameters' && item.key !== 'type') {
      const type = parameterValue(fields, 'type');
      if (!type) { return false; }
      const tof: string[] = ['difC', 'difA', 'difB', 'Zero', 'alpha', 'beta-0', 'beta-1', 'beta-q', 'sig-0', 'sig-1', 'sig-2', 'sig-q', 'X', 'Y', 'Z'];
      return type === 'PNT' ? tof.includes(item.key) : ['Lam', 'Zero', 'U', 'V', 'W', 'X', 'Y', 'Z', 'SH/L'].includes(item.key) || (type === 'PXC' && item.key === 'Polariz.');
    }
    if (panel === 'Sample Parameters') {
      const geometry = parameterValue(fields, 'geometry');
      if (['DisplaceX', 'DisplaceY', 'Absorption'].includes(item.key)) { return geometry === 'Debye-Scherrer'; }
      if (['Shift', 'Transparency', 'SurfRoughA', 'SurfRoughB'].includes(item.key)) { return geometry === 'Bragg-Brentano'; }
    }
    return true;
  });
}
export function validateParameters(panel: string, fields: ParameterField[]): string {
  // Hidden values remain drafts when changing a method/template. Validate them too,
  // so switching back never exposes an invalid value restored from storage.
  for (const item of fields) {
    const value = item.value.trim();
    if (value.length > (item.numeric ? 64 : 512)) { return `${item.label}: value is too long.`; }
    if (!value) { if (item.refine) { return `${item.label}: Refine requires a value.`; } continue; }
    if (item.choices.length > 0 && !item.choices.includes(value)) { return `${item.label}: select a listed value.`; }
    if (item.numeric && (!/^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$/.test(value) || !Number.isFinite(Number(value)) || Number(value) < item.min || Number(value) > item.max)) {
      return `${item.label}: invalid number or outside allowed range.`;
    }
  }
  if (panel === 'Limits') {
    const lower = parameterValue(fields, 'lower').trim(); const upper = parameterValue(fields, 'upper').trim();
    if ((lower === '') !== (upper === '') || (lower !== '' && Number(lower) >= Number(upper))) { return 'Tmin and Tmax must both be set, with Tmin < Tmax.'; }
  }
  return '';
}
export function serializeParameters(panel: string, scope: string, fields: ParameterField[]): string {
  const error = validateParameters(panel, fields);
  if (error) { throw new Error(error); }
  const values = fields.map((item: ParameterField): SavedParameterField => ({ key: item.key,
    value: item.numeric || item.choices.length > 0 ? item.value.trim() : item.value, refine: item.refine }));
  const record: ParameterRecord = { version: 1, panel, scope, fields: values };
  const json = JSON.stringify(record);
  if (json.length > 8192) { throw new Error('Parameter draft exceeds Preferences storage limit.'); }
  return json;
}
export function restoreParameters(panel: string, scope: string, json: string): ParameterField[] {
  const result = parameterFields(panel);
  if (!json) { return result; }
  const record = JSON.parse(json) as ParameterRecord;
  if (!record || record.version !== 1 || record.scope !== scope ||
    (record.panel !== undefined && record.panel !== panel) || !Array.isArray(record.fields)) { throw new Error('Invalid parameter draft.'); }
  const seen: string[] = [];
  for (const saved of record.fields) {
    if (!saved || typeof saved.key !== 'string' || typeof saved.value !== 'string' || typeof saved.refine !== 'boolean' || seen.includes(saved.key)) { throw new Error('Invalid parameter field.'); }
    const target = result.find((item: ParameterField): boolean => item.key === saved.key);
    if (!target || saved.value.length > 512 || (saved.refine && !target.refinable)) { throw new Error('Invalid parameter field.'); }
    seen.push(saved.key); target.value = target.numeric || target.choices.length > 0 ? saved.value.trim() : saved.value; target.refine = saved.refine;
  }
  const error = validateParameters(panel, result);
  if (error) { throw new Error(error); }
  return result;
}
