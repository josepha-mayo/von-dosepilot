"""Invented workbook tests only. No external source or biological values."""
import copy
import io
from pathlib import Path
from unittest import mock
import unittest
from xml.sax.saxutils import escape
import zipfile

import prepare_compact_source as source
from prepare_from_source_v3 import extract_train
import test_compact_train as fixtures


def metadata_fixture():
    fixtures.CompactTests.setUpClass()
    spec=copy.deepcopy(fixtures.CompactTests.spec)
    rows=[]
    for row in fixtures.CompactTests.rows:
        rows.append(dict(sample_id=row['sample_id'],sample_id_drums='fictional',run_id=row['run_id'],
             assay_no=row['assay_no'],library_id='lib1',compound_name=row['drug_id'],
             compound_fimm='fictional',compound_drums=spec['compound_drums_by_target'][row['drug_id']],
             compound_type='single',concentration=row['dose_nM'],concentration_unit='nM',
             drow=row['drow'],dcol=row['dcol'],plate=row['plate'],signal='POISON',viability='0.75'))
    return spec,rows


def workbook(rows, *, header=None, duplicate_cell=False, wrong_reference=False):
    header=source.HEADERS if header is None else header
    xml=['<worksheet xmlns="'+source.NS['m']+'"><sheetData>']
    for n,values in enumerate([header]+[[r.get(k,'') for k in source.HEADERS] for r in rows],1):
        xml.append(f'<row r="{n}">')
        for j,value in enumerate(values):
            col=chr(65+j);ref_n=n+1 if wrong_reference and n==2 and j==0 else n
            xml.append(f'<c r="{col}{ref_n}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        if duplicate_cell and n==2:xml.append(f'<c r="A2"><v>duplicate</v></c>')
        xml.append('</row>')
    xml.append('</sheetData></worksheet>')
    raw=io.BytesIO()
    with zipfile.ZipFile(raw,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('xl/workbook.xml','<workbook xmlns="'+source.NS['m']+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="DSRT_RAW_211PDOs" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml',''.join(xml))
    return raw.getvalue()


class SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.spec,cls.rows=metadata_fixture()

    def manifest(self,rows=None):return source.build_manifest(self.rows if rows is None else rows,self.spec)

    def test_complete_selection(self):
        m=self.manifest();self.assertEqual(len(m['selected_samples']),2)
        self.assertEqual(sum(s['all_target_well_count'] for s in m['selected_samples']),len(self.rows))

    def test_metadata_has_no_response_dependency(self):
        rows=copy.deepcopy(self.rows)
        for row in rows:row['signal']=row['viability']=object()
        self.assertEqual(self.manifest(rows),self.manifest())

    def test_lib2_excluded_before_identity(self):
        self.assertEqual(self.manifest([{'library_id':'lib2','sample_id':object(),'viability':object()}]+self.rows),self.manifest())

    def test_natural_run_order(self):
        rows=copy.deepcopy(self.rows)
        other=copy.deepcopy(self.rows)
        for row in rows:row['run_id']='run10'
        for row in other:row['run_id']='run2'
        m=self.manifest(rows+other)
        self.assertTrue(all(s['run_id']=='run2' for s in m['selected_samples']))

    def test_incomplete_earlier_run_not_selected(self):
        rows=copy.deepcopy(self.rows)
        for row in rows:row['run_id']='run2'
        partial=copy.deepcopy(rows[:10])
        for row in partial:row['run_id']='run1'
        self.assertTrue(all(s['run_id']=='run2' for s in self.manifest(partial+rows)['selected_samples']))

    def test_missing_target_not_silently_dropped(self):
        rows=[r for r in self.rows if r['compound_name']!=self.spec['target_ids'][0]]
        with self.assertRaisesRegex(ValueError,'fixed TRAIN population'):self.manifest(rows)

    def test_compound_identity(self):
        rows=copy.deepcopy(self.rows);rows[0]['compound_drums']='WRONG'
        with self.assertRaisesRegex(ValueError,'compound identity'):self.manifest(rows)

    def test_duplicate_well(self):
        with self.assertRaisesRegex(ValueError,'Duplicate selected physical'):self.manifest(self.rows+[self.rows[0]])

    def test_duplicate_dose(self):
        extra=copy.deepcopy(self.rows[0]);extra['dcol']='9999'
        with self.assertRaisesRegex(ValueError,'Duplicate selected native dose'):self.manifest(self.rows+[extra])

    def test_no_patient_identity_guessing(self):
        rows=copy.deepcopy(self.rows);rows[0]['sample_id']='unknown'
        with self.assertRaisesRegex(ValueError,'sample-to-patient'):self.manifest(rows)

    def test_missing_metadata_identity(self):
        rows=copy.deepcopy(self.rows);rows[0]['run_id']=''
        with self.assertRaisesRegex(ValueError,'Missing Lib1'):self.manifest(rows)

    def test_xml_metadata_avoids_response_cells(self):
        poison={'library_id':'lib2','sample_id':'not-needed','viability':'NOT_A_NUMBER'}
        called=[];original=source.text
        def spy(cell,shared):
            if cell is not None:called.append(cell.get('r'))
            return original(cell,shared)
        with mock.patch.object(source,'text',spy):
            rows=list(source.iter_lib1_metadata(workbook([poison]+self.rows)))
        self.assertEqual(len(rows),len(self.rows))
        self.assertTrue(all(not (r.startswith(('O','P')) and r not in ('O1','P1')) for r in called))
        self.assertEqual(self.manifest(rows),self.manifest())

    def test_xml_header(self):
        header=source.HEADERS.copy();header[-1]='wrong'
        with self.assertRaisesRegex(ValueError,'header'):list(source.iter_lib1_metadata(workbook(self.rows,header=header)))

    def test_xml_duplicate_cell(self):
        with self.assertRaisesRegex(ValueError,'coordinate'):list(source.iter_lib1_metadata(workbook(self.rows,duplicate_cell=True)))

    def test_xml_bad_row_reference(self):
        with self.assertRaisesRegex(ValueError,'coordinate'):list(source.iter_lib1_metadata(workbook(self.rows,wrong_reference=True)))

    def test_invented_full_extraction(self):
        poison={'library_id':'lib2','sample_id':'not-needed','viability':'NOT_A_NUMBER'}
        raw=workbook([poison]+self.rows)
        m=source.build_manifest(source.iter_lib1_metadata(raw),self.spec)
        seen=[];arrays,tidy,audit=extract_train(io.BytesIO(raw),m,seen.append)
        self.assertEqual(audit['selected_viability_decodes'],len(self.rows))
        self.assertEqual(audit['lib2_numeric_conversions'],0)
        self.assertEqual(audit['raw_signal_conversions'],0)
        self.assertEqual(arrays['y'].shape,(2,24))
        self.assertEqual(len(tidy),len(self.rows))
        self.assertTrue(all(k[0]=='lib1' for k in seen))

    def test_required_viability_fails(self):
        rows=copy.deepcopy(self.rows);rows[0]['viability']='bad'
        with self.assertRaisesRegex(ValueError,'Nonnumeric required TRAIN'):
            extract_train(io.BytesIO(workbook(rows)),self.manifest(),lambda key:None)

    def test_cross_drug_physical_collision(self):
        rows=copy.deepcopy(self.rows)
        index=next(i for i,r in enumerate(rows) if r['compound_name']!=rows[0]['compound_name'])
        for k in ('drow','dcol','plate'):rows[index][k]=rows[0][k]
        with self.assertRaisesRegex(ValueError,'Duplicate declared physical'):
            extract_train(io.BytesIO(workbook(rows)),self.manifest(rows))

if __name__=='__main__':unittest.main()
