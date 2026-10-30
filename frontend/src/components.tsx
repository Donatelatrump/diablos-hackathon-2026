import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { api, format, hands, pitchNames } from './api';
import type { Row } from './api';

export function Notice({ children, error = false }: { children: ReactNode; error?: boolean }) {
  return <div className={`notice ${error ? 'error' : ''}`} role={error ? 'alert' : 'status'}>{children}</div>;
}

export function useResource<T>(url: string) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setData(undefined); setError('');
    api<T>(url, { signal: controller.signal }).then(setData).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [url, revision]);
  return { data, error, retry: () => setRevision(x => x + 1) };
}

const labels: Record<string, string> = { year: 'Temporada', pitcher_anon_id: 'Lanzador', n_pitches: 'Lanzamientos', n_games: 'Juegos', stuff_plus: 'Stuff+', pitching_plus: 'Pitching+', location_plus: 'Location+', AutoPitchType: 'Lanzamiento', indice_integral: 'Índice integral · fijo', indice_integral_temporada_estadio: 'Índice integral · ajustado', p_out_within_pa: 'Probabilidad de out al cerrar el turno', pitch_type: 'Lanzamiento', hand: 'Mano', n_calibration: 'Muestra de calibración', n_top: 'Muestra superior', qualification: 'Alcance', task: 'Resultado' };

export function DataTable({ rows, columns }: { rows: Row[]; columns?: string[] }) {
  const [sort, setSort] = useState<{ key: string; direction: number }>();
  const [page, setPage] = useState(0);
  useEffect(() => { setPage(0); }, [rows]);
  const keys = columns || Object.keys(rows[0] || {});
  const sorted = useMemo(() => [...rows].sort((a, b) => {
    if (!sort) return 0;
    const x = a[sort.key], y = b[sort.key];
    if (x === null || x === '') return 1;
    if (y === null || y === '') return -1;
    return (Number.isFinite(Number(x)) && Number.isFinite(Number(y)) ? Number(x) - Number(y) : String(x).localeCompare(String(y))) * sort.direction;
  }), [rows, sort]);
  if (!rows.length) return <Notice>No hay resultados disponibles para esta selección.</Notice>;
  const pages = Math.ceil(rows.length / 25);
  return <><div className="table-scroll" tabIndex={0} aria-label="Tabla de resultados, desplaza para ver todas las columnas"><table><thead><tr>{keys.map(key => <th key={key} aria-sort={sort?.key === key ? sort.direction === 1 ? 'ascending' : 'descending' : 'none'}><button onClick={() => { setSort({ key, direction: sort?.key === key ? -sort.direction : -1 }); setPage(0); }}>{labels[key] || key.replaceAll('_', ' ')} {sort?.key === key ? sort.direction === 1 ? '↑' : '↓' : '↕'}</button></th>)}</tr></thead><tbody>{sorted.slice(page * 25, (page + 1) * 25).map((row, i) => <tr key={i}>{keys.map(key => <td key={key}>{['AutoPitchType', 'pitch_type'].includes(key) ? pitchNames[String(row[key])] || format(row[key]) : key === 'hand' ? hands[String(row[key])] || format(row[key]) : format(typeof row[key] === 'string' && row[key] !== '' && Number.isFinite(Number(row[key])) ? Number(row[key]) : row[key], 3)}</td>)}</tr>)}</tbody></table></div><div className="pagination"><span>{rows.length.toLocaleString('es-MX')} registros · Página {page + 1} de {pages}</span><button disabled={page === 0} onClick={() => setPage(p => p - 1)}>Anterior</button><button disabled={page + 1 >= pages} onClick={() => setPage(p => p + 1)}>Siguiente</button></div></>;
}

export function SavedTable({ name, run = '', title }: { name: string; run?: string; title: string }) {
  const url = `/api/table?name=${name}${run ? `&run=${run}` : ''}`;
  const { data, error, retry } = useResource<{ rows: Row[]; source: string }>(url);
  return <section className="panel"><div className="section-heading"><h2>{title}</h2>{!!data?.rows.length && <a className="button" href={`${url}&download=1`}>Descargar CSV ↓</a>}</div>{error ? <Notice error>{error} <button onClick={retry}>Reintentar</button></Notice> : data ? <><DataTable rows={data.rows} /><small>Fuente: {data.source}</small></> : <Notice>Cargando resultados…</Notice>}</section>;
}

let sceneAssets: Promise<[string, string]> | undefined;
function getSceneAssets() {
  return sceneAssets ||= Promise.all(['/assets/visualizacion/dashboard_pitch_animation.html', '/assets/visualizacion/dashboard_pitch_scene.bundle.js'].map(async path => {
    const response = await fetch(path);
    if (!response.ok) throw new Error('No se pudo cargar la escena 3D.');
    return response.text();
  })) as Promise<[string, string]>;
}

export function PitchScene({ pitch, hand, values }: { pitch: string; hand: string; values: Record<string, number | null> }) {
  const [assets, setAssets] = useState<[string, string]>();
  const [error, setError] = useState('');
  const [lab, setLab] = useState(false);
  const [origin, setOrigin] = useState(0);
  const [destination, setDestination] = useState(2240);
  useEffect(() => { let active = true; getSceneAssets().then(data => { if (active) setAssets(data); }).catch(e => { sceneAssets = undefined; if (active) setError(e.message); }); return () => { active = false; }; }, []);
  const speed = values.RelSpeed, hb = values.HorzBreak, ivb = values.InducedVertBreak;
  const document = useMemo(() => {
    if (!assets || speed === null || hb === null || ivb === null || ![speed, hb, ivb].every(Number.isFinite) || speed <= 0) return '';
    const ratio = lab ? ((1 - 2.25577e-5 * destination) / (1 - 2.25577e-5 * origin)) ** 4.25588 : 1;
    const measurements = { RelSpeed: speed, HorzBreak: hb * ratio, InducedVertBreak: ivb * ratio, hand, ...(lab ? { comparison: { RelSpeed: speed, HorzBreak: hb, InducedVertBreak: ivb } } : {}) };
    const escape = (text: string) => text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
    const template = lab ? assets[0].replace('Línea roja: lanzamiento elegido · Línea azul punteada: referencia sin movimiento inducido, a 90 mph.', 'Línea roja: destino exploratorio · Línea azul punteada: mediciones de origen.') : assets[0];
    return template.replace('__PITCH__', escape(pitchNames[pitch] || pitch)).replace('__HAND__', escape(hands[hand] || hand)).replace('__MEASUREMENTS__', JSON.stringify(measurements)).replace('__THREE_SCENE__', () => assets[1]);
  }, [assets, speed, hb, ivb, hand, pitch, lab, origin, destination]);
  return <section className="scene"><div className="section-heading"><h2>Mira el lanzamiento en 3D</h2><span className="tag">Movimiento ilustrado</span></div>{error ? <Notice error>{error}</Notice> : document ? <iframe title="Escena 3D del lanzamiento" srcDoc={document} /> : <Notice>{assets ? 'Completa velocidad y movimiento para ver la ilustración.' : 'Cargando visualización…'}</Notice>}<label className="check"><input type="checkbox" checked={lab} onChange={e => setLab(e.target.checked)} /> Explorar el efecto de la altitud</label>{lab && <div className="lab"><Notice>Hipótesis de densidad con velocidad y tiempo de vuelo fijos. No representa un vuelo validado ni modifica los índices. Rojo: destino; azul: origen.</Notice><label>Altitud de origen · {origin} m<input type="range" min="0" max="3000" step="10" value={origin} onChange={e => setOrigin(+e.target.value)} /></label><label>Altitud de destino · {destination} m<input type="range" min="0" max="3000" step="10" value={destination} onChange={e => setDestination(+e.target.value)} /></label></div>}</section>;
}
