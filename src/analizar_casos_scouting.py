"""Tres casos descriptivos reproducibles para la conversacion deportiva."""
from pathlib import Path
import pandas as pd
from analizar_perfiles_estadios import read_parquet, cluster_mean_interval

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/v9_estadios'


def main():
    frame=read_parquet(ROOT/'stuff_plus_output_v9_estadios/escenarios_harp_helu_2026.parquet')
    frame=frame.dropna(subset=['pitcher_anon_id'])
    summary=frame.groupby('pitcher_anon_id').agg(n=('PitchUID','size'), games=('game_anon_id','nunique'),
        pitch_types=('AutoPitchType','nunique'), pitching_plus=('pitching_plus','mean'),
        p_whiff=('p_whiff','mean'), p_hr=('p_home_run_per_pitch','mean'))
    enough=summary.loc[summary.n.ge(300)&summary.games.ge(5)&summary.pitch_types.ge(2)]
    if len(enough)<2:
        raise ValueError('Sin muestra para casos comparables')
    choices=[('Revisar repertorio favorable', enough.pitching_plus.idxmax(),
        'Revisar video, calidad de ubicacion y consistencia de cada tipo. Confirmar salud y rol antes de priorizar al prospecto.'),
        ('Revisar ubicacion y riesgo', enough.pitching_plus.idxmin(),
        'Revisar ubicacion y distribucion de lanzamientos; contrastar el riesgo de contacto con video. No descartar al pitcher solo por este promedio.')]
    small=summary.loc[summary.n.lt(50)]
    if not small.empty:
        choices.append(('Pedir mas muestra',small.n.idxmax(),
            'Solicitar mas juegos y mediciones completas antes de comparar talento o proponer cambios de uso.'))
    records=[]
    for label,identifier,action in choices:
        item=summary.loc[identifier]
        rows=frame.loc[frame.pitcher_anon_id.eq(identifier)]
        mean,low,high=cluster_mean_interval(rows.pitching_plus,rows.game_anon_id)
        types=rows.AutoPitchType.value_counts(normalize=True)
        records.append(dict(caso=label,pitcher_anon_id=identifier,n=int(item.n),games=int(item.games),
            pitching_plus=mean,ci_low=low,ci_high=high,p_whiff=float(item.p_whiff),p_hr=float(item.p_hr),
            repertorio='; '.join(f'{name}: {value:.0%}' for name,value in types.items()),accion=action,
            alcance='Escenario Harp con fisica medida fija; caso elegido despues de evaluar; no validacion de talento'))
    pd.DataFrame(records).to_csv(REPORT/'casos_scouting.csv',index=False)
    print(f'Casos guardados: {len(records)}',flush=True)


if __name__=='__main__':
    main()
