import unittest,importlib.util,tempfile,hashlib,json,contextlib,io,sys
from pathlib import Path
from unittest.mock import patch
script=Path(__file__).parent/'flash.py'
spec=importlib.util.spec_from_file_location('flash_under_test',script);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class FlashTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='flash package with spaces ');self.root=Path(self.temp.name)
  data=b'local test binary';(self.root/'app.bin').write_bytes(data);(self.root/'boot.bin').write_bytes(data)
  parts=[dict(path='boot.bin',offset=0,size=len(data),sha256=hashlib.sha256(data).hexdigest(),initial_only=True),dict(path='app.bin',offset=65536,size=len(data),sha256=hashlib.sha256(data).hexdigest(),initial_only=False)]
  (self.root/'manifest.json').write_text(json.dumps({'targets':{'controller':{'flash_mb':8,'parts':parts}}}))
  self.args=['controller','--port','NEVER_TOUCH']
 def tearDown(self):self.temp.cleanup()
 def run_main(self,extra):
  with contextlib.redirect_stdout(io.StringIO()) as output:
   result=m.main(self.args+extra,self.root)
  return result,output.getvalue()
 def test_dry_erase_has_no_serial_calls(self):
  with patch.object(m.subprocess,'check_call') as call:
   result,out=self.run_main(['--fresh','--erase-all']);call.assert_not_called();self.assertIn('erase_flash',out);self.assertIn('CHECK ONLY',out);self.assertEqual(result,0)
 def test_erase_requires_full_install(self):
  with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as exc:self.run_main(['--erase-all'])
  self.assertEqual(exc.exception.code,2)
 def test_corrupt_image_blocks_erase(self):
  (self.root/'boot.bin').write_bytes(b'corrupt')
  with patch.object(m.subprocess,'check_call') as call,self.assertRaises(SystemExit):self.run_main(['--fresh','--erase-all','--flash'])
  call.assert_not_called()
 def test_explicit_erase_before_write(self):
  with patch.object(m.importlib.metadata,'version',return_value='4.9.0'),patch.object(m.subprocess,'check_call') as call:self.run_main(['--fresh','--erase-all','--flash'])
  self.assertEqual(call.call_count,2);self.assertEqual(call.call_args_list[0].args[0][-1],'erase_flash');self.assertIn('write_flash',call.call_args_list[1].args[0]);self.assertEqual(call.call_args_list[1].args[0][0],sys.executable)
 def test_application_only_does_not_erase(self):
  with patch.object(m.importlib.metadata,'version',return_value='4.9.0'),patch.object(m.subprocess,'check_call') as call:self.run_main(['--flash'])
  self.assertEqual(call.call_count,1);self.assertNotIn('erase_flash',call.call_args.args[0]);self.assertNotIn(str(self.root/'boot.bin'),call.call_args.args[0])
 def test_wrong_esptool_does_not_touch_port(self):
  with patch.object(m.importlib.metadata,'version',return_value='5.0'),patch.object(m.subprocess,'check_call') as call,self.assertRaises(SystemExit):self.run_main(['--flash'])
  call.assert_not_called()
if __name__=='__main__':unittest.main()
