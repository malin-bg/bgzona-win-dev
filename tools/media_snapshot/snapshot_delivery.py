"""Existing native build/acceptance/seal with trusted Git snapshot input. Never dispatches or deploys."""
from pathlib import Path
from urllib.parse import urlsplit,unquote
from html.parser import HTMLParser
import argparse,json,os,subprocess,sys,tomllib
from snapshot_adapter import configured,strict
import acceptance,artifact_seal
from media_support import data,atomic

def need(v,c):
 if not v:raise ValueError(c)
class Page(HTMLParser):
 def __init__(self):super().__init__();self.meta={}
 def handle_starttag(self,t,attrs):
  a=dict(attrs)
  if t=='meta' and 'property' in a:self.meta[a['property']]=a.get('content')

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--request',required=True);parser.add_argument('--work',required=True);parser.add_argument('--hugo',required=True);parser.add_argument('--baseline');parser.add_argument('--site');a=parser.parse_args()
 site=Path(a.site).resolve() if a.site else Path(__file__).resolve().parents[2];policy=configured();role=policy['channel'];base={'dev':'https://dev.bgzona.win/','prod':'https://bgzona.win/'}[role];out=Path(a.work).resolve();need(out.is_relative_to(policy['output_workspace']) and out!=policy['output_workspace'] and not out.exists(),'NEW_ISOLATED_OUTPUT_REQUIRED')
 need(tomllib.loads((site/'hugo.toml').read_text('utf8'))['baseURL']==base and acceptance.BASE==base,'CHANNEL_CONFIG_CHANGED');out.mkdir(parents=True)
 env=dict(os.environ,HUGO_MODULE_PROXY='off',PYTHONDONTWRITEBYTECODE='1',GIT_TERMINAL_PROMPT='0')
 def run(args,log):
  q=subprocess.run(args,env=env,capture_output=True,text=True,encoding='utf8',errors='replace');atomic(out/log,(q.stdout+'\n'+q.stderr).encode());need(q.returncode==0,'BUILD_FAILED')
 if a.baseline:
  baseline=Path(a.baseline).resolve();need(baseline.is_dir(),'BASELINE_MISSING')
 else:
  # Same native RS4B media-disabled baseline; no alternate renderer.
  baseline=out/'baseline/public';overlay=out/'baseline.toml';atomic(overlay,('resourceDir = '+json.dumps((out/'baseline-resources').as_posix())+'\n').encode())
  run([a.hugo,'--source',str(site),'--config',str(site/'hugo.toml')+','+str(overlay),'--destination',str(baseline),'--cacheDir',str(out/'baseline-cache'),'--baseURL',base,'--environment','production','--noBuildLock'],'baseline.log')
 run([sys.executable,'-B',str(Path(__file__).parent/'build.py'),'--site',str(site),'--snapshot-request',str(Path(a.request).resolve()),'--output-root',str(out/'candidate'),'--hugo',a.hugo],'candidate.log')
 candidate=out/'candidate';public=candidate/'public';proof=strict((candidate/'snapshot-input.json').read_bytes());manifest=strict((candidate/'validated-manifest.json').read_bytes())
 need(proof['authority_root']==policy['root'] and proof['trusted_ref']==policy['ref'] and proof['baseline_complete'] is True,'TRUSTED_INPUT_PROOF')
 version=dict(schema=1,channel=role,data_revision=proof['data_commit'],snapshot=proof['snapshot']);atomic(public/'media-version.json',data(version))
 accepted=acceptance.validate(candidate,baseline,out/'acceptance.json');need(accepted['status']=='PASS' and strict((candidate/'build-receipt.json').read_bytes())['status']=='BUILD_PASS_UNDEPLOYED','ACCEPTANCE_FAILED')
 # Same RS4B supplementary container checks for newly generated thumbs, without re-sanitizing originals.
 sys.path.insert(0,str(Path(__file__).parent/'git_snapshot/workers'));import privacy_gate
 generated=set()
 for row in manifest['items']:
  page=Page();path=public/row['collection']/(('kolaj-' if row['collection']=='kolaji' else 'p-')+f"{row['number']:05d}")/'index.html';page.feed(path.read_text('utf8'));description=(candidate/'media'/row['txt']).read_text('utf8').strip()
  need(not description or page.meta.get('og:title')==page.meta.get('og:description')==description,'OG_TXT_CHANGED')
  item=accepted['pages'][row['stem']];need(item['url'].startswith(base) and urlsplit(item['og']).netloc==urlsplit(base).netloc,'CHANNEL_IDENTITY');generated.add(unquote(urlsplit(item['thumbnail']).path).lstrip('/'))
 for path in generated:
  raw=(public/path).read_bytes();clean,_,removed=privacy_gate.jpeg(raw);need(Path(path).suffix.lower()=='.jpg' and clean==raw and not removed,'THUMB_PRIVACY_METADATA')
 for path in public.rglob('*'):
  if not path.is_file():continue
  rel=path.relative_to(public);need(not any(x in rel.parts for x in ('.git','.github','incoming','library','registry','reports','objects','git_snapshot')) and path.name not in {'state.json','registry.json','manifest.json','snapshot-input.json','binding.json','expected-files.json','site-input-policy.json','request.json'},'INTERNAL_PUBLIC_LEAK')
 need(strict((public/'media-version.json').read_bytes())==version,'VERSION_BINDING')
 seal=out/'site-seal.json';tree=artifact_seal.seal(public,seal);artifact_seal.verify(public,seal,tree);atomic(out/'site-tree.sha256',(tree+'\n').encode());inventory=strict(seal.read_bytes());hashes={x['path']:x['sha256'] for x in inventory['files']}
 need(all(hashes.get(path)==h for path,h in proof['public_files'].items()),'HISTORICAL_IMAGE_LOST')
 receipt=dict(status='LOCAL_BUILD_ACCEPTANCE_SEAL_PASS',role=role,canonical=base,data_revision=proof['data_commit'],snapshot=proof['snapshot'],selection=proof['selection'],ids=proof['ids'],revisions=proof['revisions'],preserved_image_paths=len(proof['public_files']),acceptance_checks=len(accepted['checks']),generated_thumbnails_privacy_checked=len(generated),public_tree_sha256=tree,version=version,legacy_D3_input_used=False,deployed=False,GitHub_writes=0)
 atomic(out/'receipt.json',data(receipt));print(json.dumps(receipt))
if __name__=='__main__':main()
