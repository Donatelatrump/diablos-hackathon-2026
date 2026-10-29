"""A joint event distribution and conditional heads; no changes to v9 scores."""
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import softmax

EVENTS=['ball','called_strike','whiff','foul','in_play','hbp']
EVENT_MAP={'BallCalled':'ball','BallinDirt':'ball','BallIntentional':'ball','AutomaticBall':'ball',
           'StrikeCalled':'called_strike','AutomaticStrike':'called_strike','StrikeSwinging':'whiff',
           'FoulBall':'foul','FoulBallNotFieldable':'foul','FoulBallFieldable':'foul','InPlay':'in_play','HitByPitch':'hbp'}


def event_labels(rows):
    return rows.PitchCall.map(EVENT_MAP).map({v:i for i,v in enumerate(EVENTS)})


def temperature_probabilities(probabilities,temperature):
    p=np.asarray(probabilities,dtype=float)
    return softmax(np.log(np.clip(p,1e-15,1))/float(temperature),axis=1)


def fit_temperature(probabilities,labels):
    p=np.asarray(probabilities,dtype=float);y=np.asarray(labels,dtype=int)
    def loss(t):
        q=temperature_probabilities(p,t)
        return -np.log(np.clip(q[np.arange(len(y)),y],1e-15,1)).mean()
    solution=minimize_scalar(loss,bounds=(.5,3.),method='bounded')
    return float(solution.x)


def joint_predictions(events,hr_given_inplay,contact):
    """All probabilities share an explicitly consistent event denominator."""
    p=np.asarray(events,dtype=float);c=np.asarray(contact,dtype=float);h=np.asarray(hr_given_inplay,dtype=float)
    if p.ndim!=2 or p.shape[1]!=6 or c.shape!=(len(p),3) or h.shape!=(len(p),):
        raise ValueError('Unexpected event/head dimensions')
    if not all(np.isfinite(x).all() for x in [p,c,h]):
        raise ValueError('Nonfinite predictions')
    if np.any(p<0) or np.any(c<0) or np.any(h<0) or np.any(h>1) or not np.allclose(p.sum(axis=1),1) or not np.allclose(c.sum(axis=1),1):
        raise ValueError('Invalid probability distribution')
    swing=p[:,2]+p[:,3]+p[:,4]
    conditional=np.divide(p[:,2],swing,out=np.zeros(len(p)),where=swing>0)
    return pd.DataFrame({'p_whiff':p[:,2],'p_whiff_given_swing':conditional,'p_ball_in_play':p[:,4],
        'p_called_strike':p[:,1],'p_home_run_per_pitch':p[:,4]*h,
        'p_weak_contact':c[:,0],'p_hard_contact':c[:,2],'p_swing':swing})


def fit_event_values(rows,smoothing=50.):
    """Non-inplay proxy values estimated only from the caller's fit rows."""
    rows=rows.copy();rows['_event']=event_labels(rows)
    global_mean=float(rows.run_value_proxy.mean())
    priors=rows.groupby('_event').run_value_proxy.mean().to_dict()
    table=rows.groupby(['Balls','Strikes','_event']).run_value_proxy.agg(['sum','count'])
    values={}
    for b in range(4):
        for s in range(3):
            vector=[]
            for event in range(6):
                prior=priors.get(event,global_mean)
                if (b,s,event) in table.index:
                    r=table.loc[(b,s,event)]
                    vector.append(float((r['sum']+smoothing*prior)/(r['count']+smoothing)))
                else:vector.append(float(prior))
            values[f'{b}-{s}']=vector
    return values


def expected_legacy_value(events,rows,contact_value,event_values):
    keys=rows.Balls.astype(int).astype(str)+'-'+rows.Strikes.astype(int).astype(str)
    values=np.asarray(keys.map(event_values).tolist(),dtype=float)
    values[:,4]=np.asarray(contact_value,dtype=float)
    return (np.asarray(events)*values).sum(axis=1)
