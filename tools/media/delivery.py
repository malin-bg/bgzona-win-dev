"""Single DEV build/accept/seal entry point. Never deploys or writes source files."""
import argparse
from io import BytesIO
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import urllib.parse
import urllib.request
import zipfile

from artifact_seal import checked_absolute, require, safe_path, seal, verify, inventory
from bridge import derive
from media_support import atomic, data, digest, fhash
from acceptance import validate
import resolve_input

REPOSITORY = 'malin-bg/bgzona-win-dev'
BASE = 'https://dev.bgzona.win/'


def read_lock(path):
    lock = json.loads(path.read_bytes().decode('utf-8-sig', 'strict'))
    return validate_lock(lock)


def validate_lock(lock):
    require(set(lock) == {'schema', 'repository', 'archive_name', 'archive_sha256', 'bytes',
                         'members', 'source_catalog_sha256', 'expected_files_sha256',
                         'snapshot', 'provider'}, 'LOCK_SCHEMA')
    require(lock['schema'] == 1 and lock['repository'] == REPOSITORY, 'LOCK_REPOSITORY')
    safe_path(lock['archive_name'])
    require('/' not in lock['archive_name'] and lock['archive_name'].endswith('.zip'), 'LOCK_NAME')
    for key in ('archive_sha256', 'source_catalog_sha256', 'expected_files_sha256'):
        require(isinstance(lock[key], str) and re.fullmatch('[0-9a-f]{64}', lock[key]), 'LOCK_SHA')
    require(type(lock['bytes']) is int and 0 < lock['bytes'] <= 500_000_000 and
            type(lock['members']) is int and 0 < lock['members'] <= 10000, 'LOCK_LIMITS')
    require(isinstance(lock['snapshot'], dict) and set(lock['snapshot']) ==
            {'published', 'kolaji', 'poslaniya', 'slides'} and
            all(type(v) is int and v >= 0 for v in lock['snapshot'].values()), 'LOCK_COUNTS')
    return lock


def get(url, limit):
    request = urllib.request.Request(url, headers={'User-Agent': 'bgzona-dev-input/1',
                        'Accept': 'application/vnd.github+json' if url.startswith('https://api.github.com/')
                        else 'application/octet-stream'})
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read(limit + 1)
    require(len(raw) <= limit, 'PROVIDER_SIZE_LIMIT')
    return raw


def obtain(lock, local_archive=None, *, provider_repository=REPOSITORY):
    if local_archive:
        require(os.environ.get('GITHUB_ACTIONS') != 'true', 'LOCAL_OVERRIDE_FORBIDDEN_IN_CI')
        raw = Path(local_archive).read_bytes()
    else:
        provider = lock['provider']
        require(isinstance(provider, dict) and set(provider) == {'release_id', 'asset_id', 'tag'},
                'PROVIDER_NOT_ACTIVATED: verified Release asset is required; no fallback')
        require(all(type(provider[k]) is int and provider[k] > 0 for k in ('release_id', 'asset_id'))
                and isinstance(provider['tag'], str) and bool(provider['tag']), 'PROVIDER_INVALID')
        api = f'https://api.github.com/repos/{provider_repository}/releases/{provider["release_id"]}'
        release = json.loads(get(api, 2_000_000))
        require(release['id'] == provider['release_id'] and release['tag_name'] == provider['tag']
                and release['draft'] is False and release['prerelease'] is False, 'PROVIDER_RELEASE')
        if provider_repository == resolve_input.CONTROL:
            require(release.get('immutable') is True, 'PROVIDER_RELEASE_IMMUTABLE')
        matches = [a for a in release['assets'] if a['id'] == provider['asset_id']]
        require(len(matches) == 1, 'PROVIDER_ASSET')
        asset = matches[0]
        url = (f'https://github.com/{provider_repository}/releases/download/' +
               urllib.parse.quote(provider['tag'], safe='') + '/' + lock['archive_name'])
        require(asset['name'] == lock['archive_name'] and asset['size'] == lock['bytes'] and
                asset['state'] == 'uploaded' and asset['browser_download_url'] == url, 'PROVIDER_IDENTITY')
        raw = get(url, lock['bytes'])
    require(len(raw) == lock['bytes'] and digest(raw) == lock['archive_sha256'], 'ARCHIVE_SHA_OR_SIZE')
    return raw


def unpack(raw, lock, destination, *, accepted=False):
    require(not destination.exists(), 'INPUT_DEST_EXISTS')
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        members = archive.infolist()
        require(len(members) == lock['members'] and
                sum(i.file_size for i in members) <= 500_000_000, 'ARCHIVE_MEMBERS_OR_SIZE')
        names = set()
        buffers = {}
        for info in members:
            safe_path(info.filename)
            require(not info.is_dir() and not info.flag_bits & 1 and
                    not stat.S_ISLNK(info.external_attr >> 16), 'ARCHIVE_MEMBER_TYPE')
            require(info.filename.casefold() not in names, 'ARCHIVE_DUPLICATE')
            names.add(info.filename.casefold())
            allowed = ('expected-files.json',) if accepted else ('expected-files.json', 'provenance.json')
            require(info.filename.startswith('artifact/') or info.filename in allowed, 'ARCHIVE_PRIVATE_OR_EXTRA')
            buffers[info.filename] = archive.read(info)
    require(digest(buffers['expected-files.json']) == lock['expected_files_sha256'] and
            digest(buffers['artifact/catalog.json']) == lock['source_catalog_sha256'], 'INPUT_METADATA_SHA')
    expected = json.loads(buffers['expected-files.json'].decode('utf-8-sig', 'strict'))
    require(isinstance(expected, dict) and {n for n in buffers if n.startswith('artifact/')} ==
            {'artifact/' + n for n in expected}, 'INPUT_EXACT_SET')
    for rel, sha in expected.items():
        safe_path(rel)
        require(digest(buffers['artifact/' + rel]) == sha, 'INPUT_FILE_SHA')
    destination.mkdir(parents=True)
    for rel, content in buffers.items():
        atomic(destination / rel, content)
    # Existing bridge validates catalog, identity, formats, revisions and references.
    manifest, states, catalog = derive(destination / 'artifact', expected)
    rows = manifest['items']
    counts = {'published': len(rows),
              'kolaji': sum(r['collection'] == 'kolaji' for r in rows),
              'poslaniya': sum(r['collection'] == 'poslaniya' for r in rows),
              'slides': sum(r['collection'] == 'kolaji' and r['slideshow'] for r in rows)}
    require(counts == lock['snapshot'], 'SNAPSHOT_COUNTS')
    return manifest, states


def run(command, log):
    q = subprocess.run(command, capture_output=True, text=True, encoding='utf8', errors='replace', timeout=180)
    atomic(log, (json.dumps(command, ensure_ascii=False) + '\n' + q.stdout + q.stderr).encode('utf8'))
    require(q.returncode == 0, 'BUILD_FAILED: ' + log.name)


def verify_c3_edit(accepted, registry):
    """Verify the exact independently accepted metadata edit before Hugo runs."""
    base_ledger='b3af46400dcca18296ff7b88314a864b0b24833d'
    base_assets='b293a4013a3b2969deeff0c833059f38d7107cef'
    base_witness='beb3b00b2d268bd0d8f415df126ce0f3c71e9c8e'
    ledger=resolve_input.provider(get,resolve_input.CONTROL,'git/commits/'+accepted['ledger_commit'])
    require([p['sha'] for p in ledger['parents']]==[base_ledger], 'C3_DEV_LEDGER_PARENT')
    w=resolve_input.provider(get,resolve_input.ASSETS,'git/commits/'+accepted['witness_commit'])
    require([p['sha'] for p in w['parents']]==[base_witness], 'C3_DEV_WITNESS_PARENT')
    old_raw=resolve_input.blob_at(get,resolve_input.ASSETS,'automation-state/registry.json',base_assets)
    require(digest(old_raw)=='263f4aae11bec845fa2ad3e57633a24a881db2a725d9f443a7a55979b063c6b7',
            'C3_DEV_BASE_REGISTRY')
    old=json.loads(old_raw)
    key='bgzona-m-00019'
    expected=old['items'] | {key:old['items'][key] | {
        'description': '\u0422\u0435\u0441\u0442\u043e\u0432\u043e \u043f\u043e\u0441\u043b\u0430\u043d\u0438\u0435 19 \u2013 \u0440\u0435\u0434\u0430\u043a\u0446\u0438\u044f C3.',
        'description_hash': '376a86f5bdfa39c95a695bdb8429fed4940ed66abdde79470cfb58054b65070a'}}
    require(registry['items']==expected and registry['counters']==old['counters'] and
            registry['library_id']==old['library_id'], 'C3_DEV_METADATA_ONLY')
    record=json.loads(resolve_input.blob_at(get,resolve_input.CONTROL,'records/00000003.json',
                                          accepted['ledger_commit']))
    require((record['index'],record['phase'],record['primary_base'],record['previous'])==
            (3,'staged',base_assets,'728b0a8a3ec296b6060c15b809eb56fff7f48cffd23d60be691ee21bbe8eebf9'),
            'C3_DEV_ACCEPTED_RECORD')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--hugo', default='hugo')
    parser.add_argument('--local-archive', type=Path, help='Isolated local verification ONLY; rejected in Actions')
    parser.add_argument('--accepted-cid', help='Exact reviewed DEV CID from input-trust.json')
    parser.add_argument('--c3-trust', type=Path, help='Verified ephemeral C3 DEV dispatch input')
    args = parser.parse_args()
    site = checked_absolute(args.site)
    parent = checked_absolute(args.work.parent)
    work = parent / args.work.name
    require(not work.exists() and not work.is_symlink() and
            not work.is_relative_to(site) and not site.is_relative_to(work) and
            not any((p / '.git').exists() for p in (parent, *parent.parents)), 'NEW_EXTERNAL_WORK_REQUIRED')
    accepted = None
    require(args.c3_trust is None or args.accepted_cid is not None, 'C3_DEV_CID_REQUIRED')
    if args.accepted_cid is not None:
        require(args.local_archive is None, 'CID_LOCAL_OVERRIDE_FORBIDDEN')
        trust = args.c3_trust if args.c3_trust else site / 'tools/media/input-trust.json'
        require(trust.is_file() and not trust.is_symlink() and trust.stat().st_size <= 8192, 'CID_INPUT_FILE')
        wire = trust.read_bytes()
        config = json.loads(wire)
        require(data(config)==wire, 'CID_INPUT_CANONICAL')
        accepted, registry = resolve_input.resolve(config, args.accepted_cid, get)
        if args.c3_trust:
            verify_c3_edit(accepted, registry)
        lock = validate_lock(accepted['input'])
        raw = obtain(lock, provider_repository=resolve_input.CONTROL)
    else:
        lock = read_lock(site / 'tools/media/input-lock.json')
        raw = obtain(lock, args.local_archive)
    work.mkdir()
    manifest, states = unpack(raw, lock, work / 'input', accepted=accepted is not None)
    if accepted is not None:
        resolve_input.verify_projection(work / 'input', registry)
    # Baseline is rebuilt from CURRENT content, not a historical article/file allowlist.
    atomic(work / 'baseline.toml', ('resourceDir = ' + json.dumps((work / 'baseline-resources').as_posix()) + '\n').encode())
    run([args.hugo, '--source', str(site), '--config', str(site / 'hugo.toml') + ',' + str(work / 'baseline.toml'),
         '--destination', str(work / 'baseline'), '--cacheDir', str(work / 'baseline-cache'),
         '--baseURL', BASE, '--environment', 'production', '--noBuildLock'], work / 'baseline.log')
    candidate = work / 'candidate'
    run([sys.executable, '-B', str(site / 'tools/media/build.py'), '--site', str(site),
         '--artifact', str(work / 'input/artifact'), '--expected-files', str(work / 'input/expected-files.json'),
         '--output-root', str(candidate), '--hugo', args.hugo], work / 'candidate.log')
    # Acceptance and seal are in one trusted caller; arbitrary PASS text is not consulted.
    validate(candidate, work / 'baseline', work / 'acceptance.json')
    require(json.loads((candidate / 'validated-manifest.json').read_bytes()) == manifest, 'MANIFEST_CHANGED')
    if accepted is not None:
        resolve_input.check_heads(get, accepted)
        version = candidate / 'public' / 'media-version.json'
        require(not version.exists() and not version.is_symlink(), 'CID_PUBLIC_PATH_EXISTS')
        atomic(version, data({'cid': args.accepted_cid, 'channel': 'dev',
                             'registry_sha256': accepted['registry_sha256']}))
    tree = seal(candidate / 'public', work / 'site-seal.json')
    verify(candidate / 'public', work / 'site-seal.json', tree)
    atomic(work / 'site-tree.sha256', (tree + '\n').encode('ascii'))
    receipt = {'status': 'ACCEPTED_SEALED_UNDEPLOYED', 'archive_sha256': lock['archive_sha256'],
               'tree_sha256': tree, 'snapshot': lock['snapshot'],
               'mode': 'LOCAL_INPUT_TEST' if args.local_archive else 'RELEASE_PROVIDER', 'deployment': False}
    if accepted is not None:
        receipt['cid'] = args.accepted_cid
        receipt['mode'] = 'INDEPENDENT_D3_CID'
    atomic(work / 'delivery-receipt.json', data(receipt))
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a', encoding='utf8') as stream:
            stream.write(f'### DEV acceptance PASS\n\n{lock["snapshot"]["published"]} media pages; '
                         f'{lock["snapshot"]["slides"]} slides. Site SHA-256: `{tree}`. '
                         'Current articles checked against this source build. No deployment yet.\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        print('DELIVERY_REJECT: ' + str(exc), file=sys.stderr)
        sys.exit(1)
