#!/usr/bin/env python3
"""Build a reproducible, provenance-preserving master from supported source exports."""
import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit


def signature(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def stable_id(prefix, value):
    return prefix + ':' + hashlib.sha256(value.encode()).hexdigest()[:24]


def handle(value):
    value = str(value or '').strip()
    if re.match(r'^(https?://)?(www\.|mobile\.)?(x\.com|twitter\.com)/', value, re.I):
        parsed = urlsplit(value if '://' in value else 'https://' + value)
        value = unquote(parsed.path).strip('/').split('/')[0]
    value = value.lstrip('@').lower()
    if value in {'home', 'intent', 'search', 'i', 'share', 'explore', 'settings'}:
        return None
    return value if re.fullmatch(r'[a-z0-9_]{1,15}', value) else None


def url(value):
    if not value:
        return None
    p = urlsplit(str(value).strip())
    if p.scheme not in {'https', 'http'} or not p.hostname:
        return None
    # Profile tracking/category query parameters are not identity.
    return urlunsplit(('https', p.netloc.lower(), p.path.rstrip('/'), '', ''))


def number(value):
    if value is None:
        return None
    text = str(value).strip().replace(',', '').replace('$', '').replace('−', '-')
    m = re.fullmatch(r'([+-]?\d+(?:\.\d+)?)\s*([KMBT]?)%?', text, re.I)
    if not m:
        return None
    result = float(m[1]) * {'': 1, 'K': 1e3, 'M': 1e6, 'B': 1e9, 'T': 1e12}[m[2].upper()]
    return int(result) if result.is_integer() else result


ALIASES = {
    'name': 'display_name', 'profile_name': 'display_name',
    'accountBasedIn': 'account_based_in', 'connectedVia': 'connected_via',
    'dateJoined': 'date_joined', 'followStatus': 'follow_status',
    'checkedAt': 'checked_at', 'scanned_at': 'scanned_at',
}


def normalize(raw):
    fields = {}
    handles, wallets, urls = set(), set(), set()
    issues = []
    for key, value in raw.items():
        if value is None or value == '':
            continue
        if key in {'handle', 'x_handle', 'x', 'x_url'} or (key in {'profileUrl', 'profile_url'} and re.match(r'https?://(?:www\.|mobile\.)?(?:x\.com|twitter\.com)/', str(value), re.I)):
            h = handle(value)
            if h:
                handles.add(h)
            else:
                issues.append({'field': key, 'value': value, 'reason': 'invalid_x_handle'})
        elif key in {'profileUrl', 'profile_url', 'pump_profile_url', 'profile'}:
            u = url(value)
            if u:
                urls.add(u)
                p = urlsplit(u)
                if p.hostname == 'pump.fun' and p.path.startswith('/profile/'):
                    address = p.path.split('/')[-1]
                    if re.fullmatch(r'[1-9A-HJ-NP-Za-km-z]{32,44}', address):
                        wallets.add(address)
            else:
                issues.append({'field': key, 'value': value, 'reason': 'invalid_profile_url'})
        elif key == 'wallet':
            if re.fullmatch(r'[1-9A-HJ-NP-Za-km-z]{32,44}', str(value)):
                wallets.add(value)
            else:
                issues.append({'field': key, 'value': value, 'reason': 'invalid_wallet'})
        elif key == 'followers':
            # Export concatenates the display name and follower count.
            prefix = str(raw.get('profile_name', ''))
            text = str(value)
            if prefix and text.startswith(prefix):
                text = text[len(prefix):]
            fields['followers'] = number(re.sub(r'\s*followers?$', '', text, flags=re.I).strip())
            if fields['followers'] is None:
                issues.append({'field': key, 'value': value, 'reason': 'invalid_number'})
        elif key in {'has_email', 'has_phone', 'has_social', 'visited'}:
            fields[key] = {'yes': True, 'no': False}.get(str(value).lower())
        elif key in {'email_addresses', 'phone_numbers', 'social_platforms'}:
            fields[key] = sorted(set(v.strip() for v in str(value).split(';') if v.strip()))
        else:
            fields[ALIASES.get(key, key)] = value
    return fields, sorted(handles), sorted(wallets), sorted(urls), issues


def read_source(path):
    """Yield kind, location, raw row, context; reject unknown schemas."""
    if path.suffix.lower() == '.csv':
        with path.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            columns = set(reader.fieldnames or [])
            if {'pump_profile_url', 'x_handle'} <= columns:
                kind = 'pump_following'
            elif {'profile_url', 'scanned_at'} <= columns:
                kind = 'profile_audit'
            else:
                raise ValueError(f'{path}: unsupported CSV columns {sorted(columns)}')
            for i, row in enumerate(reader, 2):
                if None in row or None in row.values():
                    raise ValueError(f'{path}:{i}: malformed CSV row')
                yield kind, f'row:{i}', row, {}
        return
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    context = {'exported_at': data.get('exportedAt')}
    if 'snapshots' in data:
        for i, snapshot in enumerate(data['snapshots']):
            for j, row in enumerate(snapshot['rows']):
                yield 'holding', f'/snapshots/{i}/rows/{j}', row, {
                    **context, **{k: v for k, v in snapshot.items() if k != 'rows'}}
    elif 'records' in data:
        for i, row in enumerate(data['records']):
            yield 'x_scout', f'/records/{i}', row, context
    elif data.get('app') == 'Keyword Glow':
        yield 'settings', '/settings', data['settings'], context
    else:
        raise ValueError(f'{path}: unsupported JSON schema')


def build(source_dir, output=None):
    files = sorted(p for p in source_dir.rglob('*') if p.suffix.lower() in {'.csv', '.json'} and (output is None or p.resolve() != output.resolve()))
    if not files:
        raise ValueError(f'No JSON/CSV sources found in {source_dir}')
    observations, settings, manifest, warnings = [], [], [], []
    for path in files:
        source = path.relative_to(source_dir).as_posix()
        count = 0
        for kind, location, raw, context in read_source(path):
            count += 1
            origin = {'source': source, 'location': location}
            if kind == 'settings':
                settings.append({'origin': origin, 'context': context, 'raw': raw})
                continue
            fields, handles, wallets, urls, issues = normalize(raw)
            for issue in issues:
                warnings.append({**origin, **issue})
            observations.append({'kind': kind, 'origin': origin, 'context': context,
                                 'fields': fields, 'x_handles': handles, 'wallets': wallets,
                                 'profile_urls': urls, 'raw': raw})
        manifest.append({'source': source, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'records': count})

    # Connected components over explicit identities, including cross-file bridges.
    parent = list(range(len(observations)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    seen = {}
    for i, obs in enumerate(observations):
        keys = (['x:' + h for h in obs['x_handles']] + ['wallet:' + w for w in obs['wallets']]
                + ['url:' + u for u in obs['profile_urls']])
        for key in keys:
            if key in seen:
                parent[root(i)] = root(seen[key])
            seen[key] = i
    groups = defaultdict(list)
    for i, obs in enumerate(observations):
        groups[root(i)].append(obs)
    entities, holdings = [], {}
    for group in groups.values():
        hs = sorted({h for o in group for h in o['x_handles']})
        ws = sorted({w for o in group for w in o['wallets']})
        us = sorted({u for o in group for u in o['profile_urls']})
        identity = ('x:' + hs[0]) if hs else ('wallet:' + ws[0]) if ws else ('url:' + us[0]) if us else signature(group[0]['origin'])
        eid = stable_id('profile', identity)
        values = defaultdict(dict)
        refs = []
        for obs in sorted(group, key=lambda o: (o['fields'].get('checked_at') or o['fields'].get('scanned_at') or o['context'].get('time') or o['context'].get('exported_at') or '', signature(o['origin']))):
            refs.append({'origin': obs['origin'], 'kind': obs['kind'], 'context': obs['context'], 'raw': obs['raw']})
            for key, value in obs['fields'].items():
                if value is not None and (obs['kind'] != 'holding' or key == 'display_name'):
                    values[key].pop(signature(value), None)
                    values[key][signature(value)] = value
            if obs['kind'] == 'holding':
                record = {'profile_id': eid, 'context': obs['context'], 'raw': obs['raw']}
                # Repeated exports of the same observation do not multiply balances.
                dedup_context = {k: v for k, v in obs['context'].items() if k != 'exported_at'}
                hid = stable_id('holding', signature([eid, dedup_context, obs['raw']]))
                if hid not in holdings:
                    metrics = {k: number(obs['raw'].get(k)) for k in ['final', 'marketcap', 'percentage', 'pnl', 'quantity', 'value']}
                    holdings[hid] = {'id': hid, **record, 'metrics': metrics, 'origins': []}
                holdings[hid]['origins'].append(obs['origin'])
        resolved = {k: (sorted({item for items in v.values() for item in items})
                        if k in {'email_addresses', 'phone_numbers', 'social_platforms'}
                        else list(v.values())[-1]) for k, v in sorted(values.items())}
        conflicts = {k: list(v.values()) for k, v in sorted(values.items()) if len(v) > 1}
        if len(hs) > 1:
            conflicts['x_handle'] = hs
        entities.append({'id': eid, 'x_handle': hs[0] if len(hs) == 1 else None,
                         'x_url': 'https://x.com/' + hs[0] if len(hs) == 1 else None,
                         'x_handles': hs, 'wallets': ws, 'profile_urls': us,
                         'fields': resolved, 'conflicts': conflicts, 'observations': refs})

    keywords = {}
    for config in settings:
        for profile in config['raw'].get('profiles', []):
            for keyword in profile.get('keywords', []):
                text = ' '.join(keyword['text'].split()).casefold()
                item = keywords.setdefault(text, {'text': text, 'variants': []})
                item['variants'].append({'profile_id': profile['id'], 'profile_name': profile['name'], 'keyword': keyword, 'origin': config['origin']})
    return {'schema_version': 1, 'sources': manifest,
            'summary': {'source_files': len(files), 'input_records': sum(m['records'] for m in manifest),
                        'profile_observations': len(observations), 'master_profiles': len(entities),
                        'merged_profile_observations': len(observations) - len(entities),
                        'holdings': len(holdings), 'keywords': len(keywords), 'warnings': len(warnings)},
            'profiles': sorted(entities, key=lambda e: e['id']),
            'holdings': sorted(holdings.values(), key=lambda h: h['id']),
            'keywords': [keywords[k] for k in sorted(keywords)], 'settings': settings, 'warnings': warnings}


def main():
    base = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, default=base / 'sources')
    parser.add_argument('--output', type=Path, default=base / 'master.json')
    args = parser.parse_args()
    try:
        result = build(args.sources, args.output)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(args.output.suffix + '.tmp')
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(args.output)
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, f'Error: {error}\n')
    print(json.dumps(result['summary'], indent=2))
    print(f'Wrote {args.output}')


if __name__ == '__main__':
    main()
