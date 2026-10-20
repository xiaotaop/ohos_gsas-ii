#!/usr/bin/env python3
from pathlib import Path
import tarfile,hashlib,json
import argparse
p=argparse.ArgumentParser(description='Reproduce bundled notice texts from pinned upstream sdists; never execute archive contents.')
p.add_argument('--source-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();r=a.source_dir;out=a.output
if out.exists(): p.error('output must be new')
out.mkdir(parents=True)
source=json.loads((Path(__file__).resolve().parents[1]/'packaging/licenses/scientific-sources.lock.json').read_text());records=[]
extras={'numpy':['numpy/_core/src/multiarray/dragon4.c'], 'scipy':['scipy/_lib/decorator.py','scipy/io/_fast_matrix_market/src/pystreambuf.h','scipy/optimize/__lbfgsb.c','scipy/stats/libnpyrandom/logfactorial.h','scipy/stats/libnpyrandom/logfactorial.c','scipy/interpolate/_bary_rational.py','scipy/integrate/_lebedev.py','subprojects/xsf/include/xsf/third_party/kokkos/mdspan.hpp']}
for s in source:
 p=r/s['filename'];assert hashlib.sha256(p.read_bytes()).hexdigest()==s['sha256']
 prefix=s['name']+'-'+s['version']+'/'
 with tarfile.open(p) as t:
  selected={}
  for m in t.getmembers():
   if not m.isfile():continue
   rel=m.name.removeprefix(prefix);leaf=rel.rsplit('/',1)[-1].lower()
   runtime=rel.startswith((s['name']+'/', 'subprojects/'))
   notice=leaf.startswith(('license','licence','copying','copyright')) and not leaf.endswith(('.yml','.rst'))
   if rel=='LICENSES_bundled.txt' or (runtime and notice and '/doc/' not in rel and '/.github/' not in rel) or rel in extras[s['name']]:
    selected[rel]=m
  assert all(x in selected for x in extras[s['name']]),set(extras[s['name']])-selected.keys()
  chunks=['Upstream bundled notices for '+s['name']+' '+s['version']+'\n\nCollected byte-for-byte from the SHA-256 verified upstream source distribution.\nThis is a conservative upstream notice collection, not a claim that every listed\nsource or build utility is present in the HarmonyOS binary. Inline-license files\nare included in full so their copyright and conditions remain intact.\nExact prebuilt compiler recipes are not asserted by this collection.\n\nSource: '+s['url']+'\nArchive SHA-256: '+s['sha256']+'\n']
  files=[]
  for rel,m in sorted(selected.items()):
   b=t.extractfile(m).read();text=b.decode('utf-8');files.append({'path':rel,'sha256':hashlib.sha256(b).hexdigest(),'size':len(b)})
   chunks+=['\n'+'='*72+'\nUPSTREAM FILE: '+rel+'\nSHA-256: '+files[-1]['sha256']+'\n'+'='*72+'\n',text,'\n']
 name=s['name']+'-'+s['version']+'-BUNDLED-NOTICES.txt';data=''.join(chunks).encode();(out/name).write_bytes(data)
 records.append(dict(s,noticeFile=name,noticeSha256=hashlib.sha256(data).hexdigest(),files=files))
 print(name,len(data),len(files))
(out/'BUNDLED-SOURCES.json').write_text(json.dumps({'scope':'upstream notices; no exact prebuilt recipe claim','sources':records},indent=2)+'\n')
