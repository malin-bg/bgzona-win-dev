"""Reverify the same-run archived DEV output before the Pages action."""
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from real_dev_proof import LAB, DEV, REAL_REF, need, parse_dev_inputs, verify_workflow
from rollback_archive import verify, live_head


def main():
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_bytes())
    values = event['inputs']
    request = parse_dev_inputs(values)
    verify_workflow(request, values, event, os.environ, request['commit'], request['sid'])
    verify(Path(sys.argv[1]), request['commit'], request['sid'], request['seal'], count=None)
    live_head('https://github.com/' + LAB + '.git', REAL_REF, request['commit'])
    need(subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
         == os.environ['GITHUB_SHA'], 'DEV_CODE_CHECKOUT')
    live_head('https://github.com/' + DEV + '.git', 'refs/heads/main', os.environ['GITHUB_SHA'])


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('DEV_PAGES_ADMISSION_STOP') from None
