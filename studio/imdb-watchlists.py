#!/usr/bin/env python3
"""IMDb-to-Sonarr list bridge; served only on loopback."""
import argparse
import fcntl
import json
import os
import pathlib
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path.home() / '.local/share/media-server'
QUERY = '''query($userId: ID!, $after: String) {
 predefinedList(classType: WATCH_LIST, userId:$userId) {
  titleListItemSearch(first:250, after:$after, sort:{by:LIST_ORDER, order:ASC}) {
   pageInfo {hasNextPage endCursor}
   edges {title {id titleText {text} titleType {id}}}
  }
 }
}'''


def request(url, data=None, headers=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={'Content-Type': 'application/json', **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.next')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.chmod(0o600)
    os.replace(temp, path)


def read_watchlist(user_id):
    result, seen, after = [], set(), None
    for _ in range(40):
        payload = request('https://api.graphql.imdb.com/',
                          {'query': QUERY, 'variables': {'userId': user_id, 'after': after}},
                          {'x-imdb-client-name': 'imdb-web-next'})
        if payload.get('errors'):
            raise RuntimeError('IMDb rejected the read; check list privacy and upstream availability')
        node = (payload.get('data') or {}).get('predefinedList')
        if not node:
            raise RuntimeError('IMDb returned no watchlist')
        page = node['titleListItemSearch']
        for edge in page['edges']:
            title = edge['title']
            if title['id'] not in seen:
                seen.add(title['id'])
                result.append(title)
        if not page['pageInfo']['hasNextPage']:
            return result
        cursor = page['pageInfo'].get('endCursor')
        if not cursor or cursor == after or not page['edges']:
            raise RuntimeError('IMDb pagination did not advance')
        after = cursor
    raise RuntimeError('IMDb pagination exceeded safety limit; snapshot not replaced')


def resolve(title, key):
    imdb_id = title['id']
    url = 'http://127.0.0.1:8989/api/v3/series/lookup?'
    candidates = request(url + urllib.parse.urlencode({'term': 'imdb:' + imdb_id}),
                         headers={'X-Api-Key': key})
    exact = [c for c in candidates if c.get('imdbId') == imdb_id and c.get('tvdbId')]
    if len(exact) == 1:
        return exact[0]['tvdbId']
    # Fall back to TVMaze when Sonarr cannot resolve a unique match.
    try:
        show = request('https://api.tvmaze.com/lookup/shows?' + urllib.parse.urlencode({'imdb': imdb_id}))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    return (show.get('externals') or {}).get('thetvdb') or None


def refresh(config):
    key = ET.parse(ROOT / 'state/sonarr/config.xml').findtext('ApiKey')
    directory = ROOT / 'checks/imdb-watchlists'
    cache_path = directory / 'mappings.json'
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    report = {'checked_at': time.time(), 'lists': {}}
    for entry in config['lists']:
        uid = entry['userId']
        try:
            titles = read_watchlist(uid)
            shows, unresolved, ids = [], [], set()
            for title in titles:
                if title['titleType']['id'] not in ('tvSeries', 'tvMiniSeries'):
                    continue
                tvdb = config.get('tvdbOverrides', {}).get(title['id']) or cache.get(title['id'])
                if not tvdb:
                    tvdb = resolve(title, key)
                    if tvdb:
                        cache[title['id']] = tvdb
                if tvdb and tvdb not in ids:
                    ids.add(tvdb)
                    shows.append({'tvdbId': tvdb})
                elif not tvdb:
                    unresolved.append({'imdbId': title['id'], 'title': title['titleText']['text']})
            snapshot = {'updated_at': time.time(), 'items': shows, 'unresolved': unresolved,
                        'source_count': len(titles)}
            save(directory / (uid + '.json'), snapshot)
            report['lists'][uid] = {k: v for k, v in snapshot.items() if k != 'items'}
            report['lists'][uid]['series_count'] = len(shows)
        except Exception as error:
            # Keep the entire previous feed when any upstream or lookup request fails.
            report['lists'][uid] = {'error': type(error).__name__ + ': ' + str(error)}
    save(cache_path, cache)
    save(directory / 'status.json', report)
    print(json.dumps(report), flush=True)
    return report


def serve(config):
    allowed = {entry['userId'] for entry in config['lists']}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            uid = self.path.removeprefix('/').removesuffix('.json')
            if uid not in allowed:
                self.send_error(404)
                return
            path = ROOT / 'checks/imdb-watchlists' / (uid + '.json')
            if not path.exists():
                self.send_error(503, 'No successful IMDb snapshot yet')
                return
            body = json.dumps(json.loads(path.read_text())['items']).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', config['port']), Handler)
    def worker():
        while True:
            try:
                refresh(config)
            except Exception as error:
                print('Refresh failed: ' + str(error), flush=True)
            time.sleep(config['refreshSeconds'])
    threading.Thread(target=worker, daemon=True).start()
    server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    lock_path = ROOT / 'state/imdb-watchlists.lock'
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        configuration = json.loads((ROOT / 'state/imdb-watchlists.json').read_text())
        if args.once:
            report = refresh(configuration)
            raise SystemExit(int(any('error' in v for v in report['lists'].values())))
        serve(configuration)
