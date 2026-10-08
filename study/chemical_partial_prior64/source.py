"""Compound-matched correlation on measured overlapping concentrations.
Uncovered coordinates retain an explicit Gaussian conditional prior; they are
NOT claimed as external measurements. No organoid responses are parsed here.
"""
from pathlib import Path
import csv,hashlib,importlib.util,json,datetime,argparse
import numpy as np
P=Path(__file__).resolve().parent.parent/'chemical_dose_correlation64/source.py'
spec=importlib.util.spec_from_file_location('strict_chemical_metadata_helpers',P);strict=importlib.util.module_from_spec(spec);spec.loader.exec_module(strict)
MIN_CELLS=20
CORRELATION_RIDGE=.1

def complete_correlation(pooled,covered,observed):
    pooled=np.asarray(pooled,float);covered=np.asarray(covered,int);observed=np.asarray(observed,float);d=len(pooled)
    if pooled.shape!=(d,d) or observed.shape!=(len(covered),len(covered)) or len(np.unique(covered))!=len(covered) or covered.min()<0 or covered.max()>=d:
        raise ValueError('invalid correlation/index dimensions')
    if not np.isfinite(pooled).all() or not np.isfinite(observed).all():raise ValueError('nonfinite covariance')
    prior=.9*pooled+.1*np.eye(d);block=.9*observed+.1*np.eye(len(covered))
    np.linalg.cholesky(prior);np.linalg.cholesky(block)
    other=np.setdiff1d(np.arange(d),covered)
    full=np.zeros_like(prior);full[np.ix_(covered,covered)]=block
    if len(other):
        regression=np.linalg.solve(prior[np.ix_(covered,covered)],prior[np.ix_(covered,other)]).T
        conditional=prior[np.ix_(other,other)]-regression@prior[np.ix_(covered,other)]
        full[np.ix_(other,covered)]=regression@block;full[np.ix_(covered,other)]=block@regression.T
        full[np.ix_(other,other)]=conditional+regression@block@regression.T
    full=(full+full.T)/2;sd=np.sqrt(np.diag(full));result=full/(sd[:,None]*sd[None,:]);np.linalg.cholesky(result)
    return result

def partial_bank(values,nsc,cells,high,candidates,doses_nm,pooled,min_cells=MIN_CELLS):
    logs=strict.log_molar(doses_nm);matched=np.isin(nsc,candidates);choices=[]
    for start in range(len(logs)):
        for end in range(start+2,len(logs)+1):
            mask=matched&(logs[start]>=high-4-1e-8)&(logs[end-1]<=high+1e-8)
            n_cells=len(np.unique(cells[mask]))
            if n_cells>=min_cells:choices.append((-(end-start),start,end,mask,n_cells))
    regularized=.9*pooled+.1*np.eye(len(logs))
    if not choices:return regularized,{'status':'POOLED_FALLBACK','covered_indices':[],'matched_cells':0,'matched_curve_groups':0}
    _,start,end,mask,n_cells=min(choices,key=lambda r:(r[0],r[1],r[2]))
    ix=np.arange(start,end);rows=np.flatnonzero(mask)
    interpolated=np.stack([np.interp(logs[ix],np.arange(high[i]-4,high[i]+.5),values[i]) for i in rows])
    w=strict.equal_cell_compound_weights(cells[rows],nsc[rows]);centered=interpolated-w@interpolated;cov=centered.T@(w[:,None]*centered)
    sd=np.sqrt(np.maximum(np.diag(cov),0))
    if sd.min()<=1e-6:return regularized,{'status':'POOLED_FALLBACK_LOW_SOURCE_VARIANCE','covered_indices':ix.tolist(),'matched_cells':n_cells,'matched_curve_groups':len(rows)}
    corr=cov/(sd[:,None]*sd[None,:]);corr=(corr+corr.T)/2
    result=complete_correlation(pooled,ix,corr)
    return result,{'status':'PARTIAL_CHEMICAL_DOSE_TRANSFER','covered_indices':ix.tolist(),'uncovered_indices':np.setdiff1d(np.arange(len(logs)),ix).tolist(),
       'matched_cells':n_cells,'matched_curve_groups':len(rows),'covered_log_molar_range':[float(logs[start]),float(logs[end-1])],
       'full_log_molar_range':[float(logs[0]),float(logs[-1])],'max_difference_from_regularized_pooled':float(np.max(np.abs(result-regularized))),
       'source_response_extrapolation':False,'uncovered_region_uses_gaussian_conditional_prior':True}

def prepare(source,identity,curves,out):
    source,identity,curves,out=map(Path,(source,identity,curves,out));auditpath=out.with_name('PARTIAL_BANK_AUDIT.json')
    if out.exists() or auditpath.exists():raise ValueError('existing bank not overwritten')
    if strict.sha(source)!=strict.SOURCE_SHA or strict.sha(curves)!=strict.CURVES_SHA:raise ValueError('source hash')
    identification=json.loads(identity.read_text(encoding='utf-8'))
    with np.load(source,allow_pickle=False) as z:values=z['values'];weights=z['weights'];nsc=z['nsc'];cells=z['cell_keys'];high=z['log_high']
    pooled5=strict.base.external_covariance(values,weights);grids={r['drug']:set() for r in identification['rows']}
    with curves.open(encoding='utf-8',newline='') as f:
        for row in csv.DictReader(f):
            if row['library_id']!='lib1' or row['drug_id'] not in grids:raise ValueError('metadata scope')
            grids[row['drug_id']].add(float(row['dose_nM']))
    bank={'pooled_covariance5':pooled5};names=[];records=[]
    for j,row in enumerate(identification['rows']):
        name=row['drug'];names.append(name);doses=np.array(sorted(grids[name]));logs=strict.log_molar(doses)
        generic=strict.base.relative_correlation(pooled5,(logs-logs[0])/(logs[-1]-logs[0]))
        candidates=sorted({r['nsc'] for r in row.get('source_confirmation_checks',[]) if r['exact_cid_match'] and r['standardized_cids']==[row.get('compound_cid')]},key=int)
        matched,rec=partial_bank(values,nsc,cells,high,candidates,doses,generic)
        bank[f'pooled_{j}']=.9*generic+.1*np.eye(len(doses));bank[f'partial_{j}']=matched;bank[f'doses_nM_{j}']=doses
        records.append(dict(rec,drug=name,candidates=candidates))
    bank['drug_names']=np.array(names);out.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(out,**bank)
    receipt={'schema':'dosepilot.chemical_partial_prior64.source_bank.v1','status':'SOURCE_ONLY_BANK_READY','source_cache_sha256':strict.SOURCE_SHA,
       'identity_audit_sha256':strict.sha(identity),'bank_sha256':strict.sha(out),'supported_targets':sum(r['status']=='PARTIAL_CHEMICAL_DOSE_TRANSFER' for r in records),
       'records':records,'min_cells':MIN_CELLS,'correlation_ridge':CORRELATION_RIDGE,'organoid_response_values_parsed':False,
       'organoid_model_fitted':False,'external_response_extrapolation_used':False,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with auditpath.open('x',encoding='utf-8',newline='\n') as f:json.dump(receipt,f,indent=2);f.write('\n')
    print(json.dumps(receipt,indent=2),flush=True);return receipt
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--identity',type=Path,required=True);ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();prepare(a.source,a.identity,a.curves,a.out)
