import { useEffect, useRef, useState } from 'react';
import { api, format, hands, pitchNames } from './api';
import type { Evaluation, Profile, Run } from './api';
import { DataTable, Notice, PitchScene, SavedTable } from './components';
import MovementMap from './MovementMap';

const measurementNames: Record<string, string> = { RelSpeed: 'Velocidad (mph)', InducedVertBreak: 'Movimiento vertical (pulgadas)', HorzBreak: 'Movimiento lateral (pulgadas)', SpinRate: 'Giro (rpm)', EffectiveVelo: 'Velocidad efectiva (mph)', SpinAxis: 'Eje de giro (grados)', RelHeight: 'Altura de salida (pies)', RelSide: 'Lado de salida (pies)', Extension: 'Extensión (pies)', VertBreak: 'Movimiento vertical total (pulgadas)', PlateLocHeight: 'Altura en plato (pies)', PlateLocSide: 'Lado en plato (pies)', Balls: 'Bolas', Strikes: 'Strikes' };
const core = ['RelSpeed', 'InducedVertBreak', 'HorzBreak', 'SpinRate'];
const example: Profile = { type: 'Four-Seam', hand: 'Right', n: 0, median: { RelSpeed: 90, InducedVertBreak: 15, HorzBreak: 8, SpinRate: 2200 }, p01: {}, p99: {} };

export default function Simulator({ run }: { run?: Run }) {
  const profiles = run?.profiles.length ? run.profiles : [example];
  const [profileIndex, setProfileIndex] = useState(() => Math.max(0, profiles.findIndex(p => p.type === 'Four-Seam')));
  const profile = profiles[profileIndex];
  const initial = (p: Profile) => ({ ...p.median, PlateLocHeight: 2.5, PlateLocSide: 0, Balls: 0, Strikes: 0 });
  const [values, setValues] = useState<Record<string, number | null>>(() => initial(profile));
  const scenarios = run?.stadium_context
    ? run.stadiums.map(s => ({ id: s.stadium_id, label: s.estadio }))
    : [{ id: 'Extreme Altitude', label: 'Altitud extrema' }, { id: 'No Altitude', label: 'Altitud baja' }, { id: 'Medium Altitude', label: 'Altitud media' }];
  const [selected, setSelected] = useState(() => {
    const first = scenarios.find(s => s.id === 'mexico_ahh') || scenarios[0];
    const second = scenarios.find(s => s.id === 'veracruz_avila' && s.id !== first?.id) || scenarios.find(s => s.id !== first?.id);
    return [first?.id || '', second?.id || ''];
  });
  const comparisonAvailable = selected.every(id => scenarios.some(s => s.id === id)) && selected[0] !== selected[1];
  const [batter, setBatter] = useState('Right');
  const [pitcher, setPitcher] = useState('unknown');
  const [evaluation, setEvaluation] = useState<Evaluation>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const resultRef = useRef<HTMLElement>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  function selectProfile(index: number) { setProfileIndex(index); setValues(initial(profiles[index])); setEvaluation(undefined); setDirty(false); setError(''); }
  async function submit() {
    setError(''); setBusy(true);
    controller.current = new AbortController();
    try {
      const result = await api<Evaluation>('/api/simulate', { method: 'POST', signal: controller.current.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ run: run?.id, pitch: profile.type, hand: profile.hand, measurements: values, stadiums: selected.filter(Boolean), batter, pitcher }) });
      setEvaluation(result); setDirty(false);
      requestAnimationFrame(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
    } catch (e) { if (!(e instanceof DOMException && e.name === 'AbortError')) setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const field = (key: string) => <label key={key}>{measurementNames[key] || key}<input type="number" step={key === 'Balls' || key === 'Strikes' ? 1 : 'any'} min={key === 'Balls' || key === 'Strikes' ? 0 : key === 'RelSpeed' ? 0.01 : undefined} max={key === 'Balls' ? 3 : key === 'Strikes' ? 2 : undefined} value={values[key] ?? ''} required onChange={e => { setValues({ ...values, [key]: e.target.value === '' ? null : +e.target.value }); setDirty(true); }} /></label>;
  return <><div className="hero"><h1>Simulador de <em>lanzamientos.</em></h1></div>{!run && <Notice>El análisis v9 aún no está disponible en este equipo. La visualización usa un ejemplo ilustrativo de 90 mph; no genera puntuaciones. Puedes consultar los resultados guardados en Lanzadores y Confianza.</Notice>}<div className="workbench"><form className="panel" onSubmit={e => { e.preventDefault(); void submit(); }}><fieldset disabled={busy}><h3><span className="step">01</span> Elige tu lanzamiento</h3><label>Tipo de lanzamiento<select value={profile.type} onChange={e => selectProfile(profiles.findIndex(p => p.type === e.target.value))}>{[...new Set(profiles.map(p => p.type))].map(type => <option key={type} value={type}>{pitchNames[type] || type}</option>)}</select></label><label>Mano del lanzador<select value={profileIndex} onChange={e => selectProfile(+e.target.value)}>{profiles.map((p, i) => p.type === profile.type && <option key={i} value={i}>{hands[p.hand] || p.hand}</option>)}</select></label><p className="muted">{profile.n ? `Perfil de ${format(profile.n, 0)} lanzamientos de entrenamiento.` : 'Ejemplo ilustrativo; no representa a un jugador concreto.'}</p><h3><span className="step">02</span> Características físicas</h3><div className="fields">{core.map(field)}</div><p className="muted">Compara dos escenarios con las mismas mediciones del lanzamiento.</p><h3>Estadios para comparar</h3><div className="fields">{selected.map((id, index) => <label key={index}>{`Escenario ${index + 1}`}<select value={id} onChange={e => { setSelected(selected.map((value, i) => i === index ? e.target.value : value)); setDirty(true); }}>{scenarios.map(s => <option key={s.id} value={s.id} disabled={s.id === selected[1 - index]}>{s.label}</option>)}</select></label>)}</div><details><summary>Ubicación, salida y repertorio</summary><div className="fields">{Object.keys(values).filter(key => !core.includes(key)).map(field)}</div><label>Lado del bateador<select value={batter} onChange={e => { setBatter(e.target.value); setDirty(true); }}><option value="Right">Derecho</option><option value="Left">Zurdo</option></select></label><label>Arsenal histórico<select value={pitcher} onChange={e => { setPitcher(e.target.value); setDirty(true); }}><option value="unknown">Sin historial</option>{run?.pitchers.map(id => <option key={id}>{id}</option>)}</select></label></details><button className="primary full" disabled={!run || !comparisonAvailable || busy || !selected[0] || Object.values(values).some(v => v === null)} type="submit">{busy ? 'Preparando evaluación…' : 'Estimar Stuff+ →'}</button></fieldset>{error && <Notice error>{error}</Notice>}<small>Las mediciones iniciales son valores típicos. Sustitúyelas por las de tu lanzamiento.</small>{!comparisonAvailable && <Notice>Selecciona dos escenarios distintos disponibles en el modelo.</Notice>}</form><PitchScene pitch={profile.type} hand={profile.hand} values={values} /></div><section className="panel results" ref={resultRef} aria-live="polite"><h2><span className="step">03</span> Comparación entre estadios</h2>{evaluation ? <>{dirty && <Notice>Los datos cambiaron. Pulsa «Estimar Stuff+» para actualizar los resultados.</Notice>}{evaluation.outside.length > 0 && <Notice>Mediciones fuera del rango central de entrenamiento: {evaluation.outside.map(key => measurementNames[key] || key).join(', ')}. Interpreta con cautela.</Notice>}<div className="score-grid stadium-comparison">{evaluation.results.map((result, i) => <article className="score-card" key={i}><span className="eyebrow">{String(result.stadium)}</span><strong>{format(result.stuff_plus)}</strong><span>Stuff+ · Calidad física</span><div className="score-pair"><span>Pitching+<b>{format(result.pitching_plus)}</b></span><span>Location+<b>{format(result.location_plus)}</b></span></div>{['p_whiff', 'p_home_run_per_pitch'].map(key => result[key] != null && <p key={key}>{key === 'p_whiff' ? 'Swing fallido' : 'Jonrón'}: {format(Number(result[key]) * 100, 3)}%</p>)}</article>)}</div><h3>Diferencias en las probabilidades</h3><p>Probabilidades en porcentaje. La diferencia es el segundo escenario menos el primero, en puntos porcentuales.</p><DataTable rows={[
    ['p_whiff', 'Swing fallido por lanzamiento'],
    ['p_whiff_given_swing', 'Fallo cuando intenta batear'],
    ['p_ball_in_play', 'Bola en juego'],
    ['p_groundball_given_in_play', 'Rodado entre bolas en juego'],
    ['p_weak_contact', 'Contacto débil'],
    ['p_hard_contact', 'Contacto fuerte'],
    ['p_home_run_per_pitch', 'Jonrón por lanzamiento'],
  ].filter(([key]) => evaluation.results.length === 2 && evaluation.results.every(r => typeof r[key] === 'number')).map(([key, label]) => ({
    Resultado: label,
    [`1 · ${evaluation.results[0].stadium} (%)`]: Number(evaluation.results[0][key]) * 100,
    [`2 · ${evaluation.results[1].stadium} (%)`]: Number(evaluation.results[1][key]) * 100,
    'Diferencia (pp)': (Number(evaluation.results[1][key]) - Number(evaluation.results[0][key])) * 100,
  }))} />{evaluation.results.length === 2 && ['p_whiff', 'p_whiff_given_swing', 'p_ball_in_play', 'p_groundball_given_in_play', 'p_weak_contact', 'p_hard_contact', 'p_home_run_per_pitch'].every(key => evaluation.results[0][key] === evaluation.results[1][key]) && <Notice>El modelo devuelve las mismas probabilidades para estos escenarios y mediciones.</Notice>}{evaluation.reference.stuff_plus?.informative === false && <Notice>Esta referencia es constante: no permite distinguir entre lanzamientos.</Notice>}<Notice>En v9, Stuff+ evalúa la física y no incorpora el estadio. Con las mismas mediciones, el Stuff+ es igual en ambos escenarios. Los resultados contextuales pueden variar; no se simula un cambio físico por altitud.</Notice><p>100 es la referencia histórica. Los puntos no son un porcentaje de éxito. La comparación mantiene fija la física del lanzamiento; no estima efectos causales.</p><details><summary>Todos los resultados del modelo</summary><pre>{JSON.stringify(evaluation.results, null, 2)}</pre></details><a className="button" download="evaluacion.json" href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(evaluation, null, 2))}`}>Descargar evaluación ↓</a></> : <p>Revisa el lanzamiento y el estadio, y pulsa <b>Estimar Stuff+</b> para obtener el resultado.</p>}</section><MovementMap run={run} pitch={profile.type} hand={profile.hand} values={values} /><div className="reading-strip">{[['Stuff+', 'La calidad física de la pelota.'], ['Location+', 'El lugar donde llega al plato.'], ['Pitching+', 'Su evaluación combinada.']].map(([title, text]) => <div key={title}><h3>{title}</h3><p>{text}</p></div>)}</div><details className="comparison-reports"><summary>Ver reportes de comparación entre estadios</summary><SavedTable name="profiles" title="Perfiles físicos · Qué revisar para Harp Helú" /><SavedTable name="deltas" title="Diferencias entre escenarios" /><Notice>Los perfiles describen asociaciones por tipo y mano. No demuestran una ventaja causal o universal en Harp Helú.</Notice></details></>;
}
