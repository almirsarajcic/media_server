"""Recovery policy and metadata regressions; never contact public services."""
import importlib.machinery
import importlib.util
import io
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

loader = importlib.machinery.SourceFileLoader('solver_controller', str(pathlib.Path(__file__).with_name('media-server')))
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)


class SolverRecoveryTests(unittest.TestCase):
    def test_pair_requires_exact_version_and_executable_success(self):
        with patch.object(m.subprocess, 'run', side_effect=[Mock(stdout='Google Chrome for Testing 158.0.1.2'), Mock(stdout='ChromeDriver 158.0.1.3')]):
            with self.assertRaisesRegex(RuntimeError, 'versions differ'):
                m.solver_pair_version('browser', 'driver')
        with patch.object(m.subprocess, 'run', side_effect=subprocess.TimeoutExpired('browser', 10)):
            with self.assertRaises(subprocess.TimeoutExpired):
                m.solver_pair_version('browser', 'driver')

    def test_rollback_preserves_last_working_and_cooldown_persists(self):
        good = {'browser': '/good', 'driver': '/driver'}
        state = {'last_working': good}
        m.solver_failure_state(state, {'browser': '/bad'}, 'candidate failure', 1000)
        self.assertEqual(state['last_working'], good)
        self.assertFalse(state['provision_next'])
        self.assertEqual(state['retry_at'], 1300)
        m.solver_failure_state(state, good, 'rollback failure', 1300)
        self.assertTrue(state['provision_next'])
        self.assertEqual(state['retry_at'], 1900)
        self.assertEqual(m.solver_cooldown(100), 21600)

    def test_corrupt_recovery_state_is_bounded_and_does_not_select_invalid_paths(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(m, 'ROOT', pathlib.Path(tmp)):
            path = pathlib.Path(tmp) / 'recovery.json'
            for value in ([], {'last_working': 'bad'}, {'retry_at': 'tomorrow'}, {'retry_at': float('nan')},
                          {'last_working': {'browser': '/outside', 'driver': '/bad'}}, {'failures': -1}):
                path.write_text(json.dumps(value))
                state = m.solver_load_state(path)
                self.assertEqual(state['status'], 'cooldown')
                self.assertNotIn('last_working', state)
                self.assertLessEqual(state['retry_at'] - m.time.time(), 300)

    def test_metadata_requires_exact_official_arm64_artifacts(self):
        version = '158.0.1.2'
        downloads = {name: [{'platform': 'mac-arm64', 'url': f'https://storage.googleapis.com/chrome-for-testing-public/{version}/mac-arm64/{name}-mac-arm64.zip'}] for name in ('chrome', 'chromedriver')}
        data = {'channels': {'Stable': {'version': version, 'downloads': downloads}}}
        with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(data).encode())):
            self.assertEqual(m.solver_stable_metadata()[0], version)
        downloads['chrome'][0]['url'] = 'https://example.com/chrome.zip'
        with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(data).encode())):
            with self.assertRaisesRegex(RuntimeError, 'Unexpected'):
                m.solver_stable_metadata()


if __name__ == '__main__':
    unittest.main()
