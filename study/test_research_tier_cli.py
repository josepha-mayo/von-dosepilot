"""Exercise the packaged 128-well model with fictional data and malformed cases."""
import argparse,csv,json
from pathlib import Path
from predict_research_tier import predict_file

def main(directory):
    with (directory/'synthetic_input_A.csv').open(newline='') as f:rows=list(csv.DictReader(f))
    checks=[]
    def run(name,records,orientation,expected_error=None):
        ip=directory/f'cli_fixture_{name}.csv';op=directory/f'cli_fixture_{name}_output.csv'
        with ip.open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=['sample_id','query_id','plate','viability']);w.writeheader();w.writerows(records)
        try:
            receipt=predict_file(directory,ip,orientation,op)
        except ValueError as e:
            if expected_error is None or expected_error not in str(e):raise
            if op.exists():raise AssertionError('Invalid inputs created a prediction file')
        else:
            if expected_error is not None:raise AssertionError('Invalid input accepted: '+name)
            if receipt['purchased_wells_per_sample']!=128 or receipt['outputs_per_sample']!=24:raise AssertionError('Wrong contract')
            with op.open(newline='') as f:
                reader=csv.reader(f);values=list(reader)
            assert len(values)==2 and len(values[0])==25 and len(values[1])==25
        checks.append(name)
    run('validA',rows,'A')
    inverse=[dict(r,plate='p2' if r['plate']=='p1' else 'p1') for r in rows];run('validB',inverse,'B')
    run('missing',rows[:-1],'A','exactly 128')
    run('only64',rows[:64],'A','exactly 128')
    run('duplicate',rows+[dict(rows[0])],'A','Duplicate')
    run('unpaid',rows+[dict(rows[0],query_id='unpaid-query')],'A','unpurchased')
    invalid=[dict(r) for r in rows];invalid[0]['viability']='nan';run('nonfinite',invalid,'A','Nonfinite')
    run('wrong_layout',rows,'B','unpurchased')
    report={'status':'PASS','synthetic_only':True,'treatment_wells_required':128,'checks':checks,'clinical_validation':False}
    with (directory/'CLI_VERIFICATION.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(report),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();main(a.directory)
