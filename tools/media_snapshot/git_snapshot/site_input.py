"""Local file-protocol consumer policy over the existing RS4E trusted adapter."""
from pathlib import Path
import json
import transport as T
import trusted_adapter as A
G=T.G;P=T.P;ROOT=Path(__file__).resolve().parent

def strict(raw):
 def unique(pairs):
  value={}
  for k,v in pairs:P.need(k not in value,'DUPLICATE_INPUT_KEY');value[k]=v
  return value
 return json.loads(raw,object_pairs_hook=unique)

def configured():
 policy=strict((ROOT/'site-input-policy.json').read_bytes())
 P.need(set(policy)=={'schema','channel','endpoint','workspace','output_workspace','ref','root'} and type(policy['schema']) is int and policy['schema']==1 and policy['channel'] in ('dev','prod'),'SITE_POLICY_FIELDS')
 T.select_profile(policy['ref'],policy['root'])
 for key in ['endpoint','workspace','output_workspace']:
  value=policy[key];P.need(isinstance(value,str) and value and '://' not in value and ':' not in value and '\\' not in value and not value.startswith('/'),'LOCAL_POLICY_PATH')
  path=ROOT/value;P.need(not any(p.is_symlink() or p.is_junction() for p in [path,*path.parents]),'POLICY_LINK');policy[key]=path.resolve()
 work=policy['workspace'];remote=policy['endpoint'];P.need(remote.is_relative_to(work) and remote!=work and remote.is_dir() and not (remote/'objects/info/alternates').exists(),'TRUSTED_FILE_ENDPOINT')
 T.configure(work,remote,policy['output_workspace']/('consumer-'+policy['channel']+'.git'));A.ROOT=policy['output_workspace'];return policy

def resolve_request(request):
 P.need(isinstance(request,dict) and set(request) in ({'data_commit','selection'},{'data_commit','selection','snapshot'}),'SNAPSHOT_REQUEST_FIELDS')
 G.oid(request['data_commit']);P.need(request['selection'] in ('PUBLIC12','PENDING13','CURRENT'),'SNAPSHOT_SELECTION');configured()
 return A.read(request)  # Derives SID from authorized immutable Git state, checks snapshot bytes and identities.

def materialize(artifact,request,destination):
 # Legacy positional artifact argument is unused compatibility only; no archive/resolver/D3 input is read.
 P.need(artifact is None,'NO_LEGACY_ARTIFACT_INPUT');policy=configured();dest=Path(destination).resolve();P.need(dest.is_relative_to(policy['output_workspace']) and dest!=policy['output_workspace'],'OUTPUT_POLICY')
 P.need(isinstance(request,dict) and set(request) in ({'data_commit','selection'},{'data_commit','selection','snapshot'}),'SNAPSHOT_REQUEST_FIELDS');G.oid(request['data_commit'])
 return A.materialize(None,request,dest)
