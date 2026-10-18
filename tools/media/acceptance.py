"""B3A checks adapted to current-source baseline and portable paths."""
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,urljoin
import json,html,xml.etree.ElementTree as ET
from html_probe import Doc,inspect_image,local
from media_support import fhash,atomic,data
BASE="https://dev.bgzona.win/"

class Gallery(Doc):
 def __init__(self,s):self.current=None;self.media={};super().__init__(s)
 def handle_starttag(self,t,attrs):
  super().handle_starttag(t,attrs);a=dict(attrs)
  if t=='figure' and a.get('data-media-id'):self.current=a['data-media-id'];self.media[self.current]={}
  if self.current and t=='img':self.media[self.current]['thumb']=a['src']
 def handle_endtag(self,t):
  if t=='figure':self.current=None

def validate(buildroot,baseline_output,report):
 manifest=json.loads((buildroot/'validated-manifest.json').read_bytes())
 states=json.loads((buildroot/'build-receipt.json').read_bytes())['states']
 out=buildroot/'public';rows=manifest['items'];result=[];pages={}
 def ck(label,ok,detail=None):result.append({'test':label,'status':'PASS' if ok else 'FAIL','detail':detail})
 galleries={col:Gallery((out/col/'index.html').read_text(encoding='utf8')) for col in ('kolaji','poslaniya')}
 locs=[x.text for x in ET.parse(out/'sitemap.xml').iter() if x.tag.endswith('loc')]
 slides=[urljoin(BASE,u) for u in json.loads((out/'media/slideshow.json').read_text(encoding='utf8'))['images']]
 expected_slides=[]
 for r in rows:
  key=r['stem'];col=r['collection'];url=f'{col}/'+('kolaj-' if col=='kolaji' else 'p-')+f'{r["number"]:05d}/';expected=BASE+url
  path=out/url/'index.html';ck('page:'+key,path.exists())
  if not path.exists():continue
  text=path.read_text(encoding='utf8');d=Doc(text);ck('canonical:'+key,d.metadata()['canonical']==[expected])
  art=d.select('article',**{'data-media-id':key});ck('identity-revision:'+key,len(art)==1 and art[0].get('data-revision')==str(r['revision']))
  full=d.select('a',id='open-original')[0]['href'];fp=local(out,full)
  ck('exact-original-reference:'+key,urlsplit(full).path=='/'+r['publicPath'] and parse_qs(urlsplit(full).query).get('h')==[r['sha256']])
  ck('original-SHA256:'+key,fp.is_file() and fhash(fp)==r['sha256'])
  source=buildroot/'media'/r['source'];sp=inspect_image(source);op=inspect_image(fp)
  ck('format-animation:'+key,all(sp[k]==op[k] for k in ('format','frames','durations_ms','loop','frame_pixel_hashes')))
  tu=galleries[col].media.get(key,{}).get('thumb');ck('thumbnail-present:'+key,bool(tu))
  tp=inspect_image(local(out,tu));w,h=sp['size'];tw,th=tp['size'];scale=min(1,800/w,800/h)
  ck('thumbnail-fit-no-crop-upscale:'+key,tw<=800 and th<=800 and tw<=w and th<=h and abs(tw-w*scale)<=1 and abs(th-h*scale)<=1)
  ck('thumbnail-separate-static:'+key,local(out,tu)!=fp and tp['frames']==1 and tp['format']==('PNG' if r['alpha'] else 'JPEG'))
  if r['alpha']:ck('thumbnail-alpha:'+key,tp['alpha_range'][0]<255)
  og=d.select('meta',property='og:image');twitter=d.select('meta',name='twitter:image')
  ck('OG-Twitter:'+key,len(og)==1 and len(twitter)==1 and og[0]['content']==twitter[0]['content'])
  ogurl=og[0]['content'];ogp=local(out,ogurl);ogprops=inspect_image(ogp)
  ck('OG-local-absolute:'+key,ogurl.startswith(BASE) and ogp.is_file())
  if r.get('og'):ck('own-OG-exact-path-bytes:'+key,urlsplit(ogurl).path=='/'+r['ogPublicPath'] and fhash(ogp)==fhash(buildroot/'media'/r['og']))
  elif r['ext'] in ('.gif','.webp'):ck('static-fallback:'+key,ogprops['format']=='JPEG' and ogprops['frames']==1)
  else:ck('original-OG:'+key,fhash(ogp)==r['sha256'])
  desc=(buildroot/'media'/r['txt']).read_text(encoding='utf8').strip() or (('Колаж' if r['collection']=='kolaji' else 'Послание')+f' {r["number"]:05d}')
  ck('TXT-render:'+key,html.escape(desc,quote=False).replace('\r\n','\n') in text.replace('\r\n','\n'))
  ck('social-description:'+key,all(d.select('meta',**{attr:tag})[0]['content']==desc for attr,tag in [('property','og:description'),('name','twitter:description')]))
  ck('share-copy-page-url:'+key,parse_qs(urlsplit(d.select('a',id='facebook-share')[0]['href']).query).get('u')==[expected] and d.select('button',id='copy-link')[0]['data-url']==expected)
  ck('sitemap:'+key,locs.count(expected)==1)
  if col=='kolaji' and r['slideshow']:expected_slides.append(full)
  ck('slideshow-membership:'+key,(full in slides)==(col=='kolaji' and r['slideshow']))
  pages[key]={'url':expected,'full':full,'thumbnail':tu,'og':ogurl,'description':desc,'revision':r['revision'],'original':op,'thumb_properties':tp,'og_properties':ogprops,'slideshow':r['slideshow']}
 for col,g in galleries.items():ck('gallery:'+col,set(g.media)=={r['stem'] for r in rows if r['collection']==col})
 ck('slideshow-exact-set',len(slides)==len(expected_slides) and set(slides)==set(expected_slides))
 actual_pages={a['data-media-id'] for p in out.rglob('*.html') for a in Doc(p.read_text(encoding='utf8')).select('article') if a.get('data-media-id')}
 ck('exact-individual-page-set',actual_pages=={r['stem'] for r in rows})
 bad=[]
 for p in out.rglob('*.html'):
  rr=Doc(p.read_text(encoding='utf8')).select('meta',name='robots')
  if len(rr)!=1 or rr[0].get('content')!='noindex, follow':bad.append(str(p.relative_to(out)))
 ck('DEV-noindex-all-HTML',not bad,bad)
 baseline={p.relative_to(baseline_output).as_posix():Doc(p.read_text(encoding='utf8')).metadata() for p in (baseline_output/'statii').rglob('*.html')};regress=[]
 for rel,metadata in baseline.items():
  other=out/rel
  if not other.is_file() or metadata!=Doc(other.read_text(encoding='utf8')).metadata():regress.append(rel)
 ck('article-canonical-OG-Twitter-robots-unchanged',not regress,{'count':len(baseline),'changed':regress})
 menu=(out/'index.html').read_text(encoding='utf8');positions=[menu.find('href="'+BASE+c+'/"') for c in ('videa','poslaniya','kolaji')]
 ck('menu-order',min(positions)>=0 and positions==sorted(positions),positions)
 forbidden={'incoming','replace','library','registry','automation-state','objects','.git','.github'}
 ck('no-private-files',not any(forbidden.intersection(p.relative_to(out).parts) for p in out.rglob('*')))
 ck('no-v2',not (out/'v2').exists())
 images=[]
 for p in baseline_output.rglob('*'):
  if p.is_file() and 'statii' in p.relative_to(baseline_output).parts and p.suffix.lower() in ('.jpg','.jpeg','.png','.gif','.webp'):
   rel=p.relative_to(baseline_output);images.append(rel.as_posix())
   ck('article-local-image:'+rel.as_posix(),(out/rel).is_file() and fhash(p)==fhash(out/rel))
 ck('404-metadata-unchanged',Doc((out/'404.html').read_text(encoding='utf8')).metadata()==Doc((baseline_output/'404.html').read_text(encoding='utf8')).metadata())
 ck('no-input-bundle-or-manifest-leak',not any(p.name in {'expected-files.json','provenance.json','input-lock.json','site-seal.json','delivery-receipt.json'} or p.suffix.lower()=='.zip' for p in out.rglob('*') if p.is_file()))
 value={'status':'PASS' if all(c['status']=='PASS' for c in result) else 'FAIL','checks':result,'pages':pages,'slideshow':slides,'published':len(rows),'states':states}
 atomic(report,data(value))
 if value['status']!='PASS':raise AssertionError([c for c in result if c['status']=='FAIL'])
 return value
