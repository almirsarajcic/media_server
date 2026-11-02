import importlib.machinery,importlib.util,pathlib,tempfile,unittest
from unittest.mock import patch
source=pathlib.Path(__file__).with_name('media-server').resolve()
loader=importlib.machinery.SourceFileLoader('media_controller',str(source));spec=importlib.util.spec_from_loader(loader.name,loader);m=importlib.util.module_from_spec(spec);loader.exec_module(m)
class GateTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.mount=pathlib.Path(self.temp.name);self.media=self.mount/'media';self.media.mkdir();self.original_root=m.ROOT;m.ROOT=self.mount/'runtime';m.ROOT.mkdir();(m.ROOT/'media').symlink_to(self.media)
  for n in ['movies','tv','downloads']:(self.media/n).mkdir()
  (self.media/'.media-server-storage').write_text('test-marker')
  self.profile={'mode':'external','volume_uuid':'TEST-UUID','mountpoint':str(self.mount),'media_root':str(self.media),'marker':'test-marker'}
  self.info={'VolumeUUID':'TEST-UUID','MountPoint':str(self.mount),'WritableVolume':True,'Internal':False,'DeviceIdentifier':'disk-test'}
 def tearDown(self):m.ROOT=self.original_root;self.temp.cleanup()
 def test_correct_volume_passes(self):
  with patch.object(m,'disk_info',return_value=self.info):self.assertEqual(m.storage_check(self.profile)['VolumeUUID'],'TEST-UUID')
 def test_absent_volume_blocks(self):
  with patch.object(m,'disk_info',side_effect=RuntimeError('missing')):self.assertRaises(RuntimeError,m.storage_check,self.profile)
 def test_ordinary_folder_cannot_replace_mount(self):
  with patch.object(m,'disk_info',return_value={**self.info,'MountPoint':''}):self.assertRaises(RuntimeError,m.storage_check,self.profile)
 def test_read_only_blocks(self):
  with patch.object(m,'disk_info',return_value={**self.info,'WritableVolume':False}):self.assertRaises(RuntimeError,m.storage_check,self.profile)
 def test_wrong_uuid_never_mounts(self):
  with patch.object(m,'disk_info',return_value={**self.info,'VolumeUUID':'WRONG','MountPoint':''}),patch.object(m.subprocess,'run') as run:
   self.assertRaises(RuntimeError,m.storage_check,self.profile,True);run.assert_not_called()
 def test_missing_paths_block(self):
  (self.media/'movies').rmdir()
  with patch.object(m,'disk_info',return_value=self.info):self.assertRaises(RuntimeError,m.storage_check,self.profile)
 def test_expected_unmounted_disk_is_mounted_then_verified(self):
  with patch.object(m,'disk_info',side_effect=[{**self.info,'MountPoint':''},self.info]),patch.object(m.subprocess,'run') as run:
   run.return_value.returncode=0;m.storage_check(self.profile,True);self.assertEqual(run.call_args.args[0],['/usr/sbin/diskutil','mount','disk-test'])
 def test_internal_disk_cannot_satisfy_external_profile(self):
  with patch.object(m,'disk_info',return_value={**self.info,'Internal':True}):self.assertRaises(RuntimeError,m.storage_check,self.profile)
 def test_symlink_outside_media_blocks(self):
  (self.media/'movies').rmdir();(self.media/'movies').symlink_to(self.mount)
  with patch.object(m,'disk_info',return_value=self.info):self.assertRaises(RuntimeError,m.storage_check,self.profile)
 def test_alternate_stable_path_blocks(self):
  (m.ROOT/'media').unlink();(m.ROOT/'media').symlink_to(self.mount)
  with patch.object(m,'disk_info',return_value=self.info):self.assertRaises(RuntimeError,m.storage_check,self.profile)
 def test_marker_loss_blocks(self):
  (self.media/'.media-server-storage').unlink()
  with patch.object(m,'disk_info',return_value=self.info):self.assertRaises(RuntimeError,m.storage_check,self.profile)
class RegistrationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=pathlib.Path(self.temp.name);self.old_root=m.ROOT;m.ROOT=self.base/'runtime';m.ROOT.mkdir()
  self.volume=self.base/'volume';self.media=self.volume/'data'
  for n in ['movies','tv','downloads']:(self.media/n).mkdir(parents=True,exist_ok=True)
  self.info={'VolumeUUID':'EXTERNAL-UUID','MountPoint':str(self.volume),'WritableVolume':True,'Internal':False}
 def tearDown(self):m.ROOT=self.old_root;self.temp.cleanup()
 def test_register_validates_after_switching_stable_path(self):
  with patch.object(m,'disk_info',return_value=self.info),patch.object(m.subprocess,'run') as run:
   run.return_value.returncode=1;m.register_external('EXTERNAL-UUID',str(self.volume),str(self.media))
  self.assertEqual((m.ROOT/'media').resolve(),self.media.resolve())
  self.assertTrue((m.ROOT/'state/storage.json').is_file())
 def test_failed_registration_removes_link_and_leaves_profile_absent(self):
  with patch.object(m,'disk_info',return_value=self.info),patch.object(m.subprocess,'run') as run,patch.object(m,'storage_check',side_effect=RuntimeError('gate failed')):
   run.return_value.returncode=1;self.assertRaises(RuntimeError,m.register_external,'EXTERNAL-UUID',str(self.volume),str(self.media))
  self.assertFalse((m.ROOT/'media').is_symlink());self.assertFalse((m.ROOT/'media').exists())
  self.assertFalse((m.ROOT/'state/storage.json').exists())
 def test_registration_cannot_replace_an_existing_library_directory(self):
  (m.ROOT/'media').mkdir();(m.ROOT/'media/keep.txt').write_text('keep')
  with patch.object(m,'disk_info',return_value=self.info),patch.object(m.subprocess,'run') as run:
   run.return_value.returncode=1;self.assertRaises(RuntimeError,m.register_external,'EXTERNAL-UUID',str(self.volume),str(self.media))
  self.assertEqual((m.ROOT/'media/keep.txt').read_text(),'keep')
class MdnsTests(unittest.TestCase):
 def test_disabled_does_not_query_network(self):
  with patch.object(m.subprocess,'run') as run:
   self.assertEqual(m.mdns_services({'enabled':False}),{});run.assert_not_called()
 def test_missing_network_withholds_aliases(self):
  with patch.object(m.subprocess,'run') as run:
   run.return_value.returncode=1
   self.assertEqual(m.mdns_services({'enabled':True,'interface':'en0'}),{})
 def test_changed_address_replaces_publication_command(self):
  with patch.object(m.subprocess,'run') as run:
   run.return_value.returncode=0;run.return_value.stdout='192.168.50.3\n'
   old=m.mdns_services({'enabled':True,'interface':'en0'})
   run.return_value.stdout='192.168.50.4\n'
   new=m.mdns_services({'enabled':True,'interface':'en0'})
   self.assertNotEqual(old,new)
   self.assertTrue(all(s['command'][-1]=='192.168.50.4' for s in new.values()))
 def test_bonjour_uses_standard_port_when_proxy_is_enabled(self):
  with patch.object(m.subprocess,'run') as run,patch.object(m,'proxy_services',return_value={'proxy-caddy':{}}):
   run.return_value.returncode=0;run.return_value.stdout='192.168.50.3\n'
   services=m.mdns_services({'enabled':True,'interface':'en1'})
   self.assertTrue(all(v['command'][5]=='80' for v in services.values()))
class BootAndLogTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.old_root=m.ROOT;self.old_plist=m.PLIST;self.old_daemon=m.DAEMON_PLIST
  m.ROOT=pathlib.Path(self.temp.name);m.PLIST=m.ROOT/'login.plist';m.DAEMON_PLIST=m.ROOT/'system.plist'
  (m.ROOT/'state').mkdir();(m.ROOT/'logs').mkdir()
 def tearDown(self):
  m.ROOT=self.old_root;m.PLIST=self.old_plist;m.DAEMON_PLIST=self.old_daemon;self.temp.cleanup()
 def test_boot_requires_headless(self):
  m.save_json(m.ROOT/'state/services.json',{'qbittorrent':{'command':['desktop']}})
  self.assertRaises(RuntimeError,m.prepare_boot)
 def test_boot_job_runs_as_user_without_aqua(self):
  import plistlib
  m.save_json(m.ROOT/'state/services.json',{'qbittorrent':{'command':['/apps/qbittorrent-nox']}})
  m.prepare_boot();job=plistlib.loads((m.ROOT/'state'/ (m.LABEL+'.boot.plist')).read_bytes())
  self.assertNotEqual(job['UserName'],'root');self.assertNotIn('LimitLoadToSessionType',job)
  self.assertEqual(job['EnvironmentVariables']['HOME'],str(pathlib.Path.home()))
 def test_log_rotation_preserves_open_descriptor(self):
  p=m.ROOT/'logs/test.log'
  with p.open('ab') as stream:
   stream.write(b'x'*(10*1024*1024));stream.flush();m.rotate_logs();stream.write(b'after');stream.flush()
  self.assertEqual(p.read_bytes(),b'after');self.assertEqual(pathlib.Path(str(p)+'.1').stat().st_size,10*1024*1024)
 def test_only_system_domain_is_selected(self):
  self.assertEqual(m.job_domain(),'system');m.DAEMON_PLIST.touch();self.assertEqual(m.job_domain(),'system')

if __name__ == '__main__':
 unittest.main()

class ProbeDeadlineTests(unittest.TestCase):
 def test_stalled_helper_returns_promptly_and_is_reaped(self):
  import time
  with patch.object(m, '_STORAGE_PROBE_CODE', 'import time; time.sleep(60)'), patch.object(m, '_STORAGE_PROBE_TIMEOUT', .05):
   start=time.monotonic()
   with self.assertRaisesRegex(RuntimeError, 'timed out'):
    m.bounded_storage_paths_check({})
   self.assertLess(time.monotonic()-start, 1.5)
   self.assertIsNone(m._STORAGE_PROBE)
 def test_unfinished_previous_probe_suppresses_new_process(self):
  from unittest.mock import Mock
  pending=Mock(); pending.poll.return_value=None
  with patch.object(m, '_STORAGE_PROBE', pending), patch.object(m.subprocess, 'Popen') as spawn:
   with self.assertRaisesRegex(RuntimeError, 'still blocked'):
    m.bounded_storage_paths_check({})
   spawn.assert_not_called()

class ProbeStorageSafetyTests(unittest.TestCase):
 def test_probe_failure_remains_storage_failure_during_pending_control(self):
  for message in ('Media filesystem verification timed out', 'Media filesystem verification is still blocked', 'Media filesystem verification failed'):
   self.assertTrue(m.is_storage_gate_failure(RuntimeError(message)))
