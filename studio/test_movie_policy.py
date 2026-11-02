import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('movie_policy', Path(__file__).with_name('movie-download-policy.py'))
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class PolicyTests(unittest.TestCase):
    def test_dry_run_never_writes_and_rejects_unknown_profile(self):
        class Response:
            def __init__(self, request):
                self.request = request
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def read(self):
                name = self.request.full_url.rsplit('/api/v3/', 1)[1]
                return json.dumps({'qualityprofile': [{'id': 42}], 'qualitydefinition': [],
                                   'customformat': [], 'config/indexer': {}}[name]).encode()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / 'state/radarr/config.xml'
            config.parent.mkdir(parents=True)
            config.write_text('<Config><ApiKey>fixture</ApiKey></Config>')
            requests = []
            def open_request(request, timeout):
                requests.append(request)
                return Response(request)
            with patch.object(policy, 'ROOT', root), patch.object(policy.urllib.request, 'urlopen', side_effect=open_request):
                with patch.object(sys, 'argv', ['movie-download-policy.py', '--profile-id', '42']):
                    policy.main()
                self.assertTrue(requests)
                self.assertTrue(all(r.get_method() == 'GET' for r in requests))
                self.assertFalse((root / 'checks').exists())
                with patch.object(sys, 'argv', ['movie-download-policy.py', '--profile-id', '99', '--apply']):
                    with self.assertRaises(SystemExit):
                        policy.main()
                self.assertTrue(all(r.get_method() == 'GET' for r in requests))

    def test_apply_only_updates_selected_profiles_and_snapshots_first(self):
        import copy
        profile = lambda number: {'id': number, 'items': [
            {'quality': {'resolution': 1080, 'modifier': 'none'}, 'allowed': True},
            {'quality': {'resolution': 2160, 'modifier': 'none'}, 'allowed': True}],
            'formatItems': []}
        data = {'qualityprofile': [profile(42), profile(43)], 'qualitydefinition': [],
                'customformat': [], 'config/indexer': {'maximumSize': 0}}
        writes = []
        class Response:
            def __init__(self, value): self.value = value
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return json.dumps(self.value).encode()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / 'state/radarr/config.xml'
            config.parent.mkdir(parents=True)
            config.write_text('<Config><ApiKey>fixture</ApiKey></Config>')
            def open_request(request, timeout):
                path = request.full_url.rsplit('/api/v3/', 1)[1]
                if request.get_method() == 'GET': return Response(copy.deepcopy(data[path]))
                self.assertTrue(list((root / 'checks/movie-download-policy').glob('*/before.json')))
                value = json.loads(request.data)
                writes.append(path)
                if path == 'customformat':
                    value['id'] = len(data[path]) + 1
                    data[path].append(value)
                elif path.startswith('qualityprofile/'):
                    data['qualityprofile'] = [value if p['id'] == value['id'] else p for p in data['qualityprofile']]
                else: data[path] = value
                return Response(value)
            with patch.object(policy, 'ROOT', root), patch.object(policy.urllib.request, 'urlopen', side_effect=open_request), patch.object(sys, 'argv', ['policy', '--profile-id', '42', '--apply']):
                policy.main()
            self.assertIn('qualityprofile/42', writes)
            self.assertNotIn('qualityprofile/43', writes)
            self.assertEqual(data['qualityprofile'][1], profile(43))
            self.assertEqual(data['config/indexer']['maximumSize'], 4096)
            self.assertEqual(list((root / 'checks/movie-download-policy').glob('*/before.json'))[0].stat().st_mode & 0o777, 0o600)
