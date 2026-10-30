export type Row = Record<string, string | number | boolean | null>;
export type Profile = { type: string; hand: string; n: number; median: Record<string, number | null>; p01: Record<string, number | null>; p99: Record<string, number | null> };
export type Run = { id: string; profiles: Profile[]; stadiums: { stadium_id: string; estadio: string }[]; stadium_context: boolean; pitchers: string[] };
export type Document = { id: string; title: string; markdown: boolean };
export type Bootstrap = { runs: Run[]; documents: Document[] };
export type Metric = { task: string; n: number; metrics: Record<string, number>; vs_baseline?: { gain: number; ci_low: number; ci_high: number } };
export type Evaluation = { results: Row[]; outside: string[]; reference: Record<string, { informative?: boolean }> };

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.error || 'No se pudo conectar con el servidor. Intenta de nuevo.');
  }
  return response.json();
}

export const pitchNames: Record<string, string> = { 'Four-Seam': 'Recta de cuatro costuras', Curveball: 'Curva', Slider: 'Slider', Changeup: 'Cambio', Sinker: 'Sinker', Cutter: 'Cutter', Splitter: 'Splitter', Sweeper: 'Sweeper', Other: 'Otro' };
export const hands: Record<string, string> = { Right: 'Derecho', Left: 'Zurdo', Undefined: 'Sin dato' };
export const tasks: Record<string, string> = { stuff_run_value: 'Calidad física', xrunvalue: 'Física y ubicación', arsenal_run_value: 'Con repertorio', environment_run_value: 'Evaluación combinada', whiff: 'Swing fallido', whiff_given_swing: 'Fallo cuando intenta batear', home_run_per_pitch: 'Jonrón', ball_in_play: 'Bola en juego', called_strike: 'Strike cantado', chase: 'Swing fuera de zona', groundball_given_in_play: 'Rodado entre bolas en juego' };
export const format = (value: unknown, digits = 1) => value === null || value === undefined || value === '' ? '—' : typeof value === 'number' ? value.toLocaleString('es-MX', { maximumFractionDigits: digits }) : String(value);
