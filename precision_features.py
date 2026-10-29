"""Context-only predictors and count-value targets; no changes to physical Stuff+."""
from collections import deque
import uuid

import numpy as np
import pandas as pd

FLIGHT = ['ZoneSpeed', 'ZoneTime', 'SpeedDrop', 'VertRelAngle', 'HorzRelAngle', 'VertApprAngle', 'HorzApprAngle']
SEQUENCE = ['previous_velocity', 'previous_hb', 'previous_ivb', 'velocity_change',
            'hb_change', 'ivb_change', 'observed_workload', 'previous_available']
RECENT = ['recent_velocity', 'recent_hb', 'recent_ivb', 'recent_pitches', 'recent_available']
FORBIDDEN = {'ExitSpeed', 'Angle', 'Direction', 'Distance', 'PitchCall', 'play_result',
             'OutsOnPlay', 'RunsScored', 'PitchUID', 'game_anon_id', 'pitcher_anon_id',
             'batter_anon_id', 'catcher_anon_id', 'is_swing', 'is_whiff', 'out_within_pa'}


def timestamp(identifier):
    try:
        value = uuid.UUID(str(identifier))
        return value.time if value.version == 1 else -1
    except (ValueError, TypeError, AttributeError):
        return -1


def past_context(raw, history_mask):
    """Previous observed pitch and last five eligible, strictly earlier games.

    history_mask is supplied by each training fold. Recent measurements never
    read held-out games/pitchers/parks, outcomes or the current game's aggregate.
    Workload counts observed pitches, not a guaranteed complete game workload.
    Ambiguous timestamps disable sequence/history rather than choosing an order.
    """
    frame = raw.copy().reset_index(drop=True)
    if len(history_mask) != len(frame):
        raise ValueError('History mask must align with rows')
    frame['_fit'] = np.asarray(history_mask, dtype=bool)
    frame['_row'] = np.arange(len(frame))
    frame['_time'] = frame.PitchUID.map(timestamp)
    group = ['year', 'game_anon_id']
    bad = frame._time.lt(0) | frame.duplicated(group + ['_time'], keep=False)
    frame['_ambiguous'] = bad.groupby([frame[c] for c in group]).transform('any')
    frame = frame.sort_values(group + ['_time', '_row'])
    grouped = frame.groupby(group + ['pitcher_anon_id'], dropna=False)
    valid = ~frame._ambiguous & frame.pitcher_anon_id.notna()
    frame['observed_workload'] = grouped.cumcount().where(valid)
    for src, previous, change in [('RelSpeed', 'previous_velocity', 'velocity_change'),
                                   ('HorzBreak', 'previous_hb', 'hb_change'),
                                   ('InducedVertBreak', 'previous_ivb', 'ivb_change')]:
        frame[previous] = grouped[src].shift().where(valid)
        frame[change] = pd.to_numeric(frame[src], errors='coerce') - frame[previous]
    frame['previous_available'] = frame.previous_velocity.notna().astype(float)
    for c in RECENT:
        frame[c] = np.nan if c != 'recent_available' else 0.
    # Query one row per pitcher/type/game; update history only after querying.
    keys = ['pitcher_anon_id', 'AutoPitchType', *group]
    events = frame.loc[valid].groupby(keys, dropna=False).agg(_time=('_time', 'min')).reset_index()
    refs = frame.loc[valid & frame._fit].groupby(keys).agg(
        count=('RelSpeed', 'count'), velocity=('RelSpeed', 'sum'), hb=('HorzBreak', 'sum'), ivb=('InducedVertBreak', 'sum'))
    summaries = []
    for _, events_for_pitch in events.groupby(['pitcher_anon_id', 'AutoPitchType'], dropna=False):
        queue = deque(maxlen=5)
        # A timestamp tie cannot consume measurements from a simultaneous game.
        for _, batch in events_for_pitch.groupby('_time', sort=True):
            for event in batch.itertuples(index=False, name=None):
                identity = tuple(event[:len(keys)])
                total = sum(x[0] for x in queue)
                values = {key: val for key, val in zip(keys, identity)}
                values.update(recent_pitches=float(total), recent_available=float(total >= 10))
                for dest, pos in [('recent_velocity', 1), ('recent_hb', 2), ('recent_ivb', 3)]:
                    values[dest] = sum(x[pos] for x in queue) / total if total >= 10 else np.nan
                summaries.append(values)
            for event in batch.itertuples(index=False, name=None):
                identity = tuple(event[:len(keys)])
                if identity in refs.index:
                    r = refs.loc[identity]
                    queue.append((float(r['count']), float(r.velocity), float(r.hb), float(r.ivb)))
    if summaries:
        found = frame[keys + ['_row']].merge(pd.DataFrame(summaries), on=keys, how='left', validate='many_to_one').set_index('_row')
        for col in RECENT:
            frame[col] = frame._row.map(found[col]).fillna(0.) if col.endswith('available') else frame._row.map(found[col])
    return frame.sort_values('_row')[SEQUENCE + RECENT].reset_index(drop=True)


def fit_count_values(raw, pa, smoothing=50.):
    """Fit expected terminal proxy by count on complete TRAINING turns only.

    Each PA contributes once per count. Caller must supply training rows only;
    incomplete PA or PA with rows outside that fold are rejected.
    """
    from completar_targets_pa import TERMINAL
    import entrenar_stuff_plus_v5 as v5
    labels = pa.loc[pa.out_within_pa.notna(), ['PitchUID', 'pa_id']]
    data = raw.merge(labels, on='PitchUID', how='inner', validate='one_to_one')
    expected = labels.groupby('pa_id').size()
    complete = data.groupby('pa_id').size().eq(expected)
    data = data.loc[data.pa_id.isin(complete[complete].index)].copy()
    terminal = data.loc[data.play_result.isin(TERMINAL)].copy()
    unique = terminal.groupby('pa_id').size()
    terminal = terminal.loc[terminal.pa_id.isin(unique[unique.eq(1)].index)]
    if terminal.empty:
        raise ValueError('No complete training turns to fit count values')
    terminal['terminal_value'] = v5.observed_run_value(terminal)
    data = data.merge(terminal[['pa_id', 'terminal_value']], on='pa_id', validate='many_to_one')
    prior = float(terminal.terminal_value.mean())
    table = data.drop_duplicates(['pa_id', 'Balls', 'Strikes']).groupby(['Balls', 'Strikes']).terminal_value.agg(['sum', 'count'])
    return {'prior': prior, 'smoothing': smoothing, 'training_pa': len(terminal),
            'values': {f'{int(b)}-{int(s)}': float((r['sum']+smoothing*prior)/(r['count']+smoothing)) for (b,s),r in table.iterrows()}}


def count_transition_target(raw, values):
    from completar_targets_pa import TERMINAL
    import entrenar_stuff_plus_v5 as v5
    current = (raw.Balls.astype(int).astype(str) + '-' + raw.Strikes.astype(int).astype(str)).map(values['values']).fillna(values['prior'])
    balls, strikes = raw.Balls.copy(), raw.Strikes.copy()
    balls += raw.PitchCall.isin(['BallCalled', 'BallinDirt']).astype(int)
    strikes += raw.PitchCall.isin(['StrikeCalled', 'StrikeSwinging']).astype(int)
    strikes += (raw.PitchCall.astype(str).str.startswith('Foul') & raw.Strikes.lt(2)).astype(int)
    after = (balls.astype(int).astype(str) + '-' + strikes.astype(int).astype(str)).map(values['values']).fillna(values['prior'])
    terminal = raw.play_result.isin(TERMINAL)
    after = after.where(~terminal, v5.observed_run_value(raw))
    valid = terminal | (balls.between(0,3) & strikes.between(0,2))
    return (after-current).where(valid).rename('count_transition_value')
