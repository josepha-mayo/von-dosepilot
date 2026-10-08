import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from extract_controls import read_one,source

class ControlExtractionTests(unittest.TestCase):
    def cells(self):
        vals={'A':'sample','C':'run','D':'assay','E':'lib1','I':'control_negative','L':'2','M':'3','N':'p1','O':'100','P':'DO_NOT_READ'}
        result={}
        for column,value in vals.items():
            cell=ET.Element('{'+source.NS['m']+'}c',{'r':column+'2','t':'inlineStr'})
            child=ET.SubElement(cell,'{'+source.NS['m']+'}is');ET.SubElement(child,'{'+source.NS['m']+'}t').text=value;result[column]=cell
        return result
    def setvalue(self,cells,key,value):cells[key].find('m:is/m:t',source.NS).text=value
    def guard(self,cells):
        original=source.text
        def text(cell,shared):
            if cell is cells.get('O') or cell is cells.get('P'):raise AssertionError('forbidden numeric cell requested')
            return original(cell,shared)
        return text
    def test_lib2_rejected_before_numeric_text(self):
        c=self.cells();self.setvalue(c,'E','lib2')
        with patch.object(source,'text',self.guard(c)):self.assertIsNone(read_one(c,[],{('sample','run','p1')}))
    def test_unselected_sample_rejected_before_numeric_text(self):
        c=self.cells()
        with patch.object(source,'text',self.guard(c)):self.assertIsNone(read_one(c,[],{('other','run','p1')}))
    def test_wrong_run_rejected_before_numeric_text(self):
        c=self.cells()
        with patch.object(source,'text',self.guard(c)):self.assertIsNone(read_one(c,[],{('sample','other','p1')}))
    def test_treatment_rejected_before_numeric_text(self):
        c=self.cells();self.setvalue(c,'I','single')
        with patch.object(source,'text',self.guard(c)):self.assertIsNone(read_one(c,[],{('sample','run','p1')}))
    def test_selected_control_reads_only_signal(self):
        c=self.cells();original=source.text;calls=[]
        def text(cell,shared):
            if cell is c['P']:raise AssertionError('viability read')
            if cell is c['O']:calls.append('signal')
            return original(cell,shared)
        with patch.object(source,'text',text):r=read_one(c,[],{('sample','run','p1')})
        self.assertEqual(calls,['signal']);self.assertEqual(r['signal'],100.);self.assertEqual(r['row'],2)
    def test_nonfinite_control_rejected(self):
        c=self.cells();self.setvalue(c,'O','nan')
        with self.assertRaises(ValueError):read_one(c,[],{('sample','run','p1')})
    def test_signal_formula_rejected(self):
        c=self.cells();ET.SubElement(c['O'],'{'+source.NS['m']+'}f').text='SUM(A1)'
        with self.assertRaises(ValueError):read_one(c,[],{('sample','run','p1')})

if __name__=='__main__':unittest.main(verbosity=2)
