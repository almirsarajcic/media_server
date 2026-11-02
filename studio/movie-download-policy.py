#!/usr/bin/env python3
"""Configure a compact HD movie policy; private API snapshots permit rollback."""
import argparse
import copy
import datetime
import json
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path.home() / '.local/share/media-server'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Write settings; otherwise show current settings')
    parser.add_argument('--profile-id', type=int, action='append', required=True, help='Radarr profile ID to modify; repeat for multiple profiles')
    args = parser.parse_args()
    selected = set(args.profile_id)
    key = ET.parse(ROOT / 'state/radarr/config.xml').findtext('ApiKey')

    def api(path, method='GET', value=None):
        data = None if value is None else json.dumps(value).encode()
        request = urllib.request.Request('http://127.0.0.1:7878/api/v3/' + path, data=data,
                                        headers={'X-Api-Key': key, 'Content-Type': 'application/json'}, method=method)
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
            return json.loads(body) if body else None

    before = {name: api(name) for name in ('qualityprofile', 'qualitydefinition', 'customformat', 'config/indexer')}
    missing = selected - {p['id'] for p in before['qualityprofile']}
    if missing:
        parser.error('Selected profile IDs were not found')
    if not args.apply:
        print(json.dumps(before, indent=2))
        return
    receipt = ROOT / 'checks/movie-download-policy' / datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    receipt.mkdir(parents=True, mode=0o700)
    snapshot = receipt / 'before.json'
    snapshot.touch(mode=0o600)
    snapshot.write_text(json.dumps(before, indent=2))
    formats = before['customformat']
    yts = next((x for x in formats if x['name'] == 'Prefer YTS'), None)
    spec = {'name': 'YTS or YIFY', 'implementation': 'ReleaseTitleSpecification',
            'negate': False, 'required': False, 'fields': [{'name': 'value', 'value': r'\b(?:YTS|YIFY)\b'}]}
    value = {'name': 'Prefer YTS', 'includeCustomFormatWhenRenaming': False, 'specifications': [spec]}
    if yts:
        value['id'] = yts['id']
        yts = api('customformat/' + str(yts['id']), 'PUT', value)
    else:
        yts = api('customformat', 'POST', value)
    hd = next((x for x in formats if x['name'] == 'Prefer 1080p'), None)
    value = {'name': 'Prefer 1080p', 'includeCustomFormatWhenRenaming': False,
             'specifications': [{'name': '1080p', 'implementation': 'ResolutionSpecification',
                                 'negate': False, 'required': False, 'fields': [{'name': 'value', 'value': 1080}]}]}
    if hd:
        value['id'] = hd['id']
        hd = api('customformat/' + str(hd['id']), 'PUT', value)
    else:
        hd = api('customformat', 'POST', value)
    # Preserve profile identities so existing assignments remain valid.
    # Keep identities so existing movies, collections and import lists retain their references.
    for original in before['qualityprofile']:
        if original['id'] not in selected:
            continue
        profile = copy.deepcopy(original)
        leaves = []
        def flatten(items):
            for item in items:
                if item.get('quality'):
                    leaves.append(copy.deepcopy(item))
                else:
                    flatten(item['items'])
        flatten(profile['items'])
        allowed, disabled = [], []
        for item in leaves:
            q = item['quality']
            item['allowed'] = q['resolution'] in (720, 1080) and q['modifier'] == 'none'
            (allowed if item['allowed'] else disabled).append(item)
        profile['items'] = disabled + [{'id': 1100, 'name': 'Compact HD 720p / 1080p', 'allowed': True, 'items': allowed}]
        profile.update(cutoff=1100, minFormatScore=0, cutoffFormatScore=550, minUpgradeFormatScore=1)
        # Preserve pre-existing upgrade on/off choice.
        for fmt, score in ((yts, 500), (hd, 50)):
            current = next((x for x in profile['formatItems'] if x['format'] == fmt['id']), None)
            if current:
                current['score'] = score
            else:
                profile['formatItems'].append({'format': fmt['id'], 'name': fmt['name'], 'score': score})
        api('qualityprofile/' + str(profile['id']), 'PUT', profile)
    for original in before['qualitydefinition']:
        q = original['quality']
        if q['resolution'] not in (720, 1080) or q['modifier'] != 'none':
            continue
        value = copy.deepcopy(original)
        value.update(minSize=0, preferredSize=17 if q['resolution'] == 1080 else 10,
                     maxSize=35 if q['resolution'] == 1080 else 20)
        api('qualitydefinition/' + str(value['id']), 'PUT', value)
    config = copy.deepcopy(before['config/indexer'])
    config['maximumSize'] = 4096
    api('config/indexer', 'PUT', config)
    after = {name: api(name) for name in before}
    snapshot = receipt / 'after.json'
    snapshot.touch(mode=0o600)
    snapshot.write_text(json.dumps(after, indent=2))
    assert after['config/indexer']['maximumSize'] == 4096
    for p in after['qualityprofile']:
        if p['id'] not in selected:
            continue
        assert p['cutoff'] == 1100
        assert {i['format']: i['score'] for i in p['formatItems']}[yts['id']] == 500
        for item in p['items']:
            for leaf in item.get('items') or [item]:
                if leaf['allowed']:
                    q = leaf['quality']
                    assert q['resolution'] in (720, 1080) and q['modifier'] == 'none'
    print(json.dumps({'verified': True, 'receipt': str(receipt), 'profiles': sorted(selected), 'maximumSizeMiB': 4096}))


if __name__ == '__main__':
    main()
