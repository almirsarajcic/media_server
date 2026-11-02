import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('watchlists', Path(__file__).with_name('imdb-watchlists.py'))
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class WatchlistTests(unittest.TestCase):
    def test_pagination_deduplicates_and_rejects_stalled_cursor(self):
        title = {'id': 'fixture-title', 'titleType': {'id': 'tvSeries'}, 'titleText': {'text': 'Fixture'}}
        def page(more, cursor):
            return {'data': {'predefinedList': {'titleListItemSearch': {'edges': [{'title': title}],
                    'pageInfo': {'hasNextPage': more, 'endCursor': cursor}}}}}
        with patch.object(bridge, 'request', side_effect=[page(True, 'next'), page(False, None)]):
            self.assertEqual(bridge.read_watchlist('fixture-user'), [title])
        with patch.object(bridge, 'request', side_effect=[page(True, 'next'), page(True, 'next')]):
            with self.assertRaisesRegex(RuntimeError, 'did not advance'):
                bridge.read_watchlist('fixture-user')

    def test_failed_refresh_preserves_last_good_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / 'state/sonarr/config.xml'
            config.parent.mkdir(parents=True)
            config.write_text('<Config><ApiKey>fixture</ApiKey></Config>')
            feed = root / 'checks/imdb-watchlists/fixture-user.json'
            feed.parent.mkdir(parents=True)
            previous = {'items': [{'tvdbId': 123}]}
            feed.write_text(json.dumps(previous))
            with patch.object(bridge, 'ROOT', root), patch.object(bridge, 'read_watchlist', side_effect=RuntimeError('fixture failure')):
                report = bridge.refresh({'lists': [{'userId': 'fixture-user'}]})
            self.assertIn('error', report['lists']['fixture-user'])
            self.assertEqual(json.loads(feed.read_text()), previous)

    def test_refresh_maps_series_and_deduplicates_without_movies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / 'state/sonarr/config.xml'
            config.parent.mkdir(parents=True)
            config.write_text('<Config><ApiKey>fixture</ApiKey></Config>')
            titles = [{'id': 'fixture-series', 'titleType': {'id': 'tvSeries'}, 'titleText': {'text': 'Fixture'}},
                      {'id': 'fixture-movie', 'titleType': {'id': 'movie'}, 'titleText': {'text': 'Fixture'}}]
            with patch.object(bridge, 'ROOT', root), patch.object(bridge, 'read_watchlist', return_value=titles), patch.object(bridge, 'resolve', return_value=123):
                bridge.refresh({'lists': [{'userId': 'fixture-user'}]})
            snapshot = json.loads((root / 'checks/imdb-watchlists/fixture-user.json').read_text())
            self.assertEqual(snapshot['items'], [{'tvdbId': 123}])
            self.assertEqual(snapshot['source_count'], 2)
            self.assertEqual(snapshot['unresolved'], [])
