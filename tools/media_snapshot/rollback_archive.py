import argparse, hashlib, json, os, subprocess, tarfile
from pathlib import Path
root='332a1cd0ffd95f86547aa64174b3af53c44977e2'
sid='f61fc13e43557f75df88eed7f39e4ab661c5097f60f8d3f9131fab22d9b36f81'
seal='1f9030617a351123d577f0db8009f5b6dadd79aac625839d7c96ea5e1a0934ba'
def need(ok, code):
    if not ok:
        raise ValueError(code)
def verify(path, expected_root, expected_sid, expected_seal, count=428):
    rows, seen, version = [], set(), None
    with tarfile.open(path, 'r:') as archive:
        for member in archive:
            name = member.name.removeprefix('./')
            if member.isdir() and name in ('', '.'):
                continue
            need(not any(x in name for x in (chr(92), ':', chr(0))) and all(x not in ('', '.', '..', '.git', '.github') for x in name.split('/')), 'PAGES_PATH')
            need(name.casefold() not in seen, 'PAGES_DUPLICATE')
            seen.add(name.casefold())
            if member.isdir():
                continue
            need(member.isreg() and not member.issparse(), 'PAGES_SPECIAL_FILE')
            with archive.extractfile(member) as stream:
                if name == 'media-version.json':
                    need(member.size <= 1024, 'PAGES_VERSION_SIZE')
                    raw = stream.read()
                    version = json.loads(raw)
                    digest = hashlib.sha256(raw).hexdigest()
                else:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            rows.append({'path':name,'bytes':member.size,'sha256':digest})
    need(version == {'schema':1,'channel':'dev','data_revision':expected_root,'snapshot':expected_sid}, 'PAGES_VERSION')
    data = json.dumps({'version':1,'algorithm':'sha256','files':sorted(rows,key=lambda x:x['path'])},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    need((count is None or len(rows) == count) and hashlib.sha256(data).hexdigest() == expected_seal, 'PAGES_SEAL')
def live_head(url, ref, expected):
    q=subprocess.run(['git','-c','credential.helper=','ls-remote','--exit-code','--refs',url,ref],capture_output=True,text=True,timeout=30,env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':os.devnull})
    need(q.returncode==0 and q.stdout.split()==[expected,ref], 'PAGES_REF_MOVED')


DEV = 'malin-bg/bgzona-win-dev'
DEV_ID = 1149689018
OWNER = 252877943
WORKFLOW = DEV + '/.github/workflows/hugo.yml@refs/heads/main'
MODE = 'rs4n-rollback-dev13-accept-archived-metadata'
ARCHIVE_BYTES = 26480640
ARCHIVE_SHA = '336f57a325e3fffdc421d5277b41955d089f928c3a109af3eb2937c926e8c1f2'


def admit(event, env):
    need(env.get('GITHUB_REPOSITORY') == DEV
         and env.get('GITHUB_REPOSITORY_ID') == str(DEV_ID)
         and env.get('GITHUB_REF') == 'refs/heads/main'
         and env.get('GITHUB_WORKFLOW_REF') == WORKFLOW
         and env.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'
         and env.get('GITHUB_RUN_ATTEMPT') == '1'
         and env.get('GITHUB_ACTOR_ID') == str(OWNER)
         and event.get('repository', {}).get('id') == DEV_ID
         and event.get('sender', {}).get('id') == OWNER,
         'ROLLBACK_AUTHORITY')
    need(event.get('inputs') == {'input_trust': MODE, 'accepted_cid': sid}, 'ROLLBACK_INPUT')


def stage(path):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size == ARCHIVE_BYTES,
         'ROLLBACK_ARCHIVE_SIZE')
    with path.open('rb') as f:
        need(hashlib.file_digest(f, 'sha256').hexdigest() == ARCHIVE_SHA, 'ROLLBACK_ARCHIVE_BYTES')
    verify(path, root, sid, seal)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    try:
        admit(json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_bytes()), os.environ)
        stage(args.archive)
        live_head('https://github.com/' + DEV + '.git', 'refs/heads/main', os.environ['GITHUB_SHA'])
    except (ValueError, OSError, KeyError, tarfile.TarError, subprocess.SubprocessError):
        raise SystemExit('DEV_ROLLBACK_STOP') from None
    print('DEV_ROLLBACK_ARCHIVE_VERIFIED')


if __name__ == '__main__':
    main()
