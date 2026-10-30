import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import ReactMarkdown from 'react-markdown';
import type { Bootstrap, Document, Metric, Row, Run } from './api';
import { format, pitchNames, tasks } from './api';
import { DataTable, Notice, useResource } from './components';
import Simulator from './Simulator';

const routes = [['simulador', 'Simulador'], ['lanzadores', 'Lanzadores'], ['confianza', 'Confianza'], ['ayuda', 'Ayuda']];
function currentRoute() { const route = location.hash.slice(1); return routes.some(([id]) => id === route) ? route : 'simulador'; }
const runLabels: Record<string, string> = { stuff_plus_output_v9_estadios: 'Modelo actual por estadios', stuff_plus_output_v9_incremental: 'v9 · Validación incremental', stuff_plus_output_v9: 'v9 original' };

function DocumentView({ document }: { document: Document }) {
  const [text, setText] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setText(''); setError('');
    if (document.markdown) fetch(`/api/document/${document.id}`, { signal: controller.signal }).then(async response => { if (!response.ok) throw new Error('No se pudo leer el documento.'); return response.text(); }).then(setText).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [document]);
  return <section className="panel"><div className="section-heading"><h2>{document.title}</h2><a className="button" href={`/api/document/${document.id}?download=1`}>Descargar ↓</a></div>{error ? <Notice error>{error}</Notice> : document.markdown ? text ? <div className="markdown"><ReactMarkdown components={{ a: ({ href, children }) => href?.startsWith('https://') || href?.startsWith('http://') ? <a href={href} target="_blank" rel="noreferrer">{children}</a> : <span>{children}</span> }}>{text}</ReactMarkdown></div> : <Notice>Cargando documento…</Notice> : <a href={`/api/document/${document.id}`} target="_blank" rel="noreferrer">Abrir PDF en otra pestaña ↗</a>}</section>;
}

function Help({ documents }: { documents: Document[] }) {
  const [selected, setSelected] = useState('guide');
  const document = documents.find(d => d.id === selected);
  return <><header className="page-title"><span className="eyebrow">LEE LOS DATOS CON CONTEXTO</span><h1>Cómo leer tu <em>evaluación.</em></h1><p>Tres preguntas sobre el mismo lanzamiento.</p></header><div className="reading-strip">{[['Stuff+', 'Resume velocidad, giro y movimiento frente a lanzamientos históricos comparables.'], ['Location+', 'Evalúa la ubicación de la pelota, el conteo y el lado del bateador.'], ['Pitching+', 'Combina la calidad física con el contexto disponible.']].map(([title, description]) => <article key={title}><h2>{title}</h2><p>{description}</p></article>)}</div><section className="panel">{[['¿Qué significa 100?', '100 es la referencia histórica de cada índice. 110 equivale a una desviación estándar por encima; no significa 10% más outs.'], ['¿Por qué no cambia entre estadios?', 'Cuando la capa de entorno no demuestra una mejora, el modelo conserva la estimación anterior. Algunas probabilidades pueden variar aunque los índices sean iguales.'], ['¿Qué representa la animación?', 'Ilustra el movimiento medido, amplificado para verlo mejor. El laboratorio de altitud explora una hipótesis de densidad; no modifica los índices.'], ['¿Puedo tomar una decisión solo con el modelo?', 'Usa los resultados junto con video, salud, rol, muestra y criterio del cuerpo técnico. 2026 ya fue inspeccionado durante el desarrollo; hace falta una evaluación futura independiente.']].map(([title, answer]) => <details key={title}><summary>{title}</summary><p>{answer}</p></details>)}</section><label className="document-select">Documentación<select value={selected} onChange={e => setSelected(e.target.value)}>{documents.filter(d => !d.id.startsWith('v8')).map(d => <option value={d.id} key={d.id}>{d.title}</option>)}</select></label>{document && <DocumentView document={document} />}</>;
}

function Confidence({ run }: { run?: Run }) {
  const { data, error, retry } = useResource<Record<string, Metric[]>>(`/api/evidence${run ? `?run=${run.id}` : ''}`);
  const [mode, setMode] = useState('season');
  const records = data?.[mode] || [];
  const physical = records.find(row => row.task === 'stuff_run_value')?.metrics.mse_skill_vs_count;
  const modes = [['season', 'Otra temporada'], ['pitcher', 'Lanzadores nuevos'], ['park', 'Sin haber visto Harp']];
  return <><header className="page-title"><h1>¿Cuánto podemos <em>confiar?</em></h1></header>{error ? <Notice error>{error} <button onClick={retry}>Reintentar</button></Notice> : !data ? <Notice>Cargando evidencia…</Notice> : <><Notice>{run ? `Modelo seleccionado: ${runLabels[run.id]}. Las pruebas de lanzadores nuevos y Harp corresponden al reporte v9 por estadios.` : 'Resultados guardados del modelo v9 por estadios. El modelo de simulación no está instalado en este equipo.'}</Notice><div className="score-grid">{modes.map(([key, title]) => { const record = data[key]?.find(row => row.task === 'environment_run_value'); return <article className="score-card" key={key}><span className="eyebrow">{title}</span><strong>{record?.vs_baseline ? `${format(record.vs_baseline.gain * 100, 2)}%` : '—'}</strong><span>Reducción del error frente al conteo</span><p>{record ? `${format(record.n, 0)} lanzamientos evaluados` : 'Sin evaluación disponible'}</p>{record?.vs_baseline && <small>Intervalo: {format(record.vs_baseline.ci_low * 100, 2)}% a {format(record.vs_baseline.ci_high * 100, 2)}%</small>}</article>; })}</div><section className="panel"><label>Prueba evaluada<select value={mode} onChange={e => setMode(e.target.value)}>{modes.map(([key, title]) => <option key={key} value={key}>{title}</option>)}</select></label>{physical != null && <Notice>La capa física tiene un error cuadrático {format(Math.abs(physical) * 100, 2)}% {physical < 0 ? 'mayor' : 'menor'} que una referencia que conoce solo el conteo.</Notice>}<h2>Errores y calibración</h2><p>No hay un único porcentaje de precisión. Menor error Brier es mejor; las tareas tienen muestras y denominadores distintos.</p><DataTable rows={records.map(row => ({ Resultado: tasks[row.task] || row.task, Muestra: row.n, 'Error Brier': row.metrics.brier ?? null, 'Brier de referencia': row.metrics.brier_baseline ?? null, 'Mejora Brier (%)': row.metrics.brier_skill == null ? null : row.metrics.brier_skill * 100, 'Calibración (pp)': row.metrics.ece_10_bins == null ? null : row.metrics.ece_10_bins * 100, RMSE: row.metrics.rmse ?? null }))} /><a className="button" download={`metricas-${mode}.json`} href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(records, null, 2))}`}>Descargar métricas ↓</a></section></>}<section className="panel"><h2>Qué sabemos y qué falta comprobar</h2><p>Las comparaciones mantienen fija la física medida. Los promedios de lanzadores describen la muestra evaluada, no garantizan talento futuro ni resistencia a la altura.</p><p>2026 es un benchmark reutilizado. Las pruebas retrospectivas no sustituyen una evaluación con datos futuros. El target de carreras es un proxy y las diferencias entre escenarios no son efectos causales.</p></section></>;
}

function Movement({ rows }: { rows: Row[] }) {
  const points = rows.filter(row => row.HB != null && row.IVB != null && Number.isFinite(Number(row.HB)) && Number.isFinite(Number(row.IVB)));
  if (!points.length) return <Notice>No hay mediciones de movimiento disponibles para esta selección.</Notice>;
  const scale = Math.max(25, ...points.flatMap(row => [Math.abs(Number(row.HB)), Math.abs(Number(row.IVB))])) * 1.1;
  return <figure className="movement-chart"><svg viewBox="0 0 520 360" role="img" aria-label="Mapa de movimiento horizontal y vertical en pulgadas"><line x1="260" y1="30" x2="260" y2="310" /><line x1="50" y1="170" x2="470" y2="170" /><text x="260" y="345" textAnchor="middle">Movimiento lateral · relativo a la mano (pulgadas)</text><text x="12" y="175" transform="rotate(-90 12 175)" textAnchor="middle">Movimiento vertical (pulgadas)</text>{[-20, -10, 0, 10, 20].map(value => <g key={value}><text x={260 + value / scale * 200} y="190" textAnchor="middle">{value}</text><text x="230" y={170 - value / scale * 130}>{value}</text></g>)}{points.map((row, i) => <circle key={i} cx={260 + Number(row.HB) / scale * 200} cy={170 - Number(row.IVB) / scale * 130} r="6"><title>{pitchNames[String(row.AutoPitchType)] || row.AutoPitchType}: HB {format(Number(row.HB))}, IVB {format(Number(row.IVB))}</title></circle>)}</svg><figcaption>Movimiento observado por lanzamiento. Consulta los valores en la tabla de repertorio.</figcaption></figure>;
}

function Pitchers({ run }: { run?: Run }) {
  const name = run ? 'pitchers' : 'integral';
  const url = `/api/table?name=${name}${run ? `&run=${run.id}` : ''}`;
  const { data, error, retry } = useResource<{ rows: Row[]; source: string }>(url);
  const repertoire = useResource<{ rows: Row[] }>(`/api/table?name=${run ? 'arsenal' : 'integral-arsenal'}${run ? `&run=${run.id}` : ''}`);
  const movement = useResource<{ rows: Row[] }>(`/api/table?name=movement${run ? `&run=${run.id}` : ''}`);
  const [minimum, setMinimum] = useState(true);
  const [query, setQuery] = useState('');
  const [year, setYear] = useState('');
  const [chosen, setChosen] = useState('');
  const years = [...new Set(data?.rows.map(row => String(row.year)) || [])].sort().reverse();
  const selectedYear = years.includes(year) ? year : years[0];
  const scoreKey = run ? 'pitching_plus' : 'indice_integral_temporada_estadio';
  const filtered = useMemo(() => (data?.rows || []).filter(row => String(row.year) === selectedYear && (!minimum || Number(row.n_pitches) >= 100 && Number(row.n_games) >= 5) && String(row.pitcher_anon_id).toLowerCase().includes(query.toLowerCase())).sort((a, b) => Number(b[scoreKey]) - Number(a[scoreKey])), [data, minimum, query, selectedYear, scoreKey]);
  const current = filtered.find(row => row.pitcher_anon_id === chosen) || filtered[0];
  const selectedRows = (rows: Row[] = []) => rows.filter(row => row.pitcher_anon_id === current?.pitcher_anon_id && String(row.year) === selectedYear);
  return <><header className="page-title"><h1>Conoce al <em>lanzador.</em></h1></header>{!run && <Notice>Mostrando el reporte integral guardado: índice ajustado por temporada y estadio. Esta referencia es distinta de los índices del simulador.</Notice>}<section className="panel"><div className="filter-bar"><label>Buscar lanzador<input type="search" placeholder="pitcher_00002" value={query} onChange={e => setQuery(e.target.value)} /></label><label>Temporada<select value={selectedYear || ''} onChange={e => setYear(e.target.value)}>{years.map(value => <option key={value}>{value}</option>)}</select></label><label className="check"><input type="checkbox" checked={minimum} onChange={e => setMinimum(e.target.checked)} /> Al menos 100 lanzamientos y 5 juegos</label></div>{error ? <Notice error>{error} <button onClick={retry}>Reintentar</button></Notice> : !data ? <Notice>Cargando lanzadores…</Notice> : <><label>Lanzador que quieres conocer<select value={current ? String(current.pitcher_anon_id) : ''} onChange={e => setChosen(e.target.value)}>{filtered.map(row => <option key={String(row.pitcher_anon_id)} value={String(row.pitcher_anon_id)}>{String(row.pitcher_anon_id).replace('pitcher_', 'Lanzador ')}</option>)}</select></label>{current && <article className="pitcher-card"><span className="eyebrow">TEMPORADA {selectedYear}</span><h2>{String(current.pitcher_anon_id).replace('pitcher_', 'Lanzador ')}</h2><div className="score-grid">{[scoreKey, 'n_pitches', 'n_games'].map(key => <div key={key}><strong>{format(Number(current[key]), key === scoreKey ? 1 : 0)}</strong><span>{key === scoreKey ? run ? 'Pitching+' : 'Índice integral ajustado' : key === 'n_pitches' ? 'Lanzamientos' : 'Juegos'}</span></div>)}</div><p>Describe la muestra evaluada, no el talento futuro. Revisa video, salud y rol con el coach.</p></article>}<DataTable rows={filtered} /><a className="button" href={`${url}&download=1`}>Descargar tabla completa ↓</a></>}</section>{current && <section className="panel"><h2>Repertorio · {String(current.pitcher_anon_id).replace('pitcher_', 'Lanzador ')}</h2>{repertoire.error ? <Notice error>{repertoire.error}</Notice> : !repertoire.data ? <Notice>Cargando repertorio…</Notice> : <DataTable rows={selectedRows(repertoire.data.rows)} />}{run && <Movement rows={(movement.data?.rows || []).filter(row => row.pitcher_anon_id === current.pitcher_anon_id)} />}</section>}</>;
}

export default function App() {
  const { data, error, retry } = useResource<Bootstrap>('/api/bootstrap');
  const [route, setRoute] = useState(currentRoute);
  const [runId, setRunId] = useState('');
  const [headerCompact, setHeaderCompact] = useState(() => window.scrollY > 240);
  useEffect(() => {
    const update = () => setHeaderCompact(compact => compact ? window.scrollY > 120 : window.scrollY > 240);
    update();
    window.addEventListener('scroll', update, { passive: true });
    return () => window.removeEventListener('scroll', update);
  }, []);
  useEffect(() => { const change = () => { setRoute(currentRoute()); window.scrollTo(0, 0); }; window.addEventListener('hashchange', change); return () => window.removeEventListener('hashchange', change); }, []);
  const run = data?.runs.find(value => value.id === runId) || data?.runs[0];
  return <><a className="skip" href="#content">Ir al contenido</a><header className={`masthead${headerCompact ? ' is-compact' : ''}`}><div className="header-inner"><a href="#simulador" className="brand" aria-label="Diablos · Simulador"><img src="/imgs/diablos-rojos-del-mexico-logo-brandlogos.net_kvga6c13n.svg" alt="" /></a><nav aria-label="Navegación principal" style={{ '--active-tab': routes.findIndex(([id]) => id === route), '--tab-count': routes.length } as CSSProperties}>{routes.map(([key, label]) => <a key={key} href={`#${key}`} className={route === key ? 'active' : ''} aria-current={route === key ? 'page' : undefined}>{label}</a>)}</nav></div></header><main id="content" tabIndex={-1}><div className="section-transition" key={route}>{error ? <Notice error>No se pudo conectar con la API. Inicia el servidor Python y vuelve a intentar. <button onClick={retry}>Reintentar</button></Notice> : !data ? <Notice>Cargando dashboard…</Notice> : <>{data.runs.length > 1 && <label className="run-select">Versión de los resultados<select value={run?.id} onChange={e => setRunId(e.target.value)}>{data.runs.map(value => <option key={value.id} value={value.id}>{runLabels[value.id]}</option>)}</select></label>}{route === 'simulador' ? <Simulator key={run?.id || 'simulador'} run={run} /> : route === 'lanzadores' ? <Pitchers key={run?.id || 'saved'} run={run} /> : route === 'confianza' ? <Confidence run={run} /> : <Help documents={data.documents} />}<section className="route-cards" aria-label="Explora el análisis">{[['simulador', 'Para el coach', 'Comparar el contexto'], ['lanzadores', 'Para dirección deportiva', 'Conocer un lanzador'], ['confianza', 'Para interpretar la evidencia', 'Saber cuánto confiar']].map(([key, label, title]) => <a href={`#${key}`} key={key}><span className="eyebrow">{label}</span><h3>{title} <span aria-hidden="true">↗</span></h3></a>)}</section></>}</div></main><footer><b>DIABLOS · ANÁLISIS DE PITCHEO</b><span>LMB · ISAC 2026 · Apoyo para el criterio deportivo.</span></footer></>;
}
