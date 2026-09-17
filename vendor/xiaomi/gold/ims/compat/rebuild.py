#!/usr/bin/env python3
"""Add LineageOS 23.2 legacy metrics compatibility to the unchanged IMS v5 payload.
Usage: python3 rebuild.py --tree /path/to/lineage --base-apk /path/to/v5/ImsService.apk --output /tmp/ImsService.apk
Runs existing Linux JDK/D8 tools. The output is an unsigned android_app_import input.
"""
from pathlib import Path
import argparse,hashlib,subprocess,tempfile,zipfile,json

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--tree',type=Path,required=True);p.add_argument('--base-apk',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 assert not a.output.exists(),'Output already exists'
 assert sha(a.base_apk)=='814314312976a063575927084657f6dc89137afab876b7ef59366ca7242cd64a','Requires validated v5 input'
 source=a.tree/'hardware/lineage/compat/frameworks/telephony-common-stub/src/com/android/internal/telephony/metrics/TelephonyMetrics.java'
 assert sha(source)=='c68e1d2342dfa96dd5823ba8eca106efe94fcfac4a96964e978e36c63cedd128','Review upstream source changes first'
 java=a.tree/'prebuilts/jdk/jdk21/linux-x86/bin'
 with tempfile.TemporaryDirectory(prefix='gold-ims-compat-') as td:
  tmp=Path(td);classes=tmp/'classes';dex=tmp/'dex';classes.mkdir();dex.mkdir()
  subprocess.run([str(java/'javac'),'--release','8','-d',str(classes),str(source)],check=True)
  subprocess.run([str(java/'java'),'-cp',str(a.tree/'out/host/linux-x86/framework/d8.jar'),'com.android.tools.r8.D8','--min-api','26','--output',str(dex)]+[str(f) for f in classes.rglob('*.class')],check=True)
  with zipfile.ZipFile(a.base_apk) as src,zipfile.ZipFile(a.output,'w') as dst:
   assert 'classes2.dex' not in src.namelist()
   for info in src.infolist():
    if not info.filename.startswith('META-INF/'):dst.writestr(info,src.read(info.filename))
   info=zipfile.ZipInfo('classes2.dex',(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;dst.writestr(info,(dex/'classes.dex').read_bytes())
  with zipfile.ZipFile(a.base_apk) as src,zipfile.ZipFile(a.output) as dst:
   for n in src.namelist():
    if not n.startswith('META-INF/'):assert src.read(n)==dst.read(n)
  print(json.dumps({'base_sha256':sha(a.base_apk),'compat_source_sha256':sha(source),'classes2_dex_sha256':sha(dex/'classes.dex'),'output_sha256':sha(a.output),'existing_payload_unchanged':True},indent=2))
if __name__=='__main__':main()
