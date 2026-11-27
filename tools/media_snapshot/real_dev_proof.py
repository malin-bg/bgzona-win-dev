"""Admit a DEV workflow dispatch using only independent public GitHub metadata."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

LAB = 'malin-bg/bgzona-github-lab'
DEV = 'malin-bg/bgzona-win-dev'
OWNER = 252877943
DEV_APP = 353092585
# Pin the reviewed Lab commit before staged setup. An unset pin denies admission.
LAB_CODE_PIN = 'd3c6cb24f3b12438d4911b3f5e0b632ce95989b0'
REAL_ROOT = '05cfdeb41ca116dc07614906fbbdee9b3a597745'
REAL_REF = 'refs/heads/publisher-data'


def need(value, code):
    if not value:
        raise ValueError(code)


def proof_name(trace, commit, sid, seal):
    """All components are public correlation or sanitized output values."""
    try:
        value = UUID(hex=trace)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("TRACE_FORMAT") from None
    need(value.version == 4 and value.hex == trace, "TRACE_FORMAT")
    for x, size in ((commit, 40), (sid, 64), (seal, 64)):
        need(isinstance(x, str) and re.fullmatch(f"[a-f0-9]{{{size}}}", x), "PUBLIC_IDENTITY")
    return f"real-dev-{trace}-{commit}-{sid}-{seal}"


def parse_dev_inputs(values):
    need(isinstance(values, dict) and set(values) == {"accepted_cid", "input_trust"}, "DEV_INPUT_FIELDS")
    raw = values["input_trust"]
    need(isinstance(raw, str), "DEV_INPUT_FORMAT")
    m = re.fullmatch(r"rs4n-real:([1-9][0-9]*):real-dev-([a-f0-9]{32})-([a-f0-9]{40})-([a-f0-9]{64})-([a-f0-9]{64})", raw)
    need(m is not None and values["accepted_cid"] == m[4], "DEV_INPUT_FORMAT")
    lab, trace, commit, sid, seal = m.groups()
    proof_name(trace, commit, sid, seal)
    return {"run_id": int(lab), "trace": trace, "commit": commit, "sid": sid, "seal": seal}


def admit_dev(event, request, public, trusted_lab_sha):
    """Use independently fetched API results, never API objects from a dispatch."""
    need(event.get("repository_id") == 1149689018 and event.get("repository") == DEV
         and event.get("actor_id") == DEV_APP and event.get("attempt") == 1
         and event.get("ref") == "refs/heads/main" and event.get("event") == "workflow_dispatch",
         "DEV_AUTHORITY")
    run, jobs, artifacts = (public[k] for k in ("run", "jobs", "artifacts"))
    need(run.get("id") == request["run_id"] and run.get("workflow_id") == 408732936
         and run.get("head_branch") == "automation-control"
         and run.get("head_sha") == trusted_lab_sha
         and run.get("path") == ".github/workflows/shared-media.yml"
         and run.get("event") == "workflow_dispatch" and run.get("run_attempt") == 1
         and run.get("status") == "completed" and run.get("conclusion") == "success"
         and run.get("actor", {}).get("id") == OWNER
         and run.get("triggering_actor", {}).get("id") == OWNER
         and all(run.get(key, {}).get("id") == 1426765395
                 and run.get(key, {}).get("full_name") == LAB
                 for key in ("repository", "head_repository")),
         "LAB_AUTHORITY")
    need(len(jobs) == len({job["name"] for job in jobs}), "DUPLICATE_LAB_JOB")
    details = {j["name"]:j["conclusion"] for j in jobs}
    need(all(details.get(name) == "success" for name in ("h1-export","h1-write","h1-consumer","h1-dispatch-dev")),
         "LAB_STAGE_RESULT")
    identity = proof_name(request["trace"], request["commit"], request["sid"], request["seal"])
    matches = [a for a in artifacts if a.get("name", "").startswith("real-dev-")]
    need(len(matches) == 1 and matches[0].get("name") == identity, "ARTIFACT_BINDING")
    dev_run = event.get("run_id")
    need(type(dev_run) is int and dev_run > 0, "DEV_RUN_ID")
    admission = [a for a in artifacts if a.get("name", "").startswith("dev-admitted-")]
    need(len(admission) == 1 and admission[0].get("name") == f"dev-admitted-{dev_run}",
         "DEV_DISPATCH_RUN_BINDING")
    for match in (matches[0], admission[0]):
        run_meta = match.get("workflow_run", {})
        need(match.get("expired") is False and type(match.get("id")) is int
             and match["id"] > 0 and re.fullmatch("sha256:[a-f0-9]{64}", match.get("digest", ""))
             and run_meta.get("id") == run["id"] and run_meta.get("head_sha") == trusted_lab_sha
             and run_meta.get("repository_id") == 1426765395
             and run_meta.get("head_repository_id") == 1426765395
             and run_meta.get("head_branch") == "automation-control", "ARTIFACT_PROVENANCE")
    need(matches[0]["id"] != admission[0]["id"], "ARTIFACT_PROVENANCE")
    need(public["head"] == request["commit"] and public["sid"] == request["sid"],
         "PUBLIC_HEAD_OR_SID_MOVED")
    return request["seal"]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def read_api(repository, endpoint):
    token = os.environ.get('BGZONA_DEV_API_TOKEN')
    need(token, 'GITHUB_TOKEN_REQUIRED')
    url = 'https://api.github.com/repos/' + repository + endpoint
    request = Request(url, headers={'Accept':'application/vnd.github+json',
                                   'Authorization':'Bearer ' + token,
                                   'User-Agent':'BGZONA-DEV-admission'})
    with build_opener(NoRedirect).open(request, timeout=15) as response:
        return json.load(response)


def complete_rows(repository, endpoint, parameter):
    data = read_api(repository, endpoint + ('&' if '?' in endpoint else '?') + 'per_page=100')
    rows = data.get(parameter)
    need(isinstance(rows, list) and len(rows) == data.get('total_count'),
         'INCOMPLETE_GITHUB_EVIDENCE')
    return rows


def verify_workflow(request, values, event, env, actual_head, actual_sid):
    need(LAB_CODE_PIN is not None and re.fullmatch('[a-f0-9]{40}', LAB_CODE_PIN), 'LAB_PIN_UNSET')
    need(event.get('ref') in ('main', 'refs/heads/main')
         and event.get('repository', {}).get('id') == 1149689018
         and event.get('sender', {}).get('id') == DEV_APP
         and env.get('GITHUB_WORKFLOW_REF') == DEV+'/.github/workflows/hugo.yml@refs/heads/main'
         and re.fullmatch('[a-f0-9]{40}',env.get('GITHUB_SHA',''))
         and env.get('H1_WORKFLOW_SHA') == env.get('GITHUB_SHA'), 'DEV_EVENT_BINDING')
    path = '/actions/runs/' + str(request['run_id'])
    deadline = time.monotonic() + 75
    while True:
        run = read_api(LAB, path)
        if run.get('status') == 'completed':
            break
        need(run.get('status') == 'in_progress' and time.monotonic() < deadline, 'LAB_UNKNOWN')
        time.sleep(3)
    created = run.get('created_at', '')
    try:
        utc = datetime.fromisoformat(created.replace('Z', '+00:00')).astimezone(timezone.utc)
        need(utc.isoformat().replace('+00:00','Z') == created, 'LAB_TIMESTAMP')
    except (AttributeError, ValueError):
        raise ValueError('LAB_TIMESTAMP') from None
    query = urlencode({'created': '>=' + created, 'event': 'workflow_dispatch', 'branch': 'main'})
    runs = complete_rows(DEV, '/actions/workflows/232539432/runs?' + query, 'workflow_runs')
    matching = [r for r in runs if r.get('display_title') == 'DEV automatic real publication'
                and r.get('actor', {}).get('id') == DEV_APP]
    need(len(matching) == 1 and str(matching[0].get('id')) == env.get('GITHUB_RUN_ID'),
         'DEV_DUPLICATE_OR_UNKNOWN')
    live = read_api(LAB, '/git/ref/heads/publisher-data')
    need(live.get('object',{}).get('sha') == actual_head, 'PUBLIC_HEAD_OR_SID_MOVED')
    observed = dict(run=run, jobs=complete_rows(LAB, path+'/jobs', 'jobs'),
                    artifacts=complete_rows(LAB, path+'/artifacts', 'artifacts'),
                    head=actual_head, sid=actual_sid)
    return admit_dev(dict(repository_id=int(env.get('GITHUB_REPOSITORY_ID','0')),
                          repository=env.get('GITHUB_REPOSITORY'),
                          actor_id=int(env.get('GITHUB_ACTOR_ID','0')),
                          attempt=int(env.get('GITHUB_RUN_ATTEMPT','0')),
                          run_id=int(env.get('GITHUB_RUN_ID','0')),
                          ref=env.get('GITHUB_REF'), event=env.get('GITHUB_EVENT_NAME')),
                     request, observed, LAB_CODE_PIN)
