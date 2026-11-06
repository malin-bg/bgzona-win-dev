"""Resolve one owner-pinned DEV CID against GitHub's independent D3 ledger."""
from base64 import b64decode
from hashlib import sha1
import json
import re

from artifact_seal import require
from media_support import data, digest

CONTROL = 'malin-bg/bgzona-github-lab'
ASSETS = 'malin-bg/bgzona-assets'
LEDGER = 'heads/automation-ledger'
WITNESS = 'bgzona/witness'
LIMIT = 2_000_000


def hash_string(value, width):
    return type(value) is str and re.fullmatch(f'[0-9a-f]{{{width}}}', value) is not None


def provider(get, repo, path):
    suffix = '/' + path if path else ''
    return json.loads(get(f'https://api.github.com/repos/{repo}{suffix}', LIMIT))


def check_repo(get, name, expected_id):
    row = provider(get, name, '')
    require(type(expected_id) is int and expected_id > 0 and
            (row['full_name'], row['id'], row['private'], row['archived']) ==
            (name, expected_id, False, False), 'CID_REPOSITORY')


def head(get, repo, ref):
    row = provider(get, repo, 'git/ref/' + ref)
    oid = row['object']['sha']
    require(row['ref'] == 'refs/' + ref and row['object']['type'] == 'commit' and
            hash_string(oid, 40), 'CID_REF')
    return oid


def blob_at(get, repo, path, commit):
    row = provider(get, repo, f'contents/{path}?ref={commit}')
    require((row['path'], row['type'], row['encoding']) == (path, 'file', 'base64'), 'CID_BLOB')
    raw = b64decode(''.join(row['content'].splitlines()), validate=True)
    oid = sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
    require(row['sha'] == oid and row['size'] == len(raw), 'CID_BLOB')
    return raw


def check_record(record, raw, index, previous):
    require(set(record) == {'schema', 'index', 'previous', 'library_id', 'registry_seq', 'counters',
            'registry_sha256', 'primary_main', 'primary_witness', 'primary_base',
            'phase', 'operation', 'backup'} and record['schema'] == 1 and
            type(record['index']) is int and record['index'] == index and
            record['previous'] == previous and data(record) == raw, 'CID_LEDGER_RECORD')
    require(type(record['registry_seq']) is int and record['registry_seq'] >= 0 and
            hash_string(record['library_id'], 32) and
            hash_string(record['registry_sha256'], 64) and record['phase'] in ('accepted', 'staged') and
            all(hash_string(record[k], 40) for k in ('primary_main', 'primary_witness', 'primary_base')) and
            set(record['counters']) == {'kolaji', 'poslaniya'} and
            all(type(v) is int and 0 <= v <= 99999 for v in record['counters'].values()), 'CID_LEDGER_FIELDS')
    b = record['backup']
    require(set(b) == {'file', 'sha256', 'bytes', 'full'} and hash_string(b['sha256'], 64) and
            b['file'] == b['sha256'] + '.bundle' and type(b['bytes']) is int and b['bytes'] > 0 and
            type(b['full']) is bool and (index != 0 or b['full']), 'CID_LEDGER_BACKUP')
    require(record['operation'] == digest(data({'library': record['library_id'],
            'seq': record['registry_seq'], 'registry': record['registry_sha256']})), 'CID_LEDGER_OPERATION')


def verify_ledger(get, tip, genesis, expected):
    sha = tip
    chain = []
    for _ in range(64):
        row = provider(get, CONTROL, 'git/commits/' + sha)
        require(row['sha'] == sha, 'CID_LEDGER_COMMIT')
        chain.append(sha)
        parents = row['parents']
        if not parents:
            break
        require(len(parents) == 1 and hash_string(parents[0]['sha'], 40), 'CID_LEDGER_PARENT')
        sha = parents[0]['sha']
    else:
        raise RuntimeError('CID_LEDGER_LIMIT')
    previous = None
    old = None
    for i, commit in enumerate(reversed(chain)):
        path = f'records/{i:08d}.json'
        raw = blob_at(get, CONTROL, path, tip)
        require(raw == blob_at(get, CONTROL, 'anchor.json', commit) and
                (commit == tip or raw == blob_at(get, CONTROL, path, commit)), 'CID_LEDGER_HISTORY')
        row = json.loads(raw)
        check_record(row, raw, i, previous)
        previous = digest(raw)
        if old is None:
            require(previous == genesis, 'CID_LEDGER_GENESIS')
        else:
            require(row['library_id'] == old['library_id'] and row['registry_seq'] > old['registry_seq']
                    and all(row['counters'][k] >= old['counters'][k] for k in row['counters']),
                    'CID_LEDGER_REGRESSION')
        old = row
    require(previous == expected and old['phase'] == 'staged', 'CID_LEDGER_FINAL')
    return old


def check_heads(get, accepted):
    require(head(get, CONTROL, LEDGER) == accepted['ledger_commit'] and
            head(get, ASSETS, 'heads/main') == accepted['assets_tip'] and
            head(get, ASSETS, WITNESS) == accepted['witness_commit'], 'CID_STALE')


def protected_trees(get, commit):
    row = provider(get, ASSETS, 'git/commits/' + commit)
    tree = row['tree']['sha']
    require(row['sha'] == commit and hash_string(tree, 40), 'CID_AUTHORITY_TREE')
    root = provider(get, ASSETS, 'git/trees/' + tree)
    require(root['sha'] == tree and root['truncated'] is False, 'CID_AUTHORITY_TREE')
    paths = {x['path']: x['sha'] for x in root['tree'] if x['path'] in ('automation-state', 'objects')
             and x['type'] == 'tree' and x['mode'] == '040000' and hash_string(x['sha'], 40)}
    require(set(paths) == {'automation-state', 'objects'}, 'CID_AUTHORITY_TREE')
    return paths


def verify_materialized_authority(get, accepted):
    authority, tip = accepted['authority_commit'], accepted['assets_tip']
    if tip == authority:
        return
    comp = provider(get, ASSETS, f'compare/{authority}...{tip}')
    require(comp['status'] == 'ahead' and comp['ahead_by'] > 0 and
            comp['base_commit']['sha'] == comp['merge_base_commit']['sha'] == authority and
            protected_trees(get, authority) == protected_trees(get, tip), 'CID_AUTHORITY_DIVERGED')


def resolve(config, cid, get):
    """Consume an explicitly selected CID from reviewed DEV source only."""
    require(set(config) == {'schema', 'control_id', 'assets_id', 'ledger_genesis', 'cid', 'accepted'} and
            config['schema'] == 1 and hash_string(cid, 64) and cid == config['cid'] and
            hash_string(config['ledger_genesis'], 64), 'CID_TRUST')
    a = config['accepted']
    require(set(a) == {'channel', 'ledger_commit', 'record_sha256', 'authority_commit',
            'witness_commit', 'assets_tip', 'registry_sha256', 'input'} and a['channel'] == 'dev' and
            digest(data(a)) == cid and
            all(hash_string(a[k], 40) for k in ('ledger_commit', 'authority_commit', 'witness_commit', 'assets_tip')) and
            all(hash_string(a[k], 64) for k in ('record_sha256', 'registry_sha256')), 'CID_IDENTITY')
    check_repo(get, CONTROL, config['control_id'])
    check_repo(get, ASSETS, config['assets_id'])
    check_heads(get, a)
    r = verify_ledger(get, a['ledger_commit'], config['ledger_genesis'], a['record_sha256'])
    require((r['primary_main'], r['primary_witness'], r['registry_sha256']) ==
            (a['authority_commit'], a['witness_commit'], a['registry_sha256']), 'CID_AUTHORITY')
    verify_materialized_authority(get, a)
    registry = blob_at(get, ASSETS, 'automation-state/registry.json', a['authority_commit'])
    require(digest(registry) == a['registry_sha256'], 'CID_REGISTRY')
    reg = json.loads(registry)
    require(data(reg) == registry and reg['schema'] == 1 and
            (reg['library_id'], reg['seq'], reg['counters'], reg['transaction_status']) ==
            (r['library_id'], r['registry_seq'], r['counters'], 'staged'), 'CID_REGISTRY')
    w = json.loads(blob_at(get, ASSETS, 'witness.json', a['witness_commit']))
    require(set(w) == {'schema', 'authority', 'library_id', 'seq', 'counters', 'registry_sha256', 'previous'}
            and w['schema'] == 1 and (w['authority'], w['library_id'], w['seq'], w['counters'], w['registry_sha256']) ==
            (a['authority_commit'], r['library_id'], r['registry_seq'], r['counters'], a['registry_sha256']),
            'CID_WITNESS')
    check_heads(get, a)
    return a, reg


def verify_projection(directory, registry):
    """Match the existing Store.project catalog and object set to the D3 registry."""
    rows = []
    expected = {}
    for key, item in sorted(registry['items'].items()):
        require(key == item['id'], 'CID_CATALOG_ID')
        row = {k: item[k] for k in ('id', 'collection', 'page_url', 'state')}
        if item['state'] == 'published':
            rev = item['revisions'][-1]
            require(rev['number'] == item['desired_revision'], 'CID_CATALOG_REVISION')
            row.update(revision=rev['number'], original=rev['public_path'], sha256=rev['sha256'],
                       description=item['description'], slideshow=item['slideshow'])
            expected[rev['public_path'].lstrip('/')] = rev['sha256']
            if item['og']:
                og = item['og']
                path = f'{item["collection"]}/og/{key}-{og["sha256"][:12]}{og["ext"]}'
                row['og'] = '/' + path
                expected[path] = og['sha256']
        rows.append(row)
    cat = data({'schema': 1, 'items': rows})
    expected['catalog.json'] = digest(cat)
    require((directory / 'artifact' / 'catalog.json').read_bytes() == cat and
            json.loads((directory / 'expected-files.json').read_bytes()) == expected, 'CID_CATALOG_PROJECTION')

