"""Chemical/CID and absolute-molar-dose matched external covariance bank.
No organoid response values are parsed. Unsupported targets use the original
pooled relative-dose correlation, never an extrapolated external curve.
"""
from pathlib import Path
import argparse,csv,datetime,hashlib,importlib.util,json
import numpy as np
p=Path(__file__).resolve().parent.parent/'external_shape_shrink64/model.py'
spec=importlib.util.spec_from_file_location('existing_correlation_math',p);base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
MIN_CELLS=20
SOURCE_SHA='53aae154d310256d77ddbc9c9d6ddab461235496e12009a23105620c0181b66c'
CURVES_SHA='b192dc242362d74c4faa941752792336c7610d9bd403cccbf1cee7a8a1fc7c94'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def log_molar(doses_nm):
    d=np.asarray(doses_nm,float)
    if d.ndim!=1 or len(d)<2 or not np.isfinite(d).all() or (d<=0).any() or np.any(np.diff(d)<=0):raise ValueError('positive ordered nM doses required')
    return np.log10(d)-9.
def equal_cell_compound_weights(cells,compounds):
    cells=np.asarray(cells,str);compounds=np.asarray(compounds,str)
    if len(cells)==0 or cells.shape!=compounds.shape:raise ValueError('nonempty matched metadata required')
    w=np.zeros(len(cells));cellids=np.unique(cells)
    for cell in cellids:
        ix=np.flatnonzero(cells==cell);drugs=np.unique(compounds[ix])
        for drug in drugs:
            rows=ix[compounds[ix]==drug];w[rows]=1/(len(cellids)*len(drugs)*len(rows))
    return w

def match_correlation(values,nsc,cells,high,candidates,doses_nm,fallback,min_cells=MIN_CELLS):
    values=np.asarray(values,float);nsc=np.asarray(nsc,str);cells=np.asarray(cells,str);high=np.asarray(high,float)
    d=log_molar(doses_nm);matched=np.isin(nsc,list(candidates));cover=(d[0]>=high-4-1e-8)&(d[-1]<=high+1e-8)
    mask=matched&cover;count=len(np.unique(cells[mask]));rows=np.flatnonzero(mask)
    audit={'exact_nsc_candidates':list(candidates),'chemical_curve_groups':int(matched.sum()),'fully_covering_curve_groups':len(rows),
           'fully_covering_cell_identifiers':count,'required_min_cells':min_cells,'requested_log_molar_range':[float(d[0]),float(d[-1])],
           'source_ranges_for_matching_chemical':sorted(set(map(float,high[matched]))),'extrapolation_used':False}
    if count<min_cells:
        audit['status']='POOLED_FALLBACK_INSUFFICIENT_EXACT_DOSE_COVERAGE';return np.asarray(fallback,float).copy(),audit
    curves=np.stack([np.interp(d,np.arange(high[i]-4,high[i]+.5),values[i]) for i in rows])
    weights=equal_cell_compound_weights(cells[rows],nsc[rows]);centered=curves-weights@curves
    covariance=centered.T@(weights[:,None]*centered);variance=np.diag(covariance)
    if variance.min()<=1e-12:
        audit['status']='POOLED_FALLBACK_DEGENERATE_EXTERNAL_VARIANCE';return np.asarray(fallback,float).copy(),audit
    sd=np.sqrt(variance);corr=covariance/(sd[:,None]*sd[None,:]);corr=(corr+corr.T)/2
    if np.linalg.eigvalsh(corr).min()<-1e-9:raise ValueError('non-PSD matched correlation')
    audit['status']='EXACT_CHEMICAL_AND_DOSE_MATCH';audit['weight_sum']=float(weights.sum())
    audit['max_difference_from_pooled_correlation']=float(np.max(np.abs(corr-fallback)))
    return corr,audit

def prepare(source,identity,curves,out):
    source,identity,curves,out=map(Path,(source,identity,curves,out));auditpath=out.with_name('CHEMICAL_DOSE_BANK_AUDIT.json')
    if out.exists() or auditpath.exists():raise ValueError('existing source bank: no overwrite')
    if sha(source)!=SOURCE_SHA or sha(curves)!=CURVES_SHA:raise ValueError('unauthenticated source bytes')
    identification=json.loads(identity.read_text(encoding='utf-8'))
    if identification['status']!='METADATA_AUDIT_COMPLETE':raise ValueError('chemical identities not audited')
    with np.load(source,allow_pickle=False) as z:values=z['values'];weights=z['weights'];nsc=z['nsc'];cells=z['cell_keys'];high=z['log_high']
    pooled=base.external_covariance(values,weights)
    # Read only publicly reported identifiers/concentrations from the guarded CSV.
    grids={r['drug']:set() for r in identification['rows']}
    with curves.open(encoding='utf-8',newline='') as f:
        for row in csv.DictReader(f):
            if row['library_id']!='lib1' or row['drug_id'] not in grids:raise ValueError('unexpected metadata row')
            grids[row['drug_id']].add(float(row['dose_nM']))
    bank={};records=[];names=[]
    for j,row in enumerate(identification['rows']):
        name=row['drug'];names.append(name);doses=np.array(sorted(grids[name]));logs=log_molar(doses);positions=(logs-logs[0])/(logs[-1]-logs[0])
        fallback=base.relative_correlation(pooled,positions)
        # Strict: a candidate must resolve to exactly the requested standardized CID.
        candidates=sorted({r['nsc'] for r in row.get('source_confirmation_checks',[]) if r['exact_cid_match'] and r['standardized_cids']==[row.get('compound_cid')]},key=int)
        corr,audit=match_correlation(values,nsc,cells,high,candidates,doses,fallback)
        bank[f'pooled_{j}']=fallback;bank[f'matched_{j}']=corr;bank[f'doses_nM_{j}']=doses
        records.append(dict(audit,drug=name,compound_cid=row.get('compound_cid'),source_nsc_candidates=candidates))
    bank['drug_names']=np.asarray(names);bank['pooled_covariance5']=pooled
    out.parent.mkdir(parents=True,exist_ok=True);np.savez_compressed(out,**bank)
    receipt={'schema':'dosepilot.chemical_dose_correlation64.source_bank.v1','status':'PREPARED_SOURCE_ONLY',
       'source_sha256':SOURCE_SHA,'identity_audit_sha256':sha(identity),'organoid_metadata_source_sha256':CURVES_SHA,
       'bank_sha256':sha(out),'matched_chemical_targets':identification['validated_targets'],
       'matched_chemical_and_full_dose_targets':sum(r['status']=='EXACT_CHEMICAL_AND_DOSE_MATCH' for r in records),
       'targets':24,'records':records,'organoid_viability_values_parsed':False,'organoid_model_fitted':False,
       'extrapolation_used':False,'potency_or_assay_equivalence_claimed':False,'source_response_arrays_published':False,
       'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with auditpath.open('x',encoding='utf-8',newline='\n') as f:json.dump(receipt,f,indent=2);f.write('\n')
    print(json.dumps(receipt,indent=2),flush=True);return receipt
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--identity',type=Path,required=True);ap.add_argument('--curves',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();prepare(a.source,a.identity,a.curves,a.out)
