"""External CROSS-drug covariance across identical cell-line units.
Only audited exact compounds and measured overlapping absolute concentrations
are used. No organoid outcomes or external response means are transferred.
"""
from pathlib import Path
import argparse,datetime,hashlib,json
import numpy as np
SOURCE_SHA='53aae154d310256d77ddbc9c9d6ddab461235496e12009a23105620c0181b66c'
MIN_COMMON_CELLS=20
CORRELATION_SHRINKAGE=.5

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def weighted_auc(log_doses,responses):
    d=np.asarray(log_doses,float);y=np.asarray(responses,float)
    if d.ndim!=1 or len(d)<2 or np.any(np.diff(d)<=0) or y.shape[-1]!=len(d) or not np.isfinite(y).all():raise ValueError('finite ordered dose/response vectors required')
    return np.sum((y[...,1:]+y[...,:-1])*np.diff(d),axis=-1)/(2*(d[-1]-d[0]))

def output_prior(values,nsc,cells,high,records,minimum=MIN_COMMON_CELLS):
    v=np.asarray(values,float);nsc=np.asarray(nsc,str);cells=np.asarray(cells,str);high=np.asarray(high,float)
    if v.shape!=(len(nsc),5) or cells.shape!=nsc.shape or high.shape!=nsc.shape or not np.isfinite(v).all():raise ValueError('aligned external five-dose profiles required')
    selected=[];summaries=[];coverage=[]
    for j,r in enumerate(records):
        if r['status']!='PARTIAL_CHEMICAL_DOSE_TRANSFER':continue
        lo,hi=r['covered_log_molar_range'];use=np.isin(nsc,r['candidates'])&(lo>=high-4-1e-8)&(hi<=high+1e-8)
        per_cell={}
        for cell in sorted(set(cells[use])):
            rows=np.flatnonzero(use&(cells==cell));per_compound=[]
            for compound in np.unique(nsc[rows]):
                group=rows[nsc[rows]==compound];scores=[]
                for k in group:
                    grid=np.arange(high[k]-4,high[k]+.5)
                    nodes=np.r_[lo,grid[(grid>lo)&(grid<hi)],hi]
                    scores.append(float(weighted_auc(nodes,np.interp(nodes,grid,v[k]))))
                per_compound.append(float(np.mean(scores)))
            per_cell[str(cell)]=float(np.mean(per_compound))
        selected.append(j);summaries.append(per_cell)
        coverage.append({'drug':r['drug'],'target_index':j,'source_cell_count':len(per_cell),'source_series':int(use.sum()),'log_molar_interval':[float(lo),float(hi)]})
    if len(selected)<2:raise ValueError('too few matched compounds')
    common=sorted(set.intersection(*(set(s) for s in summaries)))
    if len(common)<minimum:raise ValueError('insufficient complete cell-line intersection: '+str(len(common)))
    x=np.array([[summary[cell] for summary in summaries] for cell in common]);centered=x-x.mean(0)
    covariance=centered.T@centered/len(common);sd=np.sqrt(np.diag(covariance))
    if sd.min()<=1e-6:raise ValueError('zero-variation drug in source response panel')
    correlation=covariance/(sd[:,None]*sd[None,:]);correlation=(correlation+correlation.T)/2
    prior=np.eye(len(records));indices=np.asarray(selected)
    prior[np.ix_(indices,indices)]=(1-CORRELATION_SHRINKAGE)*correlation+CORRELATION_SHRINKAGE*np.eye(len(selected))
    np.linalg.cholesky(prior)
    return {'prior':prior,'target_indices':indices,'cell_keys':np.asarray(common),'source_summary_matrix':x,
       'coverage':coverage,'min_eigenvalue':float(np.linalg.eigvalsh(prior).min())}

def prepare(source,metadata,out):
    source,metadata,out=map(Path,(source,metadata,out));audit_path=out.with_name('OUTPUT_BANK_AUDIT.json')
    if out.exists() or audit_path.exists():raise ValueError('preserve existing source-only bank')
    if sha(source)!=SOURCE_SHA:raise ValueError('external source hash mismatch')
    meta=json.loads(metadata.read_text(encoding='utf-8'))
    if meta['status']!='SOURCE_ONLY_BANK_READY' or meta['supported_targets']!=20:raise ValueError('chemical/dose matching not audited')
    with np.load(source,allow_pickle=False) as z:fit=output_prior(z['values'],z['nsc'],z['cell_keys'],z['log_high'],meta['records'])
    out.parent.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out,prior=fit['prior'],target_indices=fit['target_indices'],cell_keys=fit['cell_keys'],
       source_summary_matrix=fit['source_summary_matrix'],drug_names=np.array([r['drug'] for r in meta['records']]))
    record={'schema':'dosepilot.external_output_coupling64.source_bank.v1','status':'SOURCE_ONLY_OUTPUT_PRIOR_READY',
       'source_cache_sha256':SOURCE_SHA,'chemical_dose_audit_sha256':sha(metadata),'bank_sha256':sha(out),
       'matched_drugs':len(fit['target_indices']),'common_source_cell_identifiers':len(fit['cell_keys']),
       'covariance_shrinkage':CORRELATION_SHRINKAGE,'source_coverage':fit['coverage'],
       'min_prior_eigenvalue':fit['min_eigenvalue'],'source_response_matrix_published':False,
       'organoid_data_read':False,'external_means_or_potencies_imported':False,'independent_biological_validation':False,
       'external_response_extrapolation':False,'source_missing_values_imputed':False,
       'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with audit_path.open('x',encoding='utf-8',newline='\n') as f:json.dump(record,f,indent=2);f.write('\n')
    print(json.dumps(record,indent=2),flush=True);return record
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--metadata',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();prepare(a.source,a.metadata,a.out)
