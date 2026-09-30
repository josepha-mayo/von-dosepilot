from __future__ import annotations
import hashlib, json, math
from itertools import combinations
from pathlib import Path
import numpy as np

SOURCE_SHA='f9a9a51fd77ae1a5b19ad71fc236ce446223b3c2fcc66631ab304ab69bec78f0'
DRUGS=('5-FU','Gef','Oxa','SN-38')
DOSE_LABELS={
 '5-FU':('0.5','1.1','2.5','5.5','12.2','27.0','60.0'),
 'Gef':('0.01','0.04','0.1','0.4','1.1','3.3','10.0'),
 'Oxa':('0.5','1.1','2.5','5.5','12.2','27.0','60.0'),
 'SN-38':('0.1','0.2','0.4','0.7','1.4','2.6','5.0')}
DOSES=np.asarray([[float(x) for x in DOSE_LABELS[d]] for d in DRUGS])
DEV_IDS=('O02','O03','O04','O09','O10','O12','O16','O18','O21','O23','O24','O28','O29')
CONFIRM_PAIRS=(('O01','F01'),('O05','F05'),('O06','F06'),('O07','F07'),
 ('O11','F11'),('O13','F13'),('O14','F14'),('O15','F15'),('O17','F17'),
 ('O19','F19'),('O20','F20'),('O22','F22'),('O25','F25'),('O26','F26'),('O27','F27'))
CONFIRM_MAP=dict(CONFIRM_PAIRS)
LAMBDAS=(.01,.1,1.,10.)
ALPHA=.1; UPGRADES=3; BUDGET=11

def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def dump(path,value):
    with Path(path).open('x') as f:
        json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')

def _decode_metadata(line,lineno):
    rest=line;fields=[]
    for _ in range(7):
        left,sep,rest=rest.partition(b'\t')
        if not sep:raise ValueError(f'row {lineno}: malformed metadata')
        fields.append(left.decode('utf-8'))
    return fields,rest

def load_scope(path,scope):
    """Decode RLU only for the explicitly allowed rows in one scope."""
    path=Path(path)
    if sha(path)!=SOURCE_SHA:raise ValueError('Source file identity changed')
    if scope not in ('development','confirmation'):raise ValueError('Unknown access scope')
    groups={};decoded=0;selected_lines=0;invalid_rlu=0
    with path.open('rb') as f:
        f.readline()
        for lineno,line in enumerate(f,2):
            fields,rest=_decode_metadata(line,lineno)
            _,organoid,context,fibroblast,drug,conc,rep=fields
            if drug not in DRUGS or conc not in set(DOSE_LABELS.get(drug,()))|{'DMSO'}:continue
            if scope=='development':
                allowed=organoid in DEV_IDS and context=='Monoculture' and fibroblast==''
                condition='mono'
            else:
                allowed=organoid in CONFIRM_MAP and (
                    (context=='Monoculture' and fibroblast=='') or
                    (context=='Coculture' and fibroblast==CONFIRM_MAP[organoid]))
                condition='mono' if context=='Monoculture' else 'co'
            if not allowed:continue
            selected_lines+=1
            raw,sep,_=rest.partition(b'\t')
            if not sep:raise ValueError(f'row {lineno}: missing RLU field')
            decoded+=1
            text=raw.decode('utf-8').strip()
            try:value=float(text)
            except ValueError:
                invalid_rlu+=1;value=np.nan
            if not np.isfinite(value) or value<0:
                invalid_rlu+=int(np.isfinite(value) and value<0);value=np.nan
            groups.setdefault((organoid,condition,drug,conc),[]).append(value)
    return _tensor_from_groups(groups,scope),{'scope':scope,'selected_rows':selected_lines,
      'rlu_fields_decoded':decoded,'invalid_or_nonfinite_rlu':invalid_rlu,'source_sha256':SOURCE_SHA}

def _tensor_from_groups(groups,scope):
    ids=list(DEV_IDS) if scope=='development' else [x[0] for x in CONFIRM_PAIRS]
    conditions=('mono',) if scope=='development' else ('co','mono')
    tensors={}
    replicate_audit={}
    for condition in conditions:
        values=np.empty((len(ids),len(DRUGS),7),float)
        for i,o in enumerate(ids):
            for j,d in enumerate(DRUGS):
                control=np.asarray(groups.get((o,condition,d,'DMSO'),[]),float)
                control=control[np.isfinite(control)&(control>=0)]
                if len(control)<2 or control.mean()<=0:
                    raise ValueError(f'{o}/{condition}/{d}: insufficient DMSO RLU')
                denom=float(control.mean())
                replicate_audit[f'{o}|{condition}|{d}|DMSO']=len(control)
                for k,label in enumerate(DOSE_LABELS[d]):
                    a=np.asarray(groups.get((o,condition,d,label),[]),float)
                    a=a[np.isfinite(a)&(a>=0)]
                    if len(a)<2:raise ValueError(f'{o}/{condition}/{d}/{label}: <2 finite RLU')
                    values[i,j,k]=float(a.mean()/denom)
                    replicate_audit[f'{o}|{condition}|{d}|{label}']=len(a)
        if not np.isfinite(values).all():raise ValueError('Nonfinite normalized viability')
        tensors[condition]=values
    return {'ids':np.asarray(ids,dtype=str),'values':tensors,'replicate_counts':replicate_audit}

def auc_full(values):
    values=np.asarray(values,float);out=np.empty(values.shape[:2])
    if values.ndim!=3 or values.shape[1:]!=(4,7):raise ValueError('Expected n x 4 x 7')
    for j in range(4):
        x=np.log(DOSES[j])
        out[:,j]=np.sum(np.diff(x)*(values[:,j,:-1]+values[:,j,1:])/2,axis=1)/(x[-1]-x[0])
    return out

def context(x,y):
    x=np.asarray(x,float);y=np.asarray(y,float)
    mx=x.mean(0);my=y.mean(0);sx=np.maximum(x.std(0),.05)
    z=(x-mx)/sx;cy=y-my
    return {'mx':mx,'my':my,'sx':sx,'cxx':z.T@z/len(x),'cxy':z.T@cy/len(x),
            'cyy':cy.T@cy/len(x)}

def subset_risk(x,y):
    y=np.asarray(y,float).reshape(-1,1);c=context(x,y);cross=c['cxy'][:,0]
    return float(c['cyy'][0,0]-cross@np.linalg.solve(c['cxx']+ALPHA*np.eye(x.shape[1]),cross))

def learned_plan(values,y):
    choices=[]
    for j,d in enumerate(DRUGS):
        best={}
        for size in (2,3):
            opts=[(subset_risk(values[:,j,list(s)],y[:,j]),s) for s in combinations(range(7),size)]
            best[size]=min(opts,key=lambda q:(q[0],q[1]))
        choices.append({'drug':d,'best2':list(best[2][1]),'best3':list(best[3][1]),
          'risk2':best[2][0],'risk3':best[3][0],'gain':best[2][0]-best[3][0]})
    upgraded={DRUGS.index(q['drug']) for q in sorted(choices,key=lambda q:(-q['gain'],q['drug']))[:UPGRADES]}
    selected=[];owner=[]
    for j,q in enumerate(choices):
        s=q['best3'] if j in upgraded else q['best2']
        selected.extend((j,k) for k in s);owner.extend([j]*len(s))
    if len(selected)!=BUDGET:raise AssertionError('Budget mismatch')
    return {'choices':choices,'upgraded':[DRUGS[j] for j in sorted(upgraded)],
            'selected':[list(q) for q in selected],'owner':owner,'budget':BUDGET}

def feature_matrix(values,plan):
    return np.column_stack([values[:,j,k] for j,k in plan['selected']])

def fit_model(values,y,plan,lam):
    x=feature_matrix(values,plan);c=context(x,y);owner=np.asarray(plan['owner'])
    beta=np.zeros((BUDGET,4))
    for j in range(4):
        cols=np.flatnonzero(owner==j)
        beta[cols,j]=np.linalg.solve(c['cxx'][np.ix_(cols,cols)]+lam*np.eye(len(cols)),c['cxy'][cols,j])
    return {'mx':c['mx'],'sx':c['sx'],'my':c['my'],'beta':beta,'lambda':float(lam)}

def predict_model(values,plan,model):
    x=feature_matrix(values,plan)
    out=model['my']+((x-model['mx'])/model['sx'])@model['beta']
    if not np.isfinite(out).all():raise ValueError('Nonfinite prediction')
    return out

def interp_one(curve,j,indices):
    full=np.log(DOSES[j]);sel=full[indices]
    y=np.interp(full,sel,curve[indices])
    return float(np.sum(np.diff(full)*(y[:-1]+y[1:])/2)/(full[-1]-full[0]))

def interp_plan(values,y):
    choices=[]
    for j,d in enumerate(DRUGS):
        best={}
        for size in (2,3):
            opts=[]
            for s in combinations(range(7),size):
                ix=list(s);pred=np.asarray([interp_one(values[i,j],j,ix) for i in range(len(values))])
                opts.append((float(np.mean((pred-y[:,j])**2)),s))
            best[size]=min(opts,key=lambda q:(q[0],q[1]))
        choices.append({'drug':d,'best2':list(best[2][1]),'best3':list(best[3][1]),
          'risk2':best[2][0],'risk3':best[3][0],'gain':best[2][0]-best[3][0]})
    upgraded={DRUGS.index(q['drug']) for q in sorted(choices,key=lambda q:(-q['gain'],q['drug']))[:UPGRADES]}
    return {'choices':choices,'upgraded':[DRUGS[j] for j in sorted(upgraded)],'budget':BUDGET}

def interp_predict(values,plan):
    out=np.empty((len(values),4));up=set(plan['upgraded'])
    for j,d in enumerate(DRUGS):
        q=plan['choices'][j];ix=q['best3'] if d in up else q['best2']
        out[:,j]=[interp_one(values[i,j],j,ix) for i in range(len(values))]
    return out

def mse(y,p):return float(np.mean((np.asarray(p)-np.asarray(y))**2))
def per_row_loss(y,p):return ((np.asarray(p)-np.asarray(y))**2).mean(1)
def per_target_mse(y,p):return ((np.asarray(p)-np.asarray(y))**2).mean(0)

def model_to_npz(path,model):
    np.savez_compressed(path,mx=model['mx'],sx=model['sx'],my=model['my'],
                       beta=model['beta'],lambda_value=np.asarray(model['lambda']))

def model_from_npz(path):
    with np.load(path,allow_pickle=False) as z:
        return {'mx':z['mx'].copy(),'sx':z['sx'].copy(),'my':z['my'].copy(),
                'beta':z['beta'].copy(),'lambda':float(z['lambda_value'])}