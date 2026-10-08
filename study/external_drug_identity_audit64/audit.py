"""Public chemical metadata only. Never reads or transmits organoid outcomes.
PubChem synonym NSCs are CANDIDATES, accepted only after DTP.NCI source-SID
standardized-CID confirmation. Compound mixtures are not mapped to ingredients.
"""
from pathlib import Path
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse,datetime,hashlib,json,re,time
from urllib.parse import quote
import numpy as np,requests
DRUGS=('5-FU','AZD7762','Afatinib','Alisertib','Atorvastatin','Bemcentinib','Encorafenib','Gedatolisib','Gemcitabine','Idasanutlin','LCL161','LGK974','Lapatinib','Luminespib','Methotrexate','Napabucasin','Palbociclib','Panobinostat','Pevonedistat','Regorafenib','SN-38','TAS-102','Trametinib','Volasertib')
ALIASES={'5-FU':'5-fluorouracil'}
SOURCE_SHA='53aae154d310256d77ddbc9c9d6ddab461235496e12009a23105620c0181b66c'
MAX_REQUESTS=96
NSC_PATTERN=re.compile(r'^NSC[ -]?(\d+)$',re.I)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def cids(value):
    result=set()
    if isinstance(value,dict):
        for key,v in value.items():
            if key=='CID':result.update([int(v)] if isinstance(v,int) else [int(x) for x in v] if isinstance(v,list) else [])
            else:result.update(cids(v))
    elif isinstance(value,list):
        for v in value:result.update(cids(v))
    return result
class Client:
    def __init__(self,out):self.out=out;self.n=0;self.last=0.;self.logs=[];self.session=requests.Session()
    def get(self,url):
        if self.n>=MAX_REQUESTS:raise RuntimeError('metadata request budget exhausted')
        time.sleep(max(0,1.1-(time.monotonic()-self.last)));self.last=time.monotonic();self.n+=1
        row={'request':self.n,'url':url,'utc':utc()}
        try:
            with self.session.get(url,timeout=(8,20),stream=True) as r:
                row['http_status']=r.status_code;parts=[];size=0
                for part in r.iter_content(16384):
                    size+=len(part)
                    if size>2_000_000:raise RuntimeError('public metadata response exceeds cap')
                    parts.append(part)
                blob=b''.join(parts);path=self.out/f'pubchem_{self.n:03d}.json'
                with path.open('xb') as f:f.write(blob)
                row.update({'response_file':path.name,'bytes':size,'sha256':sha(path)})
                result=json.loads(blob) if r.status_code==200 else None
        except Exception as e:row['error']=repr(e);result=None
        self.logs.append(row)
        return result,row

def audit(source,out):
    source=Path(source);out=Path(out)
    if sha(source)!=SOURCE_SHA:raise ValueError('wrong external cache')
    # Metadata keys only: external curve response values are not loaded.
    with np.load(source,allow_pickle=False) as z:nsc=z['nsc'];cells=z['cell_keys'];experiments=z['experiment']
    present=set(map(str,nsc));out.mkdir(parents=True,exist_ok=False);client=Client(out);rows=[]
    for drug in DRUGS:
        if drug=='TAS-102':
            rows.append({'drug':drug,'status':'COMBINATION_NOT_ASSIGNED_TO_SINGLE_COMPONENT','exact_matches':[]});continue
        public_name=ALIASES.get(drug,drug)
        url='https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/'+quote(public_name,safe='')+'/synonyms/JSON'
        payload,request=client.get(url);row={'drug':drug,'public_name_query':public_name,'synonym_request':request,'exact_matches':[]}
        if payload is None:row['status']='PUBLIC_LOOKUP_UNRESOLVED';rows.append(row);print(drug,row['status'],flush=True);continue
        records=payload.get('InformationList',{}).get('Information',[])
        if len(records)!=1 or 'CID' not in records[0]:row['status']='AMBIGUOUS_COMPOUND_NAME';rows.append(row);continue
        record=records[0];cid=int(record['CID']);row['compound_cid']=cid
        candidates=sorted({m.group(1) for text in record.get('Synonym',[]) if (m:=NSC_PATTERN.fullmatch(text.strip()))},key=int)
        row['synonym_nsc_candidates']=candidates;row['nsc_candidates_in_external_source']=[n for n in candidates if n in present];checks=[]
        for n in row['nsc_candidates_in_external_source']:
            u='https://pubchem.ncbi.nlm.nih.gov/rest/pug/substance/sourceid/DTP.NCI/'+n+'/cids/JSON?cids_type=standardized'
            document,req=client.get(u);found=sorted(cids(document)) if document is not None else []
            matched=bool(cid in found);checks.append({'nsc':n,'standardized_cids':found,'exact_cid_match':matched,'request':req})
            if matched:
                mask=nsc==n;row['exact_matches'].append({'nsc':n,'compound_cid':cid,'external_curve_groups':int(mask.sum()),'external_cell_identifiers':len(np.unique(cells[mask])),'external_experiments':len(np.unique(experiments[mask]))})
        row['source_confirmation_checks']=checks
        row['status']='EXACT_STANDARDIZED_CID_MATCH' if row['exact_matches'] else 'NO_VALIDATED_SOURCE_MATCH'
        rows.append(row);print(json.dumps({'drug':drug,'status':row['status'],'matches':row['exact_matches']}),flush=True)
    result={'schema':'dosepilot.external_drug_identity_audit64.v1','status':'METADATA_AUDIT_COMPLETE','utc':utc(),
      'source_cache_sha256':SOURCE_SHA,'source_metadata_only':True,'source_compounds':len(present),'targets':24,
      'validated_targets':sum(bool(r['exact_matches']) for r in rows),'unresolved_public_lookups':sum(r['status']=='PUBLIC_LOOKUP_UNRESOLVED' for r in rows),
      'requests':client.n,'rows':rows,'organoid_responses_read':False,'patient_data_transmitted':False,
      'same_drug_does_not_imply_same_assay':True,'salt_or_component_equivalence_assumed':False,
      'compound_mixture_to_ingredient_mapping_used':False,'candidate_model_trained':False,'accuracy_improvement_claimed':False,
      'method_documentation':'https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest'}
    with (out/'IDENTITY_AUDIT.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2),flush=True)
    return result
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();audit(a.source,a.out)
