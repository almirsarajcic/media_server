"""Migration invariants: original authentication, history, paths, paused acquisition, rollback."""
import importlib.machinery
import importlib.util
import contextlib
import json
import pathlib
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

loader = importlib.machinery.SourceFileLoader('controller', str(pathlib.Path(__file__).with_name('media-server')))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)

class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = pathlib.Path(self.temp.name)
        self.old_root = m.ROOT
        m.ROOT = self.base / 'runtime'
        self.volume = self.base / 'volume'
        m.save_json(m.ROOT / 'state/storage.json', {'mode':'external','mountpoint':str(self.volume)})
        m.save_json(m.ROOT / 'state/access.json', {'username':'native','password':'fixture'})
        m.save_json(m.ROOT / 'state/jackett/Jackett/ServerConfig.json', {'APIKey':'native-key'})
        for app, table in [('sonarr','Series'), ('radarr','Movies')]:
            for base, username in [(m.ROOT/'state', 'native'), (self.volume/'media_server', 'old')]:
                path = base / app / (app+'.db')
                path.parent.mkdir(parents=True,exist_ok=True)
                with contextlib.closing(sqlite3.connect(path)) as db, db:
                    db.executescript('CREATE TABLE Users(Id INTEGER, Username TEXT, Password TEXT); CREATE TABLE '+table+'(Id INTEGER, Path TEXT, Monitored INTEGER); CREATE TABLE Indexers(Id INTEGER,Settings TEXT,EnableRss INTEGER,EnableAutomaticSearch INTEGER,EnableInteractiveSearch INTEGER); CREATE TABLE DownloadClients(Id INTEGER,Implementation TEXT,Settings TEXT,Enable INTEGER); CREATE TABLE History(Id INTEGER,Data TEXT);')
                    db.execute('insert into Users values(1,?,?)',(username,username+'-password-hash'))
                    db.execute('insert into '+table+' values(7,?,1)',('/data/movies/Test',))
                    db.execute('insert into Indexers values(1,?,1,1,1)',(json.dumps({'baseUrl':'http://jackett:9117/api/v2.0/indexers/1337x/results/torznab/','apiKey':'old'}),))
                    db.execute('insert into DownloadClients values(1,?,?,1)',('QBittorrent',json.dumps({'host':'qbittorrent','movieCategory':'radarr'})))
                    db.execute('insert into History values(4,?)',(json.dumps({'path':'/data/movies/Test'}),))
                    db.execute('create table Collections(RootFolderPath TEXT)')
                    db.execute('insert into Collections values(?)',('/movies',))
        self.bt=self.volume/'media_server/qbittorrent/qBittorrent/BT_backup'
        self.bt.mkdir(parents=True)
        for n in range(5):
            (self.bt/(str(n)+'.fastresume')).write_bytes(m.bencode({b'paused':0,b'save_path':b'/data/downloads',b'qBt-category':b'radarr'}))
            (self.bt/(str(n)+'.torrent')).write_bytes(b'fixture')
    def tearDown(self):
        m.ROOT=self.old_root
        self.temp.cleanup()
    def run_import(self):
        with patch.object(m,'storage_check'),patch.object(m,'launchctl') as run:
            run.return_value.returncode=1
            m.import_configs()
    def test_import_preserves_history_login_and_stops_acquisition(self):
        self.run_import()
        with contextlib.closing(sqlite3.connect(m.ROOT/'state/radarr/radarr.db')) as db:
            self.assertEqual(db.execute('select Username from Users').fetchone()[0],'old')
            self.assertEqual(db.execute('select Id,Monitored from Movies').fetchone(),(7,0))
            self.assertEqual(db.execute('select Enable from DownloadClients').fetchone()[0],0)
            self.assertEqual(db.execute('select EnableRss,EnableAutomaticSearch,EnableInteractiveSearch from Indexers').fetchone(),(0,0,0))
            indexer = json.loads(db.execute('select Settings from Indexers').fetchone()[0])
            self.assertEqual(indexer['baseUrl'],'http://127.0.0.1:9117/api/v2.0/indexers/1337x/results/torznab/')
            self.assertEqual(db.execute('select RootFolderPath from Collections').fetchone()[0],str(m.ROOT/'media/movies'))
            self.assertIn(str(m.ROOT/'media/movies'),db.execute('select Data from History').fetchone()[0])
        queue=list((m.ROOT/'state/qbittorrent/qBittorrent/data/BT_backup').glob('*.fastresume'))
        self.assertEqual(len(queue),5)
        for record in queue:
            values=m.bdecode(record.read_bytes())
            self.assertEqual(values[b'paused'],1)
            self.assertEqual(values[b'save_path'],str(m.ROOT/'media/downloads').encode())
        self.assertTrue((m.ROOT/'checks/config-import.json').exists())
    def test_backup_copies_and_checks_sqlite_outside_internal_runtime(self):
        m.save_json(m.ROOT/'checks/removed-torrents.json', {'removed_hashes': ['owner-deleted']})
        with patch.object(m,'storage_check'), patch.object(m,'SCRIPT',pathlib.Path(__file__).with_name('media-server')):
            m.backup_state()
        snapshots=list((self.volume/'media-server-backups').glob('*/complete.json'))
        self.assertEqual(len(snapshots),1)
        target=snapshots[0].parent/'state/radarr/radarr.db'
        with contextlib.closing(sqlite3.connect(target)) as db:
            self.assertEqual(db.execute('pragma integrity_check').fetchone()[0],'ok')
        self.assertEqual(target.stat().st_mode & 0o777,0o600)
        receipt = snapshots[0].parent/'checks/removed-torrents.json'
        self.assertEqual(json.loads(receipt.read_text()), {'removed_hashes': ['owner-deleted']})
        self.assertEqual(receipt.stat().st_mode & 0o777,0o600)

    def test_failed_backup_resume_does_not_restore_deleted_settings_from_partial(self):
        partial = self.volume/'media-server-backups/2026-10-15T000000.partial'
        (partial/'state').mkdir(parents=True)
        (partial/'state/deleted-settings.json').write_text('{"removed":true}')
        with patch.object(m,'storage_check'), patch.object(m,'SCRIPT',pathlib.Path(__file__).with_name('media-server')), \
                patch.object(m.time,'strftime',return_value='2026-10-15T000000'):
            m.backup_state(force=True)
        finished = partial.with_name('2026-10-15T000000')
        self.assertTrue((finished/'complete.json').exists())
        self.assertFalse((finished/'state/deleted-settings.json').exists())
        self.assertTrue((finished/'state/radarr/radarr.db').exists())

    def test_settings_backup_excludes_regenerable_cover_art_and_preserves_live_files(self):
        cover = m.ROOT/'state/radarr/MediaCover/1/poster.jpg'
        cover.parent.mkdir(parents=True)
        cover.write_bytes(b'cached artwork')
        with patch.object(m,'storage_check'), patch.object(m,'SCRIPT',pathlib.Path(__file__).with_name('media-server')):
            m.backup_state()
        finished = next((self.volume/'media-server-backups').glob('*/complete.json')).parent
        self.assertTrue((finished/'state/radarr/radarr.db').exists())
        self.assertFalse((finished/'state/radarr/MediaCover').exists())
        self.assertEqual(cover.read_bytes(),b'cached artwork')

    def test_simultaneous_backup_cannot_modify_another_writers_snapshot(self):
        import fcntl
        lock = m.ROOT/'state/backup.lock'
        with lock.open('a') as other, patch.object(m,'storage_check') as gate:
            fcntl.flock(other,fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertRaisesRegex(RuntimeError,'already in progress',m.backup_state,True)
            gate.assert_not_called()

    def test_backup_retention_uses_completion_time_instead_of_folder_name(self):
        today = time.strftime('%Y-%m-%d')
        base = self.volume/'media-server-backups'
        for n in range(7):
            m.save_json(base/(today+'T00000'+str(n))/'complete.json',
                        {'created_at':time.time()-86400-n})
        with patch.object(m,'storage_check'), patch.object(m,'SCRIPT',pathlib.Path(__file__).with_name('media-server')):
            m.backup_state()
        self.assertTrue((base/today/'complete.json').exists())
        self.assertFalse((base/(today+'T000006')).exists())
        self.assertEqual(len(list(base.glob('*/complete.json'))),7)

    def test_manual_backup_satisfies_daily_backup_even_without_daily_folder(self):
        base = self.volume/'media-server-backups'
        saved = base/'manual-snapshot/complete.json'
        m.save_json(saved,{'created_at':time.time()})
        with patch.object(m,'storage_check'), patch.object(m,'SCRIPT',pathlib.Path(__file__).with_name('media-server')):
            m.backup_state()
        self.assertEqual(list(base.glob('*/complete.json')),[saved])

    def test_transfer_preferences_convert_units_preserve_native_auth_and_import_once(self):
        import io
        import urllib.parse
        original = self.volume/'media_server/qbittorrent/qBittorrent/qBittorrent.conf'
        original.write_text('[BitTorrent]\nSession\\GlobalDLSpeedLimit=4000\nSession\\GlobalUPSpeedLimit=100\nSession\\GlobalMaxRatio=10\nSession\\QueueingSystemEnabled=true\nSession\\UseAlternativeGlobalSpeedLimit=false\n[Preferences]\nWebUI\\Password=source-secret\nBittorrent\\MaxRatioAction=1\n')
        preferences = {'web_ui_password':'native-secret','save_path':'native-path'}
        calls = []
        class Opener:
            def open(self, request, timeout=None):
                url = request if isinstance(request,str) else request.full_url
                calls.append(url)
                if url.endswith('/app/setPreferences'):
                    data = urllib.parse.parse_qs(request.data.decode())
                    preferences.update(json.loads(data['json'][0]))
                return io.BytesIO(json.dumps(preferences).encode() if url.endswith('/app/preferences') else b'')
        with patch.object(m,'storage_check'),patch('urllib.request.build_opener',return_value=Opener()):
            m.restore_download_preferences()
            self.assertEqual(preferences['dl_limit'],4096000)
            self.assertEqual(preferences['up_limit'],102400)
            self.assertEqual(preferences['max_ratio'],10)
            self.assertTrue(preferences['max_ratio_enabled'])
            self.assertEqual(preferences['max_ratio_act'],0)
            self.assertEqual(preferences['web_ui_password'],'native-secret')
            self.assertEqual(preferences['save_path'],'native-path')
            count = len(calls);preferences['dl_limit']=999
            m.restore_download_preferences()
            self.assertEqual(len(calls),count)
            self.assertEqual(preferences['dl_limit'],999)

    def test_restore_original_logins_keeps_native_api_keys_and_saves_rollback(self):
        import xml.etree.ElementTree as ET
        m.save_json(m.ROOT/'state/status.json',{'phase':'maintenance','apps':{},'checked_at':time.time()})
        (m.ROOT/'state/maintenance').touch()
        for app in ('sonarr','radarr'):
            (m.ROOT/'state'/app/'config.xml').write_text('<Config><ApiKey>native-key</ApiKey><InstanceName>'+app.title()+' Temporary</InstanceName></Config>')
        with patch.object(m,'storage_check'): m.restore_original_logins()
        receipt=json.loads((m.ROOT/'checks/original-logins-restored.json').read_text())
        for app in ('sonarr','radarr'):
            with contextlib.closing(sqlite3.connect(m.ROOT/'state'/app/(app+'.db'))) as db:
                self.assertEqual(db.execute('select Username,Password from Users').fetchone(),('old','old-password-hash'))
            with contextlib.closing(sqlite3.connect(pathlib.Path(receipt['backup'])/(app+'.db'))) as db:
                self.assertEqual(db.execute('select Username from Users').fetchone()[0],'native')
            config=ET.parse(m.ROOT/'state'/app/'config.xml')
            self.assertEqual(config.findtext('ApiKey'),'native-key')
            self.assertEqual(config.findtext('InstanceName'),app.title())

    def test_incomplete_queue_rolls_back_all_native_state(self):
        before=(m.ROOT/'state/radarr/radarr.db').read_bytes()
        (self.bt/'0.fastresume').unlink()
        self.assertRaises(RuntimeError,self.run_import)
        self.assertEqual((m.ROOT/'state/radarr/radarr.db').read_bytes(),before)
        self.assertFalse((m.ROOT/'checks/config-import.json').exists())

if __name__=='__main__': unittest.main()
