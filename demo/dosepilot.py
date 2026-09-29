#!/usr/bin/env python3
"""Strict private R13 inventory -> acquisition -> identified-measurement workflow.

No network, source-workbook loading, fitting, dose interpolation or clinical advice.
All hashes authenticate bytes against a caller's trust anchor, not scientific truth.
"""
from __future__ import annotations
import argparse, hashlib, json, math, re, sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
import numpy as np

class ContractError(ValueError):
    pass

def unique(pairs):
    d={}
    for k,v in pairs:
        if k in d: raise ContractError('DUPLICATE_JSON_KEY: '+k)
        d[k]=v
    return d

def raw_hash(b): return hashlib.sha256(b).hexdigest()
def canonical(obj): return json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def identity(x,label):
    if not isinstance(x,str) or not x or x!=x.strip() or any(ord(c)<32 for c in x):
        raise ContractError('INVALID_ID: '+label)
    return x

def exact_keys(d,keys,label):
    if not isinstance(d,dict) or set(d)!=set(keys):
        raise ContractError('SCHEMA_KEYS: '+label)

def load(path):
    b=Path(path).read_bytes()
    try: d=json.loads(b,object_pairs_hook=unique,parse_constant=lambda x: (_ for _ in ()).throw(ContractError('NONFINITE_JSON')))
    except (json.JSONDecodeError,UnicodeDecodeError) as e: raise ContractError('INVALID_JSON') from e
    return d,b

def dose(x):
    if not isinstance(x,str) or x!=x.strip(): raise ContractError('DOSE_MUST_BE_EXACT_DECIMAL_STRING')
    try: d=Decimal(x)
    except InvalidOperation as e: raise ContractError('INVALID_DOSE') from e
    if not d.is_finite() or d<=0: raise ContractError('INVALID_DOSE')
    return d

def write_new(path,obj):
    p=Path(path)
    if p.exists(): raise ContractError('OUTPUT_EXISTS')
    # Construct all bytes before opening a new file. No partial scientific JSON.
    b=json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+'\n'
    with p.open('x',encoding='utf-8') as f: f.write(b)

def load_model(path,expected):
    m,b=load(path)
    if not re.fullmatch('[0-9a-f]{64}',expected or '') or raw_hash(b)!=expected:
        raise ContractError('MODEL_HASH_MISMATCH')
    exact_keys(m,['schema','library_id','target_ids','native_ids','concentrations_nM','owner','plate_A','mean_x','scale_x','mean_y','beta','lambda','provenance'],'model')
    if m['schema']!='von.r13.final.v1' or m['library_id']!='lib1': raise ContractError('UNSUPPORTED_MODEL')
    ids=m['target_ids']; qs=m['native_ids']; ds=m['concentrations_nM']
    if len(ids)!=24 or len(set(ids))!=24 or len(qs)!=64 or len(set(qs))!=64 or len(ds)!=64: raise ContractError('MODEL_DIMENSIONS')
    for x in ids+qs: identity(x,'model axis')
    for x in ds:dose(x)
    if len(m['owner'])!=64 or any(type(x) is not int or x<0 or x>=24 for x in m['owner']): raise ContractError('MODEL_OWNERSHIP')
    if len(m['plate_A'])!=64 or any(type(x) is not int or x not in [0,1] for x in m['plate_A']): raise ContractError('MODEL_PLATES')
    owner=np.asarray(m['owner']); plates=np.asarray(m['plate_A']); counts=np.bincount(owner,minlength=24)
    if (counts==2).sum()!=8 or (counts==3).sum()!=16 or (plates==0).sum()!=32: raise ContractError('MODEL_BUDGET')
    params={}
    for k,shape in [('mean_x',(64,)),('scale_x',(64,)),('mean_y',(24,)),('beta',(64,24))]:
        a=np.asarray(m[k],dtype=float)
        if a.shape!=shape or not np.isfinite(a).all(): raise ContractError('MODEL_ARRAY: '+k)
        params[k]=a
    if (params['scale_x']<.05).any() or m['lambda'] not in [.01,.1,1.,10.]: raise ContractError('MODEL_SCALE_OR_PENALTY')
    mask=owner[:,None]==np.arange(24)[None,:]
    if np.any(params['beta'][~mask]!=0):raise ContractError('NON_OWN_DRUG_COEFFICIENT')
    if len({(int(owner[i]),dose(ds[i])) for i in range(64)})!=64: raise ContractError('DUPLICATE_MODEL_DOSE')
    return m,params,raw_hash(b)

def inventory(obj):
    exact_keys(obj,['schema','library_id','sample_id','run_id','assay_context','plates','wells'],'inventory')
    if obj['schema']!='von.inventory.v1' or obj['library_id']!='lib1': raise ContractError('UNSUPPORTED_LIBRARY')
    if obj['assay_context'] not in ['source_lib1_protocol','external_unvalidated','synthetic']:
        raise ContractError('ASSAY_CONTEXT_REQUIRED')
    identity(obj['sample_id'],'sample'); identity(obj['run_id'],'run')
    exact_keys(obj['plates'],['p1','p2'],'plates')
    a,b=(identity(obj['plates'][p],p) for p in ['p1','p2'])
    if a==b:raise ContractError('DUPLICATE_PLATE_INSTANCE')
    if not isinstance(obj['wells'],list):raise ContractError('INVALID_WELL_LIST')
    physical=set(); bindings={}
    for w in obj['wells']:
        exact_keys(w,['plate','well','drug_id','concentration_nM','unit'],'inventory well')
        if w['plate'] not in ['p1','p2'] or w['unit']!='nM':raise ContractError('PLATE_OR_UNIT')
        if not isinstance(w['well'],str) or not re.fullmatch(r'[A-P](?:[1-9]|1[0-9]|2[0-4])',w['well']): raise ContractError('NONCANONICAL_384_WELL')
        identity(w['drug_id'],'drug'); d=dose(w['concentration_nM'])
        p=(obj['plates'][w['plate']],w['well']); key=(w['plate'],w['drug_id'],d)
        if p in physical:raise ContractError('DUPLICATE_PHYSICAL_WELL')
        if key in bindings:raise ContractError('AMBIGUOUS_DOSE_BINDING')
        physical.add(p);bindings[key]=w
    return bindings

def make_plan(m,mhash,inv,invhash,budget,nonce):
    if type(budget) is not int or budget<64:raise ContractError('INSUFFICIENT_TREATMENT_BUDGET: need 64 plus separate controls')
    identity(nonce,'response-independent allocation nonce')
    bindings=inventory(inv)
    # Choose without response values; the caller commits this nonce before assay reading.
    seed=canonical([mhash,inv['sample_id'],inv['run_id'],nonce])
    orientation='AB'[int(raw_hash(seed)[0],16)%2]
    shift=int(orientation=='B'); out=[]; missing=[]
    for i in range(64):
        plate='p'+str(1+(m['plate_A'][i]^shift));drug=m['target_ids'][m['owner'][i]]
        key=(plate,drug,dose(m['concentrations_nM'][i])); w=bindings.get(key)
        if w is None:
            missing.append({'plate':plate,'drug_id':drug,'concentration_nM':m['concentrations_nM'][i]});continue
        out.append({'position':i,'native_id':m['native_ids'][i],**w,'plate_instance':inv['plates'][plate]})
    if missing:raise ContractError('MISSING_EXACT_DOSE_BINDINGS: '+json.dumps(missing,separators=(',',':')))
    if len({(x['plate_instance'],x['well']) for x in out})!=64:raise ContractError('PHYSICAL_UNION_NOT_64')
    return {'schema':'von.acquisition.v1','model_sha256':mhash,'inventory_sha256':invhash,'library_id':'lib1',
        'sample_id':inv['sample_id'],'run_id':inv['run_id'],'assay_context':inv['assay_context'],
        'allocation_nonce':nonce,'orientation':orientation,'treatment_wells':64,'plate_counts':{'p1':32,'p2':32},
        'controls_included':False,'inventory':inv,'measurements':out,
        'claims':{'clinical_use':False,'independent_validation':False,'calibrated_uncertainty':False,'lab_execution_verified':False}}

def verify_plan(m,mhash,plan):
    inv=plan.get('inventory',{})
    # Bind an embedded copy with canonical hash, not a mutable path or filename.
    expected=make_plan(m,mhash,inv,raw_hash(canonical(inv)),64,plan.get('allocation_nonce'))
    if plan!=expected:raise ContractError('ACQUISITION_RECORD_MISMATCH')
    return expected

def ledger_key(plan):
    return raw_hash(canonical([plan['model_sha256'],plan['library_id'],plan['sample_id'],plan['run_id']]))+'.json'

def commit_plan(plan, directory):
    # This controls repeats inside this workflow, not a dishonest caller's laboratory IDs.
    root=Path(directory)
    if not root.is_dir() or root.is_symlink():raise ContractError('LEDGER_DIRECTORY_REQUIRED')
    entry=root/ledger_key(plan)
    if entry.exists():raise ContractError('PLAN_ALREADY_COMMITTED_FOR_SAMPLE_RUN_MODEL')
    write_new(entry,plan)

def verify_commit(plan,directory):
    root=Path(directory)
    if not root.is_dir() or root.is_symlink():raise ContractError('LEDGER_DIRECTORY_REQUIRED')
    entry=root/ledger_key(plan)
    if not entry.is_file() or entry.is_symlink():raise ContractError('PLAN_NOT_COMMITTED')
    record,_=load(entry)
    if record!=plan:raise ContractError('COMMITTED_PLAN_MISMATCH')

def request_template(plan):
    return {'schema':'von.measurements.v1','plan_sha256':raw_hash(canonical(plan)),
        'sample_id':plan['sample_id'],'run_id':plan['run_id'],'library_id':plan['library_id'],
        'rows':[{**w,'normalized_viability':None} for w in plan['measurements']]}

def predict(m,params,mhash,plan,request):
    verify_plan(m,mhash,plan)
    exact_keys(request,['schema','plan_sha256','sample_id','run_id','library_id','rows'],'measurement request')
    if request['schema']!='von.measurements.v1' or any(request[k]!=plan[k] for k in ['sample_id','run_id','library_id']):raise ContractError('MEASUREMENT_FRAME_MISMATCH')
    if request['plan_sha256']!=raw_hash(canonical(plan)):raise ContractError('PLAN_HASH_MISMATCH')
    if not isinstance(request['rows'],list) or len(request['rows'])!=64:raise ContractError('EXACT_64_ROW_FRAME_REQUIRED: use null for missing values')
    supplied={}
    for r in request['rows']:
        exact_keys(r,[*plan['measurements'][0],'normalized_viability'],'measurement row')
        i=r['position']
        if type(i) is not int or i<0 or i>=64 or i in supplied:raise ContractError('DUPLICATE_OR_UNKNOWN_POSITION')
        if {k:v for k,v in r.items() if k!='normalized_viability'}!=plan['measurements'][i]:raise ContractError('WELL_IDENTITY_MISMATCH')
        v=r['normalized_viability']
        if v is not None and (type(v) not in [int,float] or not math.isfinite(v)):raise ContractError('INVALID_NORMALIZED_VIABILITY: position '+str(i))
        supplied[i]=v
    paid=np.asarray([np.nan if supplied[i] is None else supplied[i] for i in range(64)],dtype=float)
    valid=np.isfinite(paid);owner=np.asarray(m['owner']);preds=[]
    # For complete vectors preserve the exact original batched NumPy computation.
    complete=None
    if valid.all():
        with np.errstate(over='raise',invalid='raise'):
            complete=(params['mean_y']+((paid[None,:]-params['mean_x'])/params['scale_x'])@params['beta'])[0]
    for j,drug in enumerate(m['target_ids']):
        cols=np.flatnonzero(owner==j); absent=[int(i) for i in cols if not valid[i]]
        if absent:
            value=None;status='ABSTAIN_MISSING_OWN_INPUTS'
        else:
            with np.errstate(over='raise',invalid='raise'):
                value=float(complete[j]) if complete is not None else float(params['mean_y'][j]+((paid[cols]-params['mean_x'][cols])/params['scale_x'][cols])@params['beta'][cols,j])
            if not math.isfinite(value):raise ContractError('NONFINITE_PREDICTION')
            status='PREDICTED_UNVALIDATED'
        preds.append({'drug_id':drug,'normalized_log_dose_auc':value,'status':status,'missing_positions':absent})
    n=sum(x['normalized_log_dose_auc'] is not None for x in preds)
    return {'schema':'von.prediction.v1','model_sha256':mhash,'plan_sha256':request['plan_sha256'],
        'measurement_request_sha256':raw_hash(canonical(request)),'sample_id':plan['sample_id'],'run_id':plan['run_id'],
        'orientation':plan['orientation'],'treatment_wells_planned':64,'observed_wells':int(valid.sum()),
        'output_status':'COMPLETE' if n==24 else 'PARTIAL_ABSTENTION','predicted_targets':n,'total_targets':24,
        'predictions':preds,'claims':plan['claims'],
        'warning':'Research-only. No independent validation, calibrated uncertainty or clinical interpretation. Controls remain additional. Missing inputs are not imputed.'}

def main():
    a=argparse.ArgumentParser(description=__doc__);s=a.add_subparsers(dest='command',required=True)
    for name in ['plan','predict']:
        q=s.add_parser(name);q.add_argument('--model',required=True);q.add_argument('--model-sha256',required=True);q.add_argument('--output',required=True);q.add_argument('--ledger',required=True)
        if name=='plan':q.add_argument('--inventory',required=True);q.add_argument('--budget',type=int,required=True);q.add_argument('--nonce',required=True);q.add_argument('--template',required=True)
        else:q.add_argument('--plan',required=True);q.add_argument('--measurements',required=True)
    args=a.parse_args()
    try:
        m,params,h=load_model(args.model,args.model_sha256)
        if Path(args.output).exists():raise ContractError('OUTPUT_EXISTS')
        if args.command=='plan':
            if Path(args.template).exists() or Path(args.template).resolve()==Path(args.output).resolve():raise ContractError('TEMPLATE_OUTPUT_CONFLICT')
            inv,_=load(args.inventory);p=make_plan(m,h,inv,raw_hash(canonical(inv)),args.budget,args.nonce)
            commit_plan(p,args.ledger);write_new(args.output,p);write_new(args.template,request_template(p));result={'status':'PLANNED','orientation':p['orientation'],'wells':64,'model_sha256':h}
        else:
            p,_=load(args.plan);verify_commit(p,args.ledger);r,_=load(args.measurements);result=predict(m,params,h,p,r);write_new(args.output,result)
            result={k:result[k] for k in ['output_status','predicted_targets','observed_wells','model_sha256']}
        print(json.dumps(result,sort_keys=True));return 0
    except (ValueError,OSError,FloatingPointError,KeyError,TypeError) as e:
        print(json.dumps({'status':'REJECTED','reason':str(e)}),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
