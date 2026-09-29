#!/usr/bin/env python3
"""Prepare the canonical Lib1 release from a caller-supplied exact workbook.

No download. No Lib2 numerical conversion. This version parses the same immutable bytes that passed its hash checks.
Only invented XML fixtures have exercised this version, not the original workbook.
Historical metadata files are copied as compatibility snapshots only after
newly extracted numerical files match the pinned canonical release byte hashes.
A separate SOURCE_REPRODUCTION_RECEIPT records what this invocation did.
"""
from __future__ import annotations
import argparse,csv,hashlib,io,json,math,re,shutil,sys,time,traceback,zipfile
from decimal import Decimal,InvalidOperation
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np

NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
HEADERS=['sample_id','sample_id_drums','run_id','assay_no','library_id','compound_name',
         'compound_fimm','compound_drums','compound_type','concentration','concentration_unit',
         'drow','dcol','plate','signal','viability']
SOURCE_SHA='3847aa93b2a84c7d5d0b04c26494f39f35963fc41e96eae97d8a180fbc33d81c'
MANIFEST_SHA='9222bd6689da88be5786ecda57f7a372fca40f67d7beb910d340f2ac730eff0f'
LOCK_SHA='8118b562b78b3f55866d6239a38280c942df2c7d81f0b7c4ce71ba0e39ce9ffc'

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024**2),b''):h.update(b)
 return h.hexdigest()

def dump(p,x):
 with Path(p).open('x') as f:f.write(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n')

def dose(x):
 try:
  d=Decimal(x)
  return Decimal(format(d,'.12g')).normalize() if d.is_finite() and d>0 else None
 except (InvalidOperation,TypeError):return None

def text(cell,shared):
 if cell is None:return None
 kind=cell.get('t')
 if kind=='s':
  value=cell.findtext('m:v',None,NS)
  if value is None or not re.fullmatch(r'0|[1-9][0-9]*',value):raise ValueError('Invalid shared-string index')
  index=int(value)
  if index>=len(shared):raise ValueError('Shared-string index out of bounds')
  return shared[index]
 if kind=='inlineStr':
  child=cell.find('m:is',NS)
  return ''.join(child.itertext()) if child is not None else None
 return cell.findtext('m:v',None,NS)

def sheet_member(z):
 workbook=ET.fromstring(z.read('xl/workbook.xml'))
 sheets=workbook.findall('m:sheets/m:sheet',NS)
 if [s.get('name') for s in sheets]!=['DSRT_RAW_211PDOs']:raise ValueError('Unexpected sheet schema')
 rels=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
 relmap={r.get('Id'):r.get('Target') for r in rels}
 rid=sheets[0].get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
 member=relmap[rid]
 member=member.lstrip('/') if member.startswith('/') else 'xl/'+member
 if '..' in Path(member).parts or member not in z.namelist():raise ValueError('Unsafe or missing sheet member')
 return member

def integrate(doses,values,bounds):
 x=np.log(np.asarray(doses,dtype=float));v=np.asarray(values,dtype=float)
 lo,hi=np.log(np.asarray(bounds,dtype=float))
 if len(x)<2 or np.any(np.diff(x)<=0) or not (x[0]<=lo<hi<=x[-1]):raise ValueError('Invalid frozen interval/grid')
 inside=(x>lo)&(x<hi);xx=np.r_[lo,x[inside],hi]
 yy=np.r_[np.interp(lo,x,v),v[inside],np.interp(hi,x,v)]
 return float(np.sum(np.diff(xx)*(yy[:-1]+yy[1:])/2)/(hi-lo))

def extract_train(workbook:Path, manifest:dict, observer=None):
 """Only select Lib1 records before requesting normalized-viability cell text.

 XML/shared-string parsing necessarily encounters uninterpreted file text.
 This records semantic P-cell requests/conversions, not claims of zero raw bytes.
 """
 samples=sorted([s for s in manifest['selected_samples'] if s['partition']=='train'],key=lambda s:s['sample_id'])
 if not samples or any(s['library_id']!='lib1' for s in samples):raise ValueError('Non-Lib1 TRAIN specification')
 if len({s['sample_id'] for s in samples})!=len(samples):raise ValueError('Repeated selected sample')
 expected={};drugids=[d['drug_id'] for d in manifest['target_drugs']]
 if len(drugids)!=len(set(drugids)):raise ValueError('Duplicate target')
 ranges={d['drug_id']:tuple(float(v) for v in d['common_interval_nM']) for d in manifest['target_drugs']}
 for s in samples:
  if [c['drug_id'] for c in s['curves']]!=drugids:raise ValueError('Incomplete target schema')
  for c in s['curves']:
   if [p['plate'] for p in c['plates']]!=['p1','p2']:raise ValueError('Technical plate schema changed')
   for p in c['plates']:
    for w in p['wells']:
     key=('lib1',s['sample_id'],s['run_id'],p['plate'],w['drow'],w['dcol'])
     if key in expected:raise ValueError('Duplicate declared physical well')
     expected[key]=(s,c['drug_id'],w)
 curves={};seen=set();tidy=[];decodes=0;header_seen=False;last_row=0
 with zipfile.ZipFile(workbook) as z:
  if len(z.namelist())!=len(set(z.namelist())):raise ValueError('Duplicate ZIP member')
  shared=[]
  if 'xl/sharedStrings.xml' in z.namelist():
   rr=ET.fromstring(z.read('xl/sharedStrings.xml'))
   shared=[''.join(n.itertext()) for n in rr.findall('m:si',NS)]
  with z.open(sheet_member(z)) as f:
   for _,row in ET.iterparse(f,events=('end',)):
    if row.tag!='{'+NS['m']+'}row':continue
    number=row.get('r','')
    if not re.fullmatch(r'[1-9][0-9]*',number) or int(number)<=last_row:raise ValueError('Noncanonical or unordered XML row')
    last_row=int(number)
    if not header_seen and number!='1':raise ValueError('Header row must precede data')
    cells={}
    for c in row.findall('m:c',NS):
     match=re.fullmatch(r'([A-Z]+)([1-9][0-9]*)',c.get('r',''))
     if match is None or match.group(2)!=number:raise ValueError('Cell coordinate differs from containing row')
     column=match.group(1)
     if column in cells:raise ValueError('Duplicate source cell column')
     cells[column]=c
    if row.get('r')=='1':
     if [text(cells.get(chr(65+i)),shared) for i in range(16)]!=HEADERS:raise ValueError('Header mismatch')
     header_seen=True;row.clear();continue
    if text(cells.get('E'),shared)!='lib1':row.clear();continue
    meta={HEADERS[i]:text(cells.get(chr(65+i)),shared) for i in range(14)}
    key=tuple(meta[k] for k in ('library_id','sample_id','run_id','plate','drow','dcol'))
    if key not in expected:row.clear();continue
    s,drug,w=expected[key]
    if key in seen:raise ValueError('Duplicate selected response')
    if (meta['compound_type']!='single' or meta['concentration_unit']!='nM' or meta['compound_name']!=drug or
        any(meta[k]!=w[k] for k in ('assay_no','compound_fimm','compound_drums')) or dose(meta['concentration'])!=dose(w['concentration_nM'])):
     raise ValueError('Selected physical metadata mismatch')
    c=cells.get('P')
    if c is None or c.get('t') not in (None,'n','s','inlineStr','str') or c.find('m:f',NS) is not None:raise ValueError('Missing/boolean/error/unsupported/formula required TRAIN viability')
    if observer is not None:observer(key)
    decodes+=1
    try:v=float(text(c,shared))
    except (TypeError,ValueError):raise ValueError('Nonnumeric required TRAIN viability') from None
    if not math.isfinite(v):raise ValueError('Nonfinite required TRAIN viability')
    seen.add(key);concentration=float(dose(meta['concentration']))
    ck=(s['sample_id'],drug,meta['plate']);curve=curves.setdefault(ck,{})
    if concentration in curve:raise ValueError('Duplicate dose in curve')
    curve[concentration]=v
    tidy.append({'sample_id':s['sample_id'],'patient_id':s['patient_id'],'library_id':'lib1',
      'run_id':s['run_id'],'drug_id':drug,'plate':meta['plate'],'dose_nM':concentration,'viability':v,
      'drow':meta['drow'],'dcol':meta['dcol'],'assay_no':meta['assay_no']})
    row.clear()
 if not header_seen:raise ValueError('Missing source header')
 if seen!=expected.keys():raise ValueError('Required TRAIN wells absent')
 py=np.empty((len(samples),len(drugids),2));counts=np.empty((len(samples),len(drugids)),dtype=np.int64)
 for i,s in enumerate(samples):
  for j,drug in enumerate(drugids):
   count=0
   for r,plate in enumerate(('p1','p2')):
    c=curves[(s['sample_id'],drug,plate)];grid=sorted(c)
    py[i,j,r]=integrate(grid,[c[v] for v in grid],ranges[drug]);count+=len(grid)
   counts[i,j]=count
 arrays={'y':py.mean(axis=2),'y_replicates':py,'plate_y':py,
  'sample_ids':np.asarray([s['sample_id'] for s in samples]),'patient_ids':np.asarray([s['patient_id'] for s in samples]),
  'run_ids':np.asarray([s['run_id'] for s in samples]),'drug_ids':np.asarray(drugids),
  'library_ids':np.asarray(['lib1']*len(samples)),'common_intervals_nM':np.asarray([ranges[d] for d in drugids]),'well_counts':counts}
 tidy.sort(key=lambda r:(r['sample_id'],r['drug_id'],r['plate'],r['dose_nM']))
 return arrays,tidy,{'selected_viability_decodes':decodes,'lib2_numeric_conversions':0,'raw_signal_conversions':0}

def verified_snapshot(path, expected_sha, label):
 """Read once, authenticate once, and return the bytes consumed downstream.

 A later path replacement cannot alter this snapshot. This is input integrity,
 not proof of source licensing, laboratory execution or access authorization.
 """
 raw=Path(path).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=expected_sha:
  raise ValueError('Pinned input mismatch: '+label)
 return raw

def pinned_metadata(assets, lock):
 snapshots={}
 for rel,record in lock['input_files'].items():
  if rel in {'train/train.npz','train/train_curves.csv'}:continue
  p=Path(rel)
  if p.is_absolute() or '..' in p.parts or str(p)!=rel:
   raise ValueError('Unsafe metadata template path')
  snapshots[rel]=verified_snapshot(Path(assets)/rel,record['sha256'],rel)
 return snapshots

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--source-xlsx',type=Path,required=True)
 p.add_argument('--assets',type=Path,required=True)
 p.add_argument('--output',type=Path,required=True)
 a=p.parse_args()
 if a.output.exists():raise SystemExit('Refusing existing output')
 # Each object is parsed/copied from its authenticated byte buffer, never reopened.
 source_bytes=verified_snapshot(a.source_xlsx,SOURCE_SHA,'original workbook')
 manifest_bytes=verified_snapshot(a.assets/'INPUT_MANIFEST_v1.json',MANIFEST_SHA,'eligibility manifest')
 lock_bytes=verified_snapshot(Path(__file__).parent/'STUDY_LOCK.json',LOCK_SHA,'study lock')
 lock=json.loads(lock_bytes)
 metadata=pinned_metadata(a.assets,lock)
 manifest=json.loads(manifest_bytes)
 script_hash=sha(Path(__file__))
 a.output.mkdir(parents=True);(a.output/'train').mkdir()
 started=time.perf_counter();access=[]
 # Written before semantic access. On abrupt interruption it conservatively
 # records possible access, not a fabricated zero-conversion success/failure.
 dump(a.output/'SOURCE_ACCESS_STARTED.json',{
  'status':'ACCESS_MAY_HAVE_STARTED','allowed_partition':'train','allowed_library':'lib1',
  'source_sha256':SOURCE_SHA,'manifest_sha256':MANIFEST_SHA,'script_sha256':script_hash,
  'automatic_retry':False,'success_receipt_required':True})
 try:
  arrays,tidy,audit=extract_train(io.BytesIO(source_bytes),manifest,access.append)
  np.savez_compressed(a.output/'train/train.npz',**arrays)
  with (a.output/'train/train_curves.csv').open('w',newline='') as f:
   writer=csv.DictWriter(f,fieldnames=list(tidy[0]));writer.writeheader();writer.writerows(tidy)
  for rel in ('train/train.npz','train/train_curves.csv'):
   if sha(a.output/rel)!=lock['input_files'][rel]['sha256']:
    raise ValueError('New extraction does not match canonical release bytes: '+rel)
  for rel,raw in metadata.items():
   dest=a.output/rel;dest.parent.mkdir(parents=True,exist_ok=True)
   with dest.open('xb') as f:f.write(raw)
  dump(a.output/'SOURCE_REPRODUCTION_RECEIPT.json',{
   'status':'canonical_numeric_release_reproduced','source_sha256':SOURCE_SHA,
   'script_sha256':script_hash,'manifest_sha256':MANIFEST_SHA,'seconds':time.perf_counter()-started,
   'historical_metadata_copied_as_snapshots':True,'new_execution_provenance':'this receipt only',
   'audit':audit,'inputs_parsed_from_verified_byte_snapshots':True,
   'note':'Historical metadata remains historical; this receipt identifies the current execution.'})
 except Exception as exc:
  dump(a.output/'SOURCE_FAILURE.json',{'error':str(exc),'traceback':traceback.format_exc(),
   'selected_cells_requested':len(access),'outputs_retained':True,'automatic_retry':False})
  raise

if __name__=='__main__':main()
