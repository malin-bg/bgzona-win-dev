"""Manual read-only H1I snapshot build admission; never dispatches or deploys."""
from pathlib import Path
import json,os,re,subprocess
COMMIT='849ba21975b5bda246cf27e9d63358b902750910'
SID='8e48b14dd9f6c7e9d26d07913b9b1386b63ccd12bfdb25647e777587cb1db117'
ROOT='564c405279c89e990c9345ccf7c54e2bf38c4470'
MARKER='rs4n-build-only'
REAL12_COMMIT='05cfdeb41ca116dc07614906fbbdee9b3a597745'
REAL12_SID='317a99d4d0f13416e2a001b94352870d95f63cc4a057b6957ebaf22a68edc55f'
REFS={'CURRENT':'refs/heads/rs4m-synthetic-data','PUBLIC12':'refs/heads/publisher-data'}
def need(v,c):
 if not v:raise ValueError(c)
def admit(event,env):
 need(env.get('GITHUB_REPOSITORY')=='malin-bg/bgzona-win-dev' and env.get('GITHUB_REPOSITORY_ID')=='1149689018' and env.get('GITHUB_REF')=='refs/heads/main','DEV_IDENTITY')
 need(env.get('GITHUB_EVENT_NAME')=='workflow_dispatch' and env.get('GITHUB_ACTOR_ID')=='252877943' and env.get('GITHUB_RUN_ATTEMPT')=='1','DEV_ACTOR_EVENT')
 need(env.get('H1_WORKFLOW_SHA')==env.get('GITHUB_SHA') and re.fullmatch('[a-f0-9]{40}',env.get('GITHUB_SHA','')),'DEV_CODE')
 need(event.get('repository',{}).get('id')==1149689018 and event.get('sender',{}).get('id')==252877943,'DEV_EVENT_BINDING')
 values=event.get('inputs',{})
 need(set(values)=={'accepted_cid','input_trust'} and values['input_trust'] in (MARKER,'rs4n-real12-pages'),'DEV_BUILD_ONLY_INPUTS')
 if values['input_trust']=='rs4n-real12-pages':
  need(values['accepted_cid']==REAL12_SID,'DEV_REAL12_PAGES_INPUT')
 if values['accepted_cid']==SID:
  return {'data_commit':COMMIT,'selection':'CURRENT','snapshot':SID}
 need(values['accepted_cid']==REAL12_SID,'DEV_BUILD_ONLY_INPUTS')
 return {'data_commit':REAL12_COMMIT,'selection':'PUBLIC12','snapshot':REAL12_SID}
def main():
 site=Path(os.environ['GITHUB_WORKSPACE']).resolve();temp=Path(os.environ['RUNNER_TEMP']).resolve();event=json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_bytes());request=admit(event,os.environ)
 def git(path,*args):
  q=subprocess.run(['git','--no-optional-locks','-C',str(path),*args],capture_output=True);need(q.returncode==0,'CHECKOUT_UNKNOWN');return q.stdout.decode().strip()
 need(git(site,'rev-parse','HEAD')==os.environ['GITHUB_SHA'],'DEV_CODE_CHECKOUT')
 source=site/'.rs4n-public-data';need(git(source,'remote','get-url','origin') in ('https://github.com/malin-bg/bgzona-github-lab','https://github.com/malin-bg/bgzona-github-lab.git'),'PUBLIC_ENDPOINT')
 ref=REFS[request['selection']];commit=request['data_commit']
 root=ROOT if request['selection']=='CURRENT' else REAL12_COMMIT
 need(git(source,'rev-parse','HEAD')==git(source,'rev-parse',ref)==commit and git(source,'rev-list','--max-parents=0',commit)==root,'PUBLIC_CHECKOUT_BINDING')
 package=Path(__file__).resolve().parent/'git_snapshot';common=Path(os.path.commonpath([site,temp]));need(common!=Path(common.anchor),'WORKSPACE_SCOPE')
 rel=lambda path:os.path.relpath(path,package).replace('\\','/')
 policy={'schema':1,'channel':'dev','endpoint':rel(source/'.git'),'workspace':rel(common),'output_workspace':rel(temp),'ref':ref,'root':root}
 (package/'site-input-policy.json').write_text(json.dumps(policy,indent=2)+'\n','utf8');(temp/'rs4n-request.json').write_text(json.dumps(request)+'\n','utf8')
 print('RS4N_READ_ONLY_BUILD_INPUT_BOUND')
if __name__=='__main__':main()
