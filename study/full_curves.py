"""Reconstruct a fixed full TRAIN grid without expanding the inference action set."""
from __future__ import annotations
import csv,hashlib,io
from types import SimpleNamespace
import numpy as np
from conditional import exact_auc_map


def full_training_curves(path,data,features,catalog,spec):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=spec['prepared_curves_sha256']:
        raise ValueError('authenticated Lib1 TRAIN input required')
    sample_ids=list(map(str,data['sample_ids']));sample_lookup={s:i for i,s in enumerate(sample_ids)}
    drug_ids=list(map(str,catalog.target_ids));target_lookup={t:i for i,t in enumerate(drug_ids)}
    source={};grids={}
    for row in csv.DictReader(io.StringIO(raw.decode('utf-8'))):
        if row['library_id']!='lib1' or row['sample_id'] not in sample_lookup or row['drug_id'] not in target_lookup or row['plate'] not in ('p1','p2'):
            raise ValueError('unauthorized/malformed source identity')
        i=sample_lookup[row['sample_id']];j=target_lookup[row['drug_id']];plate=0 if row['plate']=='p1' else 1
        if row['patient_id']!=str(data['patient_ids'][i]):raise ValueError('patient identity mismatch')
        dose=float(row['dose_nM']);key=(i,j,plate,dose)
        if key in source:raise ValueError('duplicate full-grid cell')
        source[key]=float(row['viability']);grids.setdefault((i,j,plate),set()).add(dose)
    full_doses=[];owners=[];lookup={}
    for j in range(len(drug_ids)):
        variants={tuple(sorted(grids[(i,j,plate)])) for i in range(len(sample_ids)) for plate in (0,1)}
        if len(variants)!=1:raise ValueError('nonuniform full TRAIN grid needs a different prefrozen protocol')
        for dose in next(iter(variants)):
            lookup[(j,dose)]=len(full_doses);full_doses.append(dose);owners.append(j)
    values=np.full((len(sample_ids),len(full_doses),2),np.nan)
    for (i,j,plate,dose),value in source.items():values[i,lookup[(j,dose)],plate]=value
    if not np.isfinite(values).all():raise ValueError('full TRAIN data missing or nonfinite')
    query_to_full=np.array([lookup[(int(j),float(dose))] for j,dose in zip(catalog.native_target_indices,catalog.concentrations)])
    if not np.array_equal(values[:,query_to_full,:],features['x_replicates']):raise ValueError('fixed eligible query catalog changed')
    fullcat=SimpleNamespace(native_ids=np.arange(len(full_doses)),target_ids=catalog.target_ids,
          native_target_indices=np.asarray(owners),concentrations=tuple(full_doses))
    q=exact_auc_map(fullcat,spec['target_bounds_nM'])
    difference=float(np.max(np.abs(values.reshape(len(values),-1)@q-data['y'])))
    if difference>1e-12:raise ValueError('exact endpoint reconstruction failed')
    return {'values':values,'doses':np.asarray(full_doses),'owner':np.asarray(owners),'query_to_full':query_to_full,'q':q,
            'quadrature_maxdiff':difference,'full_physical_cells':2*len(full_doses),
            'eligible_physical_cells':2*len(query_to_full),'new_inference_actions_added':False}
