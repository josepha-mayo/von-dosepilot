"""Construct location-only maps and sample-local routine-control fields.
No regression labels enter control-field estimation. The inference fields require
only the declared plate layout and the same standard control wells.
"""
from pathlib import Path
import csv,io
import numpy as np
from core import field
ARMS=('identity','flat','spatial')


def integer_coordinate(value):
    text=str(value)
    if text.isalpha():
        n=0
        for char in text.upper():n=n*26+ord(char)-64
        return n
    x=float(text)
    if not np.isfinite(x) or int(x)!=x:raise ValueError('noninteger plate coordinate')
    return int(x)


def normalized_positions(positions):
    a=np.asarray(positions,float)
    if a.ndim!=2 or a.shape[1]!=2 or not np.isfinite(a).all():raise ValueError('row-column positions required')
    if np.any(a[:,0]<1) or np.any(a[:,0]>16) or np.any(a[:,1]<1) or np.any(a[:,1]>24):
        raise ValueError('outside fixed 16x24 plate')
    return 2*(a-np.array([1.,1.]))/np.array([15.,23.])-1


def layout_and_fields(curves_path,controls_path,data,catalog,full):
    samples=list(map(str,data['sample_ids']));targets=list(map(str,catalog.target_ids));sid_index={v:i for i,v in enumerate(samples)}
    target_index={v:i for i,v in enumerate(targets)};metadata={};grids={j:set() for j in range(24)};allowed=set()
    # Only metadata columns are requested here. The authenticated full-grid loader
    # separately supplies fitting responses under its own checks.
    with Path(curves_path).open(encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            if r['library_id']!='lib1' or r['sample_id'] not in sid_index or r['drug_id'] not in target_index:
                raise ValueError('unexpected curve identity')
            i=sid_index[r['sample_id']];j=target_index[r['drug_id']];plate={'p1':0,'p2':1}[r['plate']];dose=float(r['dose_nM'])
            key=(i,j,dose,plate)
            if key in metadata:raise ValueError('duplicate physical curve cell')
            metadata[key]=[integer_coordinate(r['drow']),integer_coordinate(r['dcol'])]
            grids[j].add(dose);allowed.add((r['sample_id'],r['run_id'],r['plate']))
    lookup={};owners=[]
    for j in range(24):
        for dose in sorted(grids[j]):lookup[(j,dose)]=len(owners);owners.append(j)
    if not np.array_equal(owners,full['owner']):raise ValueError('full-grid ordering mismatch')
    positions=np.full((len(samples),2*len(owners),2),np.nan)
    for (i,j,dose,plate),position in metadata.items():positions[i,2*lookup[(j,dose)]+plate]=position
    if not np.isfinite(positions).all():raise ValueError('missing physical location')
    controls={};seen=set()
    with Path(controls_path).open(encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):
            if (r['sample_id'],r['run_id'],r['plate']) not in allowed or r['control_type'] not in ('negative','positive'):
                raise ValueError('unauthorized control row')
            i=sid_index[r['sample_id']];plate={'p1':0,'p2':1}[r['plate']]
            point=(integer_coordinate(r['row']),integer_coordinate(r['column']))
            key=(i,plate,*point)
            if key in seen:raise ValueError('duplicate control position')
            seen.add(key);controls.setdefault((i,plate,r['control_type']),[]).append((point,float(r['signal'])))
    offsets={arm:np.zeros(positions.shape[:2]) for arm in ARMS};gains={arm:np.ones(positions.shape[:2]) for arm in ARMS};audit=[]
    for i in range(len(samples)):
        for plate in (0,1):
            pair={}
            for kind,count in (('negative',13),('positive',9)):
                rows=sorted(controls.get((i,plate,kind),[]))
                if len(rows)!=count:raise ValueError('routine-control count changed')
                pair[kind]=(normalized_positions([r[0] for r in rows]),np.asarray([r[1] for r in rows]))
            where=np.arange(plate,positions.shape[1],2);query=normalized_positions(positions[i,where])
            for arm in ARMS:
                a,g,report=field(*pair['negative'],*pair['positive'],query,arm)
                offsets[arm][i,where]=a;gains[arm][i,where]=g
                audit.append(dict(report,sample_index=i,plate=plate,arm=arm))
    return {'offsets':offsets,'gains':gains,'position_metadata':positions,
            'field_audit':audit,'control_values_used':len(seen),'control_wells_per_plate':22,
            'full_owner':np.repeat(full['owner'],2)}
