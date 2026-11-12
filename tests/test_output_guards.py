"""Regression for destructive report-path aliasing. Uses disposable fixtures only."""
import json,subprocess,sys,tempfile,unittest
from pathlib import Path
S=Path(__file__).resolve().parents[1]/'tools'/'py'
class Guards(unittest.TestCase):
 def check_case(self,tool,make_args):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);source=d/'source.json';raw=b'{"bones":[{"name":"root"}],"animations":{}}';source.write_bytes(raw)
   output=d/'out.json';report=d/'report.json';alias=d/'alias.json';alias.symlink_to(source)
   args=make_args(source,output,report,alias)
   before={p:p.read_bytes() for p in d.iterdir() if p.is_file()}
   p=subprocess.run([sys.executable,str(S/tool),*map(str,args)],capture_output=True)
   self.assertNotEqual(p.returncode,0)
   for f,b in before.items():self.assertEqual(f.read_bytes(),b)
   self.assertFalse(output.exists());self.assertFalse(report.exists())
 def test_compact_report_input(self):self.check_case('compact_spine_json.py',lambda s,o,r,a:[s,'--out',o,'--report',s])
 def test_compact_report_symlink(self):self.check_case('compact_spine_json.py',lambda s,o,r,a:[s,'--out',o,'--report',a])
 def test_compact_report_main_output(self):self.check_case('compact_spine_json.py',lambda s,o,r,a:[s,'--out',o,'--report',o])
 def test_compact_output_input(self):self.check_case('compact_spine_json.py',lambda s,o,r,a:[s,'--out',s])
 def test_audit_output_input(self):self.check_case('spine_audit.py',lambda s,o,r,a:[s,'--out',s])
 def test_audit_output_symlink(self):self.check_case('spine_audit.py',lambda s,o,r,a:[s,'--out',a])
 def test_new_outputs_work(self):
  with tempfile.TemporaryDirectory() as t:
   d=Path(t);s=d/'source.json';s.write_text('{"bones":[],"animations":{}}');raw=s.read_bytes()
   for tool,args in [('spine_audit.py',[s,'--out',d/'audit.json']),('compact_spine_json.py',[s,'--out',d/'new.json','--report',d/'report.json'])]:
    p=subprocess.run([sys.executable,str(S/tool),*map(str,args)],capture_output=True);self.assertEqual(p.returncode,0,p.stderr)
   self.assertEqual(s.read_bytes(),raw);self.assertEqual(json.loads((d/'new.json').read_text()),json.loads(raw))
if __name__=='__main__':unittest.main()
