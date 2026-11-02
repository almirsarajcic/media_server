"""Production regressions: boot-only startup, refreshed libraries, retained queue."""
import importlib.machinery
import importlib.util
import json
import pathlib
import plistlib
import pwd
import tempfile
import time
import threading
import time
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import Mock, patch

loader = importlib.machinery.SourceFileLoader('controller', str(pathlib.Path(__file__).with_name('media-server')))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.patcher = patch.object(m, 'ROOT', self.root / 'runtime')
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def test_regenerated_proxy_keeps_site_import_and_media_policy(self):
        state = m.ROOT / 'state'
        state.mkdir(parents=True)
        (state / 'home-access.json').write_text(json.dumps({'management_networks': ['192.168.1.0/24']}))
        config = m.proxy_config()
        self.assertIn('import proxy-sites/*.caddy', config)
        self.assertIn('http://jellyfin.local', config)
        self.assertIn('not remote_ip 127.0.0.1 ::1 192.168.1.0/24', config)

    def test_library_refresh_waits_for_ids_and_options_after_rename(self):
        unresolved = {'Locations': [str(m.ROOT/'media/movies')], 'Name': 'Movies'}
        resolved = dict(unresolved, ItemId='new-id', LibraryOptions={'EnableRealtimeMonitor': True})
        outside = {'Locations': ['/some/other/library']}
        api = Mock(side_effect=[[unresolved, outside], None, [resolved, outside]])
        self.assertEqual(m.ready_jellyfin_libraries(api), [resolved])
        self.assertEqual(api.call_args_list[1].args, ('/Library/Refresh', {}))

    def test_library_refresh_failure_is_explicit(self):
        api = Mock(side_effect=[[], None])
        self.assertRaisesRegex(RuntimeError, 'not ready', m.ready_jellyfin_libraries, api, 0)

    def test_start_cannot_fall_back_to_login_or_release_hold_without_boot_job(self):
        hold = m.ROOT/'state/maintenance'
        hold.parent.mkdir(parents=True)
        hold.touch()
        with patch.object(m, 'DAEMON_PLIST', self.root/'missing.plist'), patch.object(m, 'launchctl') as launch:
            self.assertRaisesRegex(RuntimeError, 'System boot service', m.install_startup)
            launch.assert_not_called()
        self.assertTrue(hold.exists())

    def test_failed_system_bootstrap_preserves_maintenance(self):
        hold = m.ROOT/'state/maintenance'
        hold.parent.mkdir(parents=True)
        hold.touch()
        plist = self.root/'boot.plist'
        script = self.root/'controller'
        script.touch()
        plist.write_bytes(plistlib.dumps({'Label': m.LABEL, 'UserName': pwd.getpwuid(m.os.getuid()).pw_name,
            'WorkingDirectory': str(m.ROOT), 'ProgramArguments': [m.PYTHON, str(script), 'run']}))
        with patch.object(m, 'DAEMON_PLIST', plist), patch.object(m, 'SCRIPT', script), \
                patch.object(m.subprocess, 'run'), patch.object(m, 'launchctl', side_effect=[Mock(returncode=1), RuntimeError('bootstrap failed')]):
            self.assertRaisesRegex(RuntimeError, 'bootstrap failed', m.install_startup)
        self.assertTrue(hold.exists())

    def boot_fixture(self):
        hold = m.ROOT/'state/maintenance'
        hold.parent.mkdir(parents=True)
        hold.touch()
        script = m.ROOT/'media-server'
        script.write_text('prior controller')
        plist = self.root/'boot.plist'
        job = {'Label': m.LABEL, 'UserName': pwd.getpwuid(m.os.getuid()).pw_name,
               'WorkingDirectory': str(m.ROOT), 'ProgramArguments': [m.PYTHON, str(script), 'run']}
        plist.write_bytes(plistlib.dumps(job))
        return hold, script, plist, job

    def test_wrong_boot_job_cannot_replace_controller_or_release_hold(self):
        hold, script, plist, job = self.boot_fixture()
        for changed in ({'ProgramArguments': [m.PYTHON, '/wrong/controller', 'run']},
                        {'UserName': 'root'}, {'LimitLoadToSessionType': 'Aqua'}):
            plist.write_bytes(plistlib.dumps({**job, **changed}))
            with self.subTest(changed=changed), patch.object(m, 'DAEMON_PLIST', plist), \
                    patch.object(m, 'SCRIPT', script), patch.object(m, 'launchctl') as launch:
                self.assertRaisesRegex(RuntimeError, 'does not match', m.install_startup)
                launch.assert_not_called()
            self.assertTrue(hold.exists())
            self.assertEqual(script.read_text(), 'prior controller')

    def test_loaded_job_must_use_current_script_before_releasing_hold(self):
        hold, script, plist, _ = self.boot_fixture()
        with patch.object(m, 'DAEMON_PLIST', plist), patch.object(m, 'SCRIPT', script), \
                patch.object(m, 'launchctl', return_value=Mock(returncode=0, stdout='\t/wrong/controller\n')):
            self.assertRaisesRegex(RuntimeError, 'does not run this controller', m.install_startup)
        self.assertTrue(hold.exists())

    def test_matching_boot_job_installs_complete_controller_and_releases_hold(self):
        hold, script, plist, _ = self.boot_fixture()
        with patch.object(m, 'DAEMON_PLIST', plist), patch.object(m, 'SCRIPT', script), \
                patch.object(m, 'launchctl', return_value=Mock(returncode=0, stdout='\t' + str(script) + '\n')):
            m.install_startup()
        self.assertFalse(hold.exists())
        self.assertEqual(script.read_bytes(), pathlib.Path(m.__file__).read_bytes())
        self.assertFalse(script.with_name(script.name + '.next').exists())

    def test_dependency_changes_require_fresh_confirmed_maintenance(self):
        with patch.object(m, 'launchctl', return_value=Mock(returncode=0)):
            for status in ({'phase': 'running', 'apps': {}, 'checked_at': time.time()},
                           {'phase': 'maintenance', 'apps': {'sonarr': 123}, 'checked_at': time.time()},
                           {'phase': 'maintenance', 'apps': {}, 'checked_at': time.time() - 60}):
                m.save_json(m.ROOT/'state/status.json', status)
                (m.ROOT/'state/maintenance').touch()
                with self.subTest(status=status): self.assertRaisesRegex(RuntimeError, 'Stop the media stack', m.require_stopped)
            m.save_json(m.ROOT/'state/status.json', {'phase': 'maintenance', 'apps': {}, 'checked_at': time.time()})
            m.require_stopped()

    def test_missing_native_settings_fail_before_staging_can_replace_accounts(self):
        binary = m.ROOT/'apps/qbittorrent-nox.app/Contents/MacOS/qbittorrent-nox'
        binary.parent.mkdir(parents=True)
        binary.touch()
        m.save_json(m.ROOT/'state/services.json', {'previous': {'command': ['keep']}})
        before = (m.ROOT/'state/services.json').read_bytes()
        with patch.object(m.subprocess, 'run') as run:
            self.assertRaisesRegex(RuntimeError, 'Restore native settings', m.prepare_native_services)
            run.assert_not_called()
        self.assertEqual((m.ROOT/'state/services.json').read_bytes(), before)
        self.assertFalse((m.ROOT/'state/bazarr/config/config.yaml').exists())

    def test_incomplete_app_restore_cannot_reduce_the_saved_service_set(self):
        binary = m.ROOT/'apps/qbittorrent-nox.app/Contents/MacOS/qbittorrent-nox'
        binary.parent.mkdir(parents=True)
        binary.touch()
        m.save_json(m.ROOT/'state/services.json', {'previous': {'command': ['keep']}})
        before = (m.ROOT/'state/services.json').read_bytes()
        with patch.object(m, 'require_rebuild_state'), patch.object(m.pathlib.Path, 'home', return_value=self.root), \
                patch.object(m.subprocess, 'run') as run:
            self.assertRaisesRegex(RuntimeError, 'All six native applications', m.prepare_native_services)
            run.assert_not_called()
        self.assertEqual((m.ROOT/'state/services.json').read_bytes(), before)

    def test_service_staging_cannot_fall_back_to_desktop_qbittorrent(self):
        with patch.object(m.subprocess, 'run') as run:
            self.assertRaisesRegex(RuntimeError, 'headless qBittorrent is required', m.prepare_native_services)
            run.assert_not_called()
        self.assertFalse((m.ROOT/'state/services.json').exists())

    def fixture_queue(self, explicit=True):
        profile = {'mountpoint': str(self.root/'volume')}
        receipt = {'paused_torrents': 1}
        if explicit:
            receipt['protected_torrent_hashes'] = ['aaa']
        else:
            original = self.root/'volume/media_server/qbittorrent/qBittorrent/BT_backup'
            original.mkdir(parents=True)
            (original/'aaa.fastresume').touch()
        m.save_json(m.ROOT/'checks/config-import.json', receipt)
        resume = m.ROOT/'state/qbittorrent/qBittorrent/data/BT_backup/aaa.fastresume'
        resume.parent.mkdir(parents=True)
        resume.write_bytes(m.bencode({b'paused': 1, b'auto_managed': 0}))
        queue = [{'hash': 'aaa', 'state': 'missingFiles', 'dlspeed': 0, 'upspeed': 0},
                 {'hash': 'bbb', 'state': 'downloading', 'dlspeed': 1000}]
        return profile, queue, resume

    def test_new_active_downloads_are_permitted_alongside_protected_queue(self):
        profile, queue, _ = self.fixture_queue()
        self.assertEqual(m.verify_retained_torrents(queue, profile), queue[:1])

    def test_existing_receipt_can_derive_identities_from_original_records(self):
        profile, queue, _ = self.fixture_queue(explicit=False)
        self.assertEqual(m.verify_retained_torrents(queue, profile), queue[:1])

    def test_protected_active_or_absent_records_fail(self):
        profile, queue, _ = self.fixture_queue()
        queue[0]['state'] = 'downloading'
        self.assertRaisesRegex(RuntimeError, 'no longer stopped', m.verify_retained_torrents, queue, profile)
        self.assertRaisesRegex(RuntimeError, 'missing from', m.verify_retained_torrents, queue[1:], profile)

    def test_protected_durable_resume_flags_are_required(self):
        profile, queue, resume = self.fixture_queue()
        resume.write_bytes(m.bencode({b'paused': 0, b'auto_managed': 1}))
        self.assertRaisesRegex(RuntimeError, 'not durably stopped', m.verify_retained_torrents, queue, profile)

    def test_explicit_owner_cleanup_allows_removed_original_records(self):
        profile, queue, _ = self.fixture_queue()
        m.save_json(m.ROOT/'checks/removed-torrents.json', {'removed_hashes': ['aaa']})
        self.assertEqual(m.verify_retained_torrents(queue[1:], profile), [])
        # Even a stopped removed record must not reappear silently.
        self.assertRaisesRegex(RuntimeError, 'reappeared', m.verify_retained_torrents, queue, profile)

    def test_documented_redownload_can_reuse_an_owner_removed_hash(self):
        profile, queue, resume = self.fixture_queue()
        m.save_json(m.ROOT/'checks/removed-torrents.json',
                    {'removed_hashes': ['aaa'], 'readded_hashes': ['aaa'],
                     'readded_provenance': {'aaa': 'Owner requested download; later Arr grab/import verified'}})
        queue[0]['state'] = 'uploading'
        queue[0]['upspeed'] = 100
        resume.unlink()
        self.assertEqual(m.verify_retained_torrents(queue, profile), [])

    def test_redownload_exception_cannot_exempt_a_record_never_removed(self):
        profile, queue, _ = self.fixture_queue()
        m.save_json(m.ROOT/'checks/removed-torrents.json', {'removed_hashes': [], 'readded_hashes': ['aaa']})
        self.assertRaisesRegex(RuntimeError, 'not a previously removed', m.verify_retained_torrents, queue, profile)

    def test_unknown_cleanup_identity_is_rejected(self):
        profile, queue, _ = self.fixture_queue()
        m.save_json(m.ROOT/'checks/removed-torrents.json', {'removed_hashes': ['unknown']})
        self.assertRaisesRegex(RuntimeError, 'unknown original identity', m.verify_retained_torrents, queue, profile)

    def test_home_network_rejects_public_and_overbroad_subnets(self):
        for value in ('0.0.0.0/0', '8.8.8.0/24', '127.0.0.0/8', '::/0', '192.168.50.3/24'):
            with self.subTest(value=value):
                self.assertRaises(ValueError, m.home_network, value)
        self.assertEqual(str(m.home_network('192.168.50.0/24')), '192.168.50.0/24')

    def test_password_free_proxy_gates_only_management_by_actual_peer_address(self):
        m.save_json(m.ROOT/'state/home-access.json', {'management_networks': ['192.168.50.0/24']})
        config = m.proxy_config()
        self.assertEqual(config.count('@outside not remote_ip 127.0.0.1 ::1 192.168.50.0/24'), 5)
        self.assertEqual(config.count('respond @outside "Home network only" 403'), 5)
        jellyfin = config.split('http://jellyfin.local {')[1].split('}')[0]
        self.assertNotIn('@outside', jellyfin)
        self.assertNotIn('X-Forwarded-For', config)

    def test_invalid_home_policy_cannot_generate_unrestricted_routes(self):
        for networks in (['0.0.0.0/0'], []):
            m.save_json(m.ROOT/'state/home-access.json', {'management_networks': networks})
            self.assertRaises(ValueError, m.proxy_config)

    def test_existing_remove_policy_changes_to_stop_without_changing_limits(self):
        import io
        import urllib.parse
        m.save_json(m.ROOT/'state/access.json', {'username': 'fixture', 'password': 'fixture'})
        m.save_json(m.ROOT/'state/storage.json', {})
        preferences = {'max_ratio_act': 1, 'dl_limit': 4096000, 'max_ratio': 10}
        writes = []
        class Opener:
            def open(self, request, timeout=None):
                url = request if isinstance(request, str) else request.full_url
                if url.endswith('/app/setPreferences'):
                    data = json.loads(urllib.parse.parse_qs(request.data.decode())['json'][0])
                    writes.append(data)
                    preferences.update(data)
                return io.BytesIO(json.dumps(preferences).encode())
        with patch.object(m, 'storage_check'), patch('urllib.request.build_opener', return_value=Opener()):
            m.ensure_download_import_safety()
            m.ensure_download_import_safety()
        self.assertEqual(writes, [{'max_ratio_act': 0}])
        self.assertEqual(preferences['dl_limit'], 4096000)
        self.assertEqual(preferences['max_ratio'], 10)


    def test_media_group_start_preserves_service_holds_and_restart_skips_them(self):
        configured = set(m.MEDIA_SERVICE_IDS)
        lifecycle = {'service_stops': ['sonarr'], 'media_stops': [], 'operation': None}
        stopped, started = m.apply_control_intent(lifecycle, 'media', 'stop', configured)
        self.assertEqual(set(stopped), configured)
        self.assertEqual(started, [])
        self.assertNotIn('sonarr', lifecycle['media_stops'])
        _, started_by_group = m.apply_control_intent(lifecycle, 'media', 'start', configured)
        self.assertEqual(set(started_by_group), configured - {'sonarr'})
        self.assertEqual(lifecycle['service_stops'], ['sonarr'])
        restarted, relaunched = m.apply_control_intent(lifecycle, 'media', 'restart', configured)
        self.assertEqual(set(restarted), configured - {'sonarr'})
        self.assertEqual(set(relaunched), configured - {'sonarr'})

    def test_service_start_releases_only_its_own_hold(self):
        lifecycle = {'service_stops': ['sonarr', 'radarr'], 'media_stops': ['jellyfin']}
        stopped, started = m.apply_control_intent(lifecycle, 'sonarr', 'start', set(m.MEDIA_SERVICE_IDS))
        self.assertEqual(stopped, [])
        self.assertEqual(started, ['sonarr'])
        self.assertEqual(lifecycle['service_stops'], ['radarr'])
        self.assertEqual(lifecycle['media_stops'], ['jellyfin'])

    def test_expired_control_request_is_rejected_without_changing_intent(self):
        lifecycle = {'service_stops': ['sonarr'], 'media_stops': [], 'operation': None}
        request = {'id': 'stale', 'service': 'radarr', 'action': 'stop',
                   'created_at': time.time() - 20, 'expires_at': time.time() - 10}
        result = m.accept_control_request(request, lifecycle, set(m.MEDIA_SERVICE_IDS), 123)
        self.assertIsNone(result)
        saved = m.load_lifecycle()
        self.assertEqual(saved['service_stops'], ['sonarr'])
        self.assertEqual(saved['media_stops'], [])
        self.assertIsNone(saved['operation'])
        self.assertEqual(saved['last_result']['status'], 'blocked')

    def test_graceful_control_timeout_remains_pending_and_never_force_kills(self):
        process = Mock(pid=4321)
        process.poll.return_value = None
        lifecycle = {'service_stops': [], 'media_stops': ['radarr'],
                     'operation': {'id': 'op', 'service': 'media', 'action': 'stop',
                                   'status': 'pending', 'phase': 'stopping',
                                   'stop_targets': ['radarr'], 'start_targets': [],
                                   'signalled': [], 'timeout_at': time.time() - 1}}
        children = {'radarr': (process, None)}
        with patch.object(m.os, 'killpg') as killpg, patch.object(m, 'process_group_exists', return_value=True):
            guard, _ = m.progress_control_operation(lifecycle, children, None)
        self.assertIsNone(guard)
        self.assertEqual(lifecycle['operation']['status'], 'pending')
        self.assertTrue(lifecycle['operation']['timed_out'])
        killpg.assert_called_once_with(4321, m.signal.SIGTERM)
        self.assertNotEqual(killpg.call_args.args[1], m.signal.SIGKILL)

    def test_graceful_bazarr_stop_uses_its_sigint_shutdown_handler(self):
        process = Mock(pid=4322)
        process.poll.return_value = None
        lifecycle = {'service_stops': ['bazarr'], 'media_stops': [],
                     'operation': {'id': 'bazarr-stop', 'service': 'bazarr', 'action': 'stop',
                                   'status': 'pending', 'phase': 'stopping',
                                   'stop_targets': ['bazarr'], 'start_targets': [],
                                   'signalled': [], 'timeout_at': time.time() + 60}}
        children = {'bazarr': (process, None)}
        with patch.object(m.os, 'killpg') as killpg, \
                patch.object(m, 'process_group_exists', return_value=True), \
                patch.object(m, 'service_health', return_value=False):
            m.progress_control_operation(lifecycle, children, None)
        killpg.assert_called_once_with(4322, m.signal.SIGINT)
        self.assertEqual(lifecycle['operation']['status'], 'pending')

    def test_all_intentionally_stopped_apps_are_not_reported_as_failed(self):
        lifecycle = {'service_stops': [], 'media_stops': list(m.MEDIA_SERVICE_IDS), 'operation': None}
        status = m.lifecycle_service_status(set(m.MEDIA_SERVICE_IDS), {}, {}, lifecycle, {})
        self.assertEqual(set(status), set(m.MEDIA_SERVICE_IDS))
        self.assertTrue(all(item['status'] == 'intentionally_stopped' for item in status.values()))
        self.assertTrue(all(item['intentional_stop'] for item in status.values()))
        self.assertTrue(all(item['endpoint_healthy'] is None for item in status.values()))

    def test_reaped_child_pid_is_never_signalled_again(self):
        process = Mock(pid=4321)
        process.poll.return_value = 0
        with patch.object(m.os, 'killpg') as killpg:
            children = {'radarr': (process, None)}
            m.stop_children(children)
        killpg.assert_not_called()
        self.assertEqual(children, {})


    def test_temporary_hold_releases_only_new_group_holds_after_real_boot(self):
        lifecycle = {
            'service_stops': ['sonarr'],
            'media_stops': ['radarr', 'bazarr', 'jellyfin'],
            'resume_on_boot': {'id': 'host-op', 'boot_id': 'boot-A',
                               'created_holds': ['jellyfin', 'qbittorrent']},
        }
        self.assertFalse(m.reconcile_resume_on_boot(lifecycle, 'boot-A'))
        self.assertIn('jellyfin', lifecycle['media_stops'])
        self.assertTrue(m.reconcile_resume_on_boot(lifecycle, 'boot-B'))
        self.assertEqual(lifecycle['media_stops'], ['bazarr', 'radarr'])
        self.assertEqual(lifecycle['service_stops'], ['sonarr'])
        self.assertIsNone(lifecycle['resume_on_boot'])

    def test_temporary_boot_marker_is_created_only_after_stop_completion(self):
        lifecycle = {'service_stops': ['sonarr'], 'media_stops': ['radarr'],
                     'operation': None, 'resume_on_boot': None}
        request = {'id': 'host-op', 'service': 'media', 'action': 'stop',
                   'resume_on_boot': True, 'created_at': time.time(),
                   'expires_at': time.time() + 60}
        with patch.object(m, 'host_boot_id', return_value='boot-A'), \
                patch.object(m, 'require_arr_idle'), patch.object(m, 'backup_is_active', return_value=False):
            guard = m.accept_control_request(request, lifecycle, set(m.MEDIA_SERVICE_IDS), 123)
        self.assertIsNotNone(guard)
        try:
            saved = m.load_lifecycle()
            self.assertIsNone(saved['resume_on_boot'])
            self.assertEqual(set(saved['operation']['temporary_created_holds']),
                             set(m.MEDIA_SERVICE_IDS) - {'sonarr', 'radarr'})
            m.finish_control_operation(saved, saved['operation'], guard, 'All target apps stopped.')
            marker = m.load_lifecycle()['resume_on_boot']
            self.assertEqual(marker['id'], 'host-op')
            self.assertEqual(marker['boot_id'], 'boot-A')
            self.assertEqual(set(marker['created_holds']), set(m.MEDIA_SERVICE_IDS) - {'sonarr', 'radarr'})
        finally:
            m.release_operation_guard(guard)

    def test_temporary_hold_rollback_restores_only_operation_created_apps(self):
        lifecycle = {
            'service_stops': ['sonarr'],
            'media_stops': ['bazarr', 'radarr', 'jellyfin'],
            'resume_on_boot': {'id': 'host-op', 'boot_id': 'boot-A',
                               'created_holds': ['radarr', 'jellyfin']},
            'operation': None,
        }
        request = {'id': 'rollback-op', 'service': 'media', 'action': 'start',
                   'restore_temporary': 'host-op', 'created_at': time.time(),
                   'expires_at': time.time() + 60}
        guard = m.accept_control_request(request, lifecycle, set(m.MEDIA_SERVICE_IDS), 123)
        self.assertIsNotNone(guard)
        try:
            saved = m.load_lifecycle()
            self.assertEqual(saved['media_stops'], ['bazarr'])
            self.assertEqual(set(saved['operation']['start_targets']), {'radarr', 'jellyfin'})
            self.assertIsNone(saved['resume_on_boot'])
            result = m.finish_control_operation(saved, saved['operation'], guard,
                                                'Temporary hold rollback completed.')
            self.assertIsNone(result)
            self.assertEqual(saved['last_result']['restored_temporary_hold_id'], 'host-op')
        finally:
            m.release_operation_guard(guard)


    def test_service_health_follows_jackett_cookie_redirect(self):
        class JackettHandler(BaseHTTPRequestHandler):
            saw_cookie = False

            def do_GET(self):
                if self.path == '/':
                    self.send_response(302)
                    self.send_header('Set-Cookie', 'anti-forgery=token; Path=/')
                    self.send_header('Location', '/dashboard')
                elif self.path == '/dashboard' and 'anti-forgery=token' in self.headers.get('Cookie', ''):
                    type(self).saw_cookie = True
                    self.send_response(200)
                else:
                    self.send_response(400)
                self.send_header('Content-Length', '0')
                self.end_headers()

            def log_message(self, _format, *_args):
                pass

        server = HTTPServer(('127.0.0.1', 0), JackettHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.dict(m.SERVICE_PORTS, {'jackett': server.server_port}):
                self.assertTrue(m.service_health('jackett', timeout=2))
            self.assertTrue(JackettHandler.saw_cookie)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
