"""Audit and cache the official HTS384 source; no DosePilot outcomes read.
Records are grouped by documented experiment, compound, concentration range,
and cell identifiers. Extra curves are not extra independent cell lines.
"""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,csv,hashlib,json,math,datetime
import numpy as np
SOURCE_SHA='4088c00b6eea513c4d5add4e7052b53f66a13c4c541c42ef853f8658a9db8cba'
FIELDS=['EXPID','PREFIX','NSC','CONCUNIT','LHICONC','LCONC','M_GIPRCNT','PANELCDE','CELLNBR','PANELNAME','CELLNAME','PANELNBR','M_PTC']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def prepare(source,out):
    source=Path(source);out=Path(out)
    if sha(source)!=SOURCE_SHA:raise ValueError('unrecognized official CSV bytes')
    if (out/'CURVE_AUDIT.json').exists() or (out/'curves_private.npz').exists():raise ValueError('prepared source exists')
    groups=defaultdict(list);row_reasons=Counter();all_rows=0
    with source.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=FIELDS:raise ValueError('source schema changed')
        for row in reader:
            all_rows+=1
            if row['PREFIX']!='S' or row['CONCUNIT']!='M':row_reasons['not_public_small_molecule_molar']+=1;continue
            key=tuple(row[k] for k in ('EXPID','PREFIX','NSC','LHICONC','PANELNBR','CELLNBR'))
            try:hi=float(row['LHICONC']);dose=float(row['LCONC']);response=float(row['M_PTC'])/100
            except ValueError:groups[key].append(None);row_reasons['non_numeric_required_field']+=1;continue
            if not all(math.isfinite(x) for x in (hi,dose,response)):
                groups[key].append(None);row_reasons['nonfinite_required_field']+=1;continue
            groups[key].append((dose,response,row['CELLNAME'],row['PANELNAME']))
    accepted=[];reasons=Counter()
    for key,rows in groups.items():
        if any(row is None for row in rows):reasons['required_values_missing']+=1;continue
        if len(rows)!=5:reasons['not_exactly_five_rows']+=1;continue
        rows=sorted(rows);d=np.array([v[0] for v in rows]);hi=float(key[3])
        if len(set(d))!=5:reasons['duplicate_concentration']+=1;continue
        if not np.allclose(d,np.arange(hi-4,hi+1),atol=1e-8,rtol=0):reasons['not_standard_five_log_grid']+=1;continue
        if len({r[2] for r in rows})!=1:reasons['cell_name_conflict']+=1;continue
        accepted.append((key,np.array([r[1] for r in rows]),rows[0][2],rows[0][3]))
    accepted.sort(key=lambda r:r[0])
    if not accepted:raise ValueError('no complete eligible external curves')
    keys=[r[0] for r in accepted];values=np.stack([r[1] for r in accepted]);cells=np.array([k[4]+'|'+k[5] for k in keys]);nsc=np.array([k[2] for k in keys])
    weights=np.zeros(len(keys));cell_count=len(np.unique(cells))
    for cell in np.unique(cells):
        ii=np.flatnonzero(cells==cell);compounds=np.unique(nsc[ii])
        for compound in compounds:
            jj=ii[nsc[ii]==compound];weights[jj]=1/(cell_count*len(compounds)*len(jj))
    if abs(weights.sum()-1)>1e-12:raise ValueError('external weighting failed')
    out.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(out/'curves_private.npz',values=values,weights=weights,cell_keys=cells,nsc=nsc,
        experiment=np.array([k[0] for k in keys]),log_high=np.array([float(k[3]) for k in keys]),
        cell_names=np.array([r[2] for r in accepted]),normalized_log_dose=np.linspace(0,1,5))
    covariance=(values-weights@values).T@(weights[:,None]*(values-weights@values))
    audit={'schema':'dosepilot.hts384.external_curve_audit.v1','status':'READY_FOR_SHAPE_ONLY_PRIOR',
       'source_sha256':SOURCE_SHA,'source_rows':all_rows,'candidate_curve_groups':len(groups),'accepted_curves':len(keys),
       'unique_cell_identifiers':len(np.unique(cells)),'unique_cell_names':len(set(r[2] for r in accepted)),
       'unique_compounds':len(np.unique(nsc)),'unique_experiments':len(set(k[0] for k in keys)),
       'row_exclusions':dict(row_reasons),'curve_exclusions':dict(reasons),
       'response_field':'M_PTC / 100, not M_GIPRCNT','response_quantiles':dict(zip(['min','p001','p01','median','p99','p999','max'],np.quantile(values,[0,.001,.01,.5,.99,.999,1]).tolist())),
       'shape_coordinate':'relative log concentration within each five-point four-log series; no drug-potency equivalence',
       'external_weighting':'equal cell identifier, equal NSC within cell, equal experiment/range within cell+NSC',
       'weight_sum':float(weights.sum()),'weighted_mean_curve':(weights@values).tolist(),'covariance5':covariance.tolist(),
       'prepared_sha256':sha(out/'curves_private.npz'),'source_responses_clipped':False,
       'patient_inputs_read':False,'existing_external_validation_partition_reused':False,
       'novel_independent_patient_count_claimed':False,'raw_source_republished':False,
       'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with (out/'CURVE_AUDIT.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(audit,f,indent=2);f.write('\n')
    print(json.dumps(audit,indent=2),flush=True);return audit

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();prepare(a.source,a.out)
