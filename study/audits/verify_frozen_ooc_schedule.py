#!/usr/bin/env python3
"""Response-free audit of the frozen bandwidth treatment schedules and OoC templates."""
from pathlib import Path
import argparse,csv,hashlib,importlib.util,json,re

TBD='TBD_BEFORE_PROSPECTIVE_COLLECTION'
UNRESOLVED=['chip_device_id','chip_compartment_id','circuit_id','reservoir_id','channel_id',
            'dosing_route','exposure_hours','readout_timepoint_hours','readout_type']

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,msg):
    if not ok: raise ValueError(msg)
def load_module(path):
    spec=importlib.util.spec_from_file_location('ooc_feasibility_audit',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def load_public_schedule(path):
    text=Path(path).read_text()
    match=re.search(r"const frozenSchedule=(\[.*?\]);\s*const frozenAbbr=",text,re.S)
    require(match is not None,'SITE_SCHEDULE_PARSE')
    return json.loads(match.group(1))

def verify(root,repo):
    root=Path(root);repo=Path(repo)
    summary=json.loads((root/'frozen_ooc_execution_schedule_20261003.json').read_text())
    receipt=json.loads((repo/'evidence/bandwidth_successor_20261003.json').read_text())
    compiler=load_module(repo/'demo/ooc_feasibility.py')
    require(summary['schema']=='dosepilot.frozen_ooc_execution_schedule.v1','SUMMARY_SCHEMA')
    require(summary['status']=='TREATMENT_SCHEDULE_FROZEN_DEVICE_BINDING_PENDING','SUMMARY_STATUS')
    require(summary['model_kind']==receipt['model_kind']=='dosepilot.additive_kernel_bandwidth.v1','MODEL_KIND')
    require(summary['bandwidth_multiplier']==receipt['bandwidth_multiplier']==.7,'BANDWIDTH')
    require(summary['original_plan_sha256']==receipt['final_model']['plan_sha256'],'SOURCE_PLAN_HASH')
    require(summary['construction_sha256']==receipt['final_model']['construction_sha256'],'CONSTRUCTION_HASH')
    require(summary['unresolved_fields']==UNRESOLVED,'UNRESOLVED_FIELDS')
    require(summary['controls_required_separately']==['vehicle','viability'],'CONTROLS')
    require(summary['prospective_experiment_executed'] is False and summary['biological_validation_created'] is False,'CLAIM_SCOPE')
    plans={};templates={};synthetic={}
    for orientation in ('A','B'):
        pp=root/f'frozen_bandwidth_orientation_{orientation}_plan_20261003.json'
        cp=root/f'prospective_ooc_binding_template_{orientation}_20261003.csv'
        require(sha(pp)==summary['orientations'][orientation]['plan_sha256'],'PLAN_HASH_'+orientation)
        require(sha(cp)==summary['orientations'][orientation]['binding_template_sha256'],'CSV_HASH_'+orientation)
        plan=json.loads(pp.read_text());plans[orientation]=plan
        require(plan['schema']=='von.acquisition.v1','PLAN_SCHEMA_'+orientation)
        require(plan['orientation']==orientation,'ORIENTATION_'+orientation)
        require(plan['source_original_plan_sha256']==summary['original_plan_sha256'],'PLAN_SOURCE_HASH_'+orientation)
        require(plan['source_construction_sha256']==summary['construction_sha256'],'PLAN_CONSTRUCTION_'+orientation)
        require(plan['physical_slot_semantics']=='PROSPECTIVE_PLACEHOLDER_NOT_EXECUTED','SLOT_SCOPE_'+orientation)
        require(plan['treatment_wells']==64 and plan['controls_included'] is False,'PLAN_BUDGET_'+orientation)
        require(plan['plate_counts']=={'p1':32,'p2':32},'PLATE_COUNTS_'+orientation)
        rows=plan['measurements'];require(len(rows)==64,'ROWS_'+orientation)
        require([r['position'] for r in rows]==list(range(64)),'POSITIONS_'+orientation)
        require(len({r['native_id'] for r in rows})==64,'NATIVE_IDS_'+orientation)
        require(sum(r['plate']=='p1' for r in rows)==32 and sum(r['plate']=='p2' for r in rows)==32,'OBS_PLATES_'+orientation)
        compiler._validate_plan(plan)
        fixture=compiler.make_synthetic_fixture(plan)
        manifest=compiler.compile_manifest(plan,fixture)
        require(manifest['treatment_action_count']==64 and manifest['distinct_treatment_resources']==64,'COMPILED_TREATMENTS_'+orientation)
        require(manifest['separate_control_resource_count']==2 and manifest['controls_in_treatment_budget'] is False,'COMPILED_CONTROLS_'+orientation)
        synthetic[orientation]={'inventory_sha256':manifest['inventory_sha256'],'manifest_payload_sha256':manifest['manifest_payload_sha256'],
            'treatment_actions':manifest['treatment_action_count'],'separate_controls':manifest['separate_control_resource_count']}
        with cp.open() as f: table=list(csv.DictReader(f))
        require(len(table)==64,'TEMPLATE_ROWS_'+orientation);templates[orientation]=table
        for row,bind in zip(rows,table):
            for a,b in [('position','position'),('native_id','native_id'),('drug_id','drug_id'),('concentration_nM','concentration_nM'),('unit','unit')]:
                require(str(row[a])==str(bind[b]),'TEMPLATE_ID_'+orientation+'_'+a)
            require(bind['source_plate']==row['plate'] and bind['source_plate_instance']==row['plate_instance'] and bind['source_well']==row['well'],'TEMPLATE_SOURCE_'+orientation)
            require(all(bind[k]==TBD for k in UNRESOLVED),'TEMPLATE_TBD_'+orientation)
            require(bind['binding_status']=='UNRESOLVED_DEVICE_BINDING','TEMPLATE_STATUS_'+orientation)
    a,b=plans['A']['measurements'],plans['B']['measurements']
    for ra,rb in zip(a,b):
        for key in ('position','native_id','drug_id','concentration_nM','unit'):
            require(ra[key]==rb[key],'AB_IDENTITY_'+key)
        require(ra['plate']!=rb['plate'],'AB_NOT_COMPLEMENTARY')
    counts={}
    for row in a:counts[row['drug_id']]=counts.get(row['drug_id'],0)+1
    require(len(counts)==24,'TARGET_COUNT')
    require(sorted(counts.values())==[2]*8+[3]*16,'TARGET_ALLOCATION')

    # Bind the judge-facing schedule to the verified plans rather than trusting
    # a separately hand-copied JavaScript array or Markdown table.
    expected_public=[]
    for ra,rb in zip(a,b):
        expected_public.append({
            'drug':ra['drug_id'],'dose':str(ra['concentration_nM']),
            'native':ra['native_id'],'a':0 if ra['plate']=='p1' else 1,
            'b':0 if rb['plate']=='p1' else 1,
        })
    public_schedule=load_public_schedule(repo/'site/frozen_schedule.js')
    require(public_schedule==expected_public,'SITE_SCHEDULE_MISMATCH')

    manifest_doc=(repo/'docs/FROZEN_OOC_EXECUTION_MANIFEST.md').read_text()
    writeup=(repo/'docs/KAGGLE_WRITEUP.md').read_text()
    site_html=(repo/'site/index.html').read_text()
    for label,text in (('MANIFEST_DOC',manifest_doc),('WRITEUP',writeup),('SITE_HTML',site_html)):
        require('\\n' not in text,'TRANSPORT_ESCAPE_'+label)
    require('<script src="frozen_schedule.js"></script>' in site_html,'SITE_SCRIPT_LINK')
    require('id="frozen-schedule"' in site_html,'SITE_SECTION')
    selection_disclosure=(
        'bandwidth 0.7 was selected from the prefrozen {1.0, 0.7, 1.4} menu '
        'after comparing reused outer-fold development results. Its displayed MSE '
        'is a post-selection development point estimate, not an unbiased nested '
        'estimate of bandwidth selection.'
    )
    require(selection_disclosure in site_html,'SITE_SELECTION_DISCLOSURE')
    require('NO CHERRY-PICKING' not in site_html,'SITE_OVERSTATED_SEARCH_LABEL')

    grouped={}
    for ra,rb in zip(a,b):
        item=grouped.setdefault(ra['drug_id'],{'doses':[],'a':[],'b':[]})
        item['doses'].append(str(ra['concentration_nM']))
        item['a'].append(ra['plate'])
        item['b'].append(rb['plate'])
    for drug,item in grouped.items():
        expected='| '+drug+' | '+', '.join(item['doses'])+' | '+', '.join(item['a'])+' | '+', '.join(item['b'])+' |'
        require(expected in manifest_doc,'MANIFEST_TABLE_'+drug)

    return {'status':'PASS','model_kind':summary['model_kind'],'bandwidth_multiplier':.7,
        'orientations':{'A':{'wells':64,'p1':32,'p2':32},'B':{'wells':64,'p1':32,'p2':32}},
        'ab_same_treatments':True,'ab_complementary_plate_assignment':True,
        'targets':24,'two_dose_targets':8,'three_dose_targets':16,
        'public_schedule_rows':len(public_schedule),'public_site_schedule_exact':True,
        'manifest_table_exact':True,'transport_escape_literals':0,
        'bandwidth_post_selection_disclosed':True,
        'overstated_search_label_absent':True,
        'public_surface_sha256':{
            'site/frozen_schedule.js':sha(repo/'site/frozen_schedule.js'),
            'site/index.html':sha(repo/'site/index.html'),
            'docs/FROZEN_OOC_EXECUTION_MANIFEST.md':sha(repo/'docs/FROZEN_OOC_EXECUTION_MANIFEST.md'),
            'docs/KAGGLE_WRITEUP.md':sha(repo/'docs/KAGGLE_WRITEUP.md')},
        'unresolved_device_binding_fields':len(UNRESOLVED),'separate_control_types':2,
        'synthetic_compiler_witness':synthetic,'prospective_experiment_executed':False,
        'protected_response_access':False,'private_patient_rows_read':False,'biological_validation_created':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path)
    a=p.parse_args();r=verify(a.root,a.repo);text=json.dumps(r,indent=2)+'\n'
    if a.output:
        if a.output.exists():raise ValueError('Output exists')
        a.output.write_text(text)
    print(text,end='')
if __name__=='__main__':main()
