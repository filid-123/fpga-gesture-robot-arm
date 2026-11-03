"""Offline snapshot ownership and failure-evidence tests; no PYNQ connection."""
import io,json,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import roarm_mode_a as a

class Vision:
 def __init__(self,bits=0):self.enabled=False;self.ready=False;self.bits=bits;self.writes=[];self.addr=0
 def read(self,addr):
  if addr==0x50:
   if not(self.enabled and self.ready):raise AssertionError('Read without held ownership')
   value=self.addr;self.addr+=1;return value
  values={0x74:0x43414d31,0x78:self.bits|(int(self.enabled)<<9)|(int(self.enabled and self.ready)<<10),
    0x40:int(self.enabled),0x44:(int(self.enabled)<<1)|int(self.enabled and self.ready),0x48:12,0x58:100,
    0x28:11,0x2c:11,0x7c:4,0x80:2,0x84:123}
  return values[addr]
 def write(self,addr,value):
  self.writes.append((addr,value))
  if addr==0x40:self.enabled=bool(value)
  elif addr==0x4c:self.addr=value

class CameraTests(unittest.TestCase):
 def board(self,vis,permission=False):
  arm=Mock();arm.status.return_value.permission=permission
  task=Mock();task.status.return_value.state=a.m.State.OFF
  return arm,Mock(),task,vis
 def test_diagnostics_decode_existing_state_and_counters(self):
  vis=Vision((5<<16)|(1<<12)|3|(1<<3)|(1<<5))
  d=a.camera_diagnostics(vis)
  self.assertTrue(d['xclk_locked']);self.assertTrue(d['init_done'])
  self.assertEqual(d['pipeline_state'],'WAIT_FRAME');self.assertEqual(d['capture_state'],'HELD')
  self.assertEqual(d['format_errors'],2);self.assertEqual(d['dropped_while_owned'],4)
  self.assertFalse(d['init_error']);self.assertFalse(d['snapshot_requested'])
 def test_timeout_preserves_requested_state_in_error_then_releases(self):
  vis=Vision(3|(1<<3));stdout=io.StringIO()
  with patch.object(a,'board',return_value=self.board(vis)),patch.object(a.time,'monotonic',side_effect=[0,6]),patch('sys.stdout',stdout):
   with self.assertRaisesRegex(TimeoutError,'No retained camera frame'):a.take_snapshot(Path('UNUSED_OFFLINE_OUTPUT'))
  event=json.loads(stdout.getvalue())
  self.assertEqual(event['event'],'SNAPSHOT_FAILURE')
  self.assertTrue(event['camera']['snapshot_requested'])
  self.assertEqual(vis.writes,[(0x40,1),(0x40,0)])
  self.assertFalse(vis.enabled)
 def test_fatal_fails_without_waiting_and_still_releases(self):
  vis=Vision(1<<4)
  with patch.object(a,'board',return_value=self.board(vis)),patch.object(a.time,'monotonic',return_value=0),patch.object(a.time,'sleep') as wait,patch('sys.stdout',io.StringIO()):
   with self.assertRaisesRegex(RuntimeError,'FIFO overflow'):a.take_snapshot(Path('UNUSED_OFFLINE_OUTPUT'))
   wait.assert_not_called()
  self.assertEqual(vis.writes,[(0x40,1),(0x40,0)])
 def test_motion_permission_and_other_snapshot_owner_are_not_touched(self):
  vis=Vision()
  with patch.object(a,'board',return_value=self.board(vis,True)):
   with self.assertRaisesRegex(RuntimeError,'motion permission removed'):a.take_snapshot(Path('UNUSED_OFFLINE_OUTPUT'))
  self.assertEqual(vis.writes,[])
  vis.enabled=True
  with patch.object(a,'board',return_value=self.board(vis)):
   with self.assertRaisesRegex(RuntimeError,'Another snapshot request'):a.take_snapshot(Path('UNUSED_OFFLINE_OUTPUT'))
  self.assertEqual(vis.writes,[]);self.assertTrue(vis.enabled)
 def test_success_exports_complete_little_endian_pgm_under_one_owner(self):
  root=(a.ROOT/'runs').resolve();root.mkdir(exist_ok=True)
  with tempfile.TemporaryDirectory(prefix='SYNTHETIC_camera_',dir=root) as tmp:
   target=Path(tmp).resolve();self.assertTrue(target.is_relative_to(root));out=target/'camera.pgm'
   vis=Vision(3|(1<<3)|(1<<5)|(1<<12)|(5<<16));vis.ready=True
   with patch.object(a,'board',return_value=self.board(vis)),patch('sys.stdout',io.StringIO()):a.take_snapshot(out)
   pixels=out.read_bytes();header=b'P5\n640 480\n255\n'
   self.assertTrue(pixels.startswith(header));self.assertEqual(len(pixels)-len(header),307200)
   self.assertEqual(pixels[len(header):len(header)+8],struct.pack('<II',0,1))
   self.assertEqual(pixels[-4:],struct.pack('<I',76799));self.assertEqual(vis.addr,76800)
   metadata=json.loads(out.with_suffix('.json').read_text())
   self.assertEqual(metadata['frame_id'],12);self.assertTrue(metadata['camera']['snapshot_requested'])
   self.assertTrue(metadata['camera']['snapshot_ready']);self.assertFalse(vis.enabled)

if __name__=='__main__':unittest.main()
