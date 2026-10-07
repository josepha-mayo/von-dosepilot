"""Read only standard-control signals for the exact authorized Lib1 TRAIN plates.
The XLSX bytes contain broader study data. Metadata is parsed before requesting
any numeric control signal; no treatment signal or viability value is decoded.
"""
from pathlib import Path
import csv,hashlib,io,json,math,re,sys,zipfile,datetime
import xml.etree.ElementTree as ET
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'study'))
import prepare_from_source_v3 as source
SOURCE_SHA='3847aa93b2a84c7d5d0b04c26494f39f35963fc41e96eae97d8a180fbc33d81c'
CURVE_SHA='b192dc242362d74c4faa941752792336c7610d9bd403cccbf1cee7a8a1fc7c94'
QUALITY_SHA='f09448aad3d62de360d07be799a43a3fa7f3442b6b1f7c829c12533f43d8b0ba'
TAGS={'control_negative':'negative','control_positive':'positive'}

def read_one(cells,shared,allowed,observer=None):
    # Critically: never request column O or P unless library/sample/run/type/plate pass.
    if source.text(cells.get('E'),shared)!='lib1':return None
    sid=source.text(cells.get('A'),shared);run=source.text(cells.get('C'),shared)
    plate=source.text(cells.get('N'),shared)
    if (sid,run,plate) not in allowed:return None
    kind=source.text(cells.get('I'),shared)
    if kind not in TAGS:return None
    meta={key:source.text(cells.get(col),shared) for key,col in [('sample_id','A'),('run_id','C'),('assay_no','D'),('drow','L'),('dcol','M')]}
    c=cells.get('O')
    if c is None or c.get('t') not in (None,'n','s','inlineStr','str') or c.find('m:f',source.NS) is not None:
        raise ValueError('missing/formula/unsupported control signal')
    if observer is not None:observer((sid,run,plate,kind,meta['drow'],meta['dcol']))
    value=float(source.text(c,shared))
    if not math.isfinite(value):raise ValueError('nonfinite control signal')
    def coord(v):
        if re.fullmatch('[A-Za-z]+',v or ''):
            n=0
            for char in v.upper():n=n*26+ord(char)-64
            return n
        x=float(v)
        if not math.isfinite(x) or int(x)!=x:raise ValueError('nonintegral coordinate')
        return int(x)
    return dict(meta,plate=plate,control_type=TAGS[kind],row=coord(meta['drow']),column=coord(meta['dcol']),signal=value)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def execute(workbook,curves,quality,out):
    workbook=Path(workbook);curves=Path(curves);quality=Path(quality);out=Path(out)
    if out.exists():raise ValueError('no overwrite: inspect prior extraction')
    raw=workbook.read_bytes();curve_bytes=curves.read_bytes();quality_bytes=quality.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCE_SHA or hashlib.sha256(curve_bytes).hexdigest()!=CURVE_SHA or hashlib.sha256(quality_bytes).hexdigest()!=QUALITY_SHA:
        raise ValueError('input byte mismatch')
    allowed=set();patients={}
    for row in csv.DictReader(io.StringIO(curve_bytes.decode('utf-8'))):
        if row['library_id']!='lib1':raise ValueError('non-Lib1 TRAIN source')
        key=(row['sample_id'],row['run_id'],row['plate']);allowed.add(key);patients[row['sample_id']]=row['patient_id']
    if len(patients)!=119 or len(set(patients.values()))!=59 or len(allowed)!=238:raise ValueError('TRAIN selection count changed')
    out.mkdir(parents=True,exist_ok=False);started={'status':'CONTROL_ACCESS_MAY_HAVE_STARTED','source_sha256':SOURCE_SHA,
      'allowed_sample_run_plates':len(allowed),'allowed_controls':list(TAGS),'treatment_signal_decoding_permitted':False,
      'viability_decoding_permitted':False,'Lib2_signal_decoding_permitted':False,'extractor_sha256':sha(__file__),
      'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (out/'ACCESS_STARTED.json').write_text(json.dumps(started,indent=2)+'\n',encoding='utf-8')
    rows=[];access=[];seen=set()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            shared=[''.join(node.itertext()) for node in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',source.NS)]
        with z.open(source.sheet_member(z)) as stream:
            for _,node in ET.iterparse(stream,events=('end',)):
                if node.tag!='{'+source.NS['m']+'}row':continue
                cells={re.match(r'[A-Z]+',c.get('r','')).group():c for c in node.findall('m:c',source.NS)}
                if node.get('r')=='1':
                    if [source.text(cells.get(chr(65+i)),shared) for i in range(16)]!=source.HEADERS:raise ValueError('header mismatch')
                else:
                    value=read_one(cells,shared,allowed,access.append)
                    if value is not None:
                        key=(value['sample_id'],value['run_id'],value['plate'],value['row'],value['column'])
                        if key in seen:raise ValueError('duplicate standard-control position')
                        seen.add(key);rows.append(value)
                node.clear()
    groups={}
    for row in rows:groups.setdefault((row['sample_id'],row['plate'],row['control_type']),[]).append(row)
    if len(groups)!=119*2*2:raise ValueError('missing standard-control group')
    old={r['sample_id']:r for r in csv.DictReader(io.StringIO(quality_bytes.decode('utf-8')))};max_quality=0.
    geometry={}
    for sid in sorted(patients):
        for plate in ('p1','p2'):
            signals={t:np.array([r['signal'] for r in groups[(sid,plate,t)]]) for t in ('negative','positive')}
            for t,tag in [('negative','neg'),('positive','pos')]:
                x=signals[t]
                computed={f'{plate}_{tag}_logmed':float(np.log1p(np.median(x))),f'{plate}_{tag}_cv':float(np.std(x)/(abs(np.mean(x))+1e-12))}
                for name,value in computed.items():max_quality=max(max_quality,abs(value-float(old[sid][name])))
                positions=tuple(sorted((r['row'],r['column']) for r in groups[(sid,plate,t)]))
                geometry.setdefault(plate+'_'+t,{})[positions]=geometry.setdefault(plate+'_'+t,{}).get(positions,0)+1
            span=max(float(np.median(signals['negative'])-np.median(signals['positive'])),0.)
            max_quality=max(max_quality,abs(float(np.log1p(span))-float(old[sid][plate+'_logrange'])))
    if max_quality>1e-10:raise ValueError('control inventory does not reproduce existing QC resource '+str(max_quality))
    rows.sort(key=lambda r:(r['sample_id'],r['plate'],r['control_type'],r['row'],r['column']))
    with (out/'controls_private.csv').open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary={'schema':'dosepilot.standard_control_spatial_inventory.v1','status':'PASS_CONTROL_ONLY_EXTRACTION',
      'source_sha256':SOURCE_SHA,'curve_sha256':CURVE_SHA,'prior_quality_sha256':QUALITY_SHA,
      'control_signal_conversions':len(access),'treatment_signal_conversions':0,'viability_conversions':0,'Lib2_numeric_conversions':0,
      'selected_samples':119,'selected_patients':59,'sample_run_plates':238,'existing_QC_summary_maxdiff':max_quality,
      'same_standard_control_inventory_as_retained_model':True,
      'control_groups':{k:[{'positions':[list(p) for p in positions],'plates_with_this_geometry':n,'control_count':len(positions)} for positions,n in value.items()] for k,value in geometry.items()},
      'private_controls_sha256':sha(out/'controls_private.csv'),'new_treatment_measurements':0,
      'candidate_predictions_computed':False,'predictive_residuals_inspected':False,'controls_are_separate_assay_resources':True,
      'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    (out/'INVENTORY.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True);return summary

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--workbook',type=Path,required=True);ap.add_argument('--curves',type=Path,required=True)
    ap.add_argument('--quality',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();execute(a.workbook,a.curves,a.quality,a.out)
