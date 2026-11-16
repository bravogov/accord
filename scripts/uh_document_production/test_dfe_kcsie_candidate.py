#!/usr/bin/env python3
"""W12 original technical editor QA. Never tests or issues actual safeguarding advice."""
import sys,json,hashlib,tempfile,shutil,os
from pathlib import Path
from zipfile import ZipFile
from PIL import Image
from pypdf import PdfReader
HERE=Path(__file__).resolve().parent
ROOT=Path(os.environ.get("UH_DOCS_QA_FIXTURES",HERE.parents[2]))
sys.path.insert(0,str(HERE))
import dfe_kcsie_authoring as dfe
import finalise_dfe_contents as toc
SOURCE=ROOT/'source/google-doc-revision-47-20261106.docx'
CHECKS=[]
def test(name,fn):
 try:assert fn();CHECKS.append((name,'PASS'))
 except Exception as exc:CHECKS.append((name,'FAIL',repr(exc)))
def denied(fn):
 try:fn()
 except (ValueError,FileNotFoundError):return True
 return False
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp)
 identity=root/'qa-geometry-only.png';Image.new('RGB',(72,45),'white').save(identity)
 manifest={'status':'unpublished_candidate','organisation':'Department for Education','kind':'full',
    'title':'Word formatting QA fixture','subtitle':'Original non-safeguarding source integrity check',
    'edition_month':'November 2026','source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    'contains_official_content':True,'qa_only_fixture':True}
 mf=root/'manifest.json';mf.write_text(json.dumps(manifest))
 out=root/'format.docx'
 def build_good():
  proof=dfe.build(SOURCE,mf,identity,root/'absent-approval.json',out,True)
  return proof['QA_fixture_not_for_issue'] and proof['source_paragraphs_preserved']==44 and proof['kind']=='full'
 test('full layout preserves 44 source paragraphs in native Word',build_good)
 def check_metadata():
  with ZipFile(out) as z:
   return ('word/header_dfe1.xml' in z.namelist() and 'word/footer_dfe1.xml' in z.namelist()
       and 'word/header_dfe_body.xml' in z.namelist() and 'word/_rels/header_dfe1.xml.rels' in z.namelist()
       and b'Word formatting QA fixture' in z.read('docProps/core.xml') and b'UH-DfE-CoverTitle' in z.read('word/styles.xml')
       and b'PAGE' in z.read('word/footer_dfe1.xml'))
 test('official document schema has cover identity, style, title and pagination slots',check_metadata)
 test('actual official branding approval missing denies production',lambda:denied(lambda:dfe.build(SOURCE,mf,identity,root/'absent-approval.json',root/'denied.docx',False)))
 wrong=manifest|{'source_sha256':'0'*64};(root/'wrong.json').write_text(json.dumps(wrong))
 test('mismatched original source checksum rejected',lambda:denied(lambda:dfe.build(SOURCE,root/'wrong.json',identity,root/'absent-approval.json',root/'bad.docx',True)))
 wrong2=manifest|{'qa_only_fixture':False,'source_content_status':'not_legal_reviewed'};(root/'notlegallycomplete.json').write_text(json.dumps(wrong2))
 test('no legislation-verified source cannot be issued',lambda:denied(lambda:dfe.build(SOURCE,root/'notlegallycomplete.json',identity,root/'absent-approval.json',root/'bad2.docx',False)))
 manifest['kind']='part-one';mf.write_text(json.dumps(manifest))
 def partone():
  proof=dfe.build(SOURCE,mf,identity,root/'absent-approval.json',root/'part.docx',True)
  with ZipFile(root/'part.docx') as z:
   return proof['kind']=='part-one' and b'Part one' in z.read('word/document.xml')
 test('separate Part One title/cover candidate has original independent structure',partone)
 test('actual original source left untouched',lambda:hashlib.sha256(SOURCE.read_bytes()).hexdigest()==manifest['source_sha256'])
 restore=root/'restore.docx';shutil.copy2(out,restore)
 test('isolated Word candidate byte restore',lambda:hashlib.sha256(restore.read_bytes()).hexdigest()==hashlib.sha256(out.read_bytes()).hexdigest())
 # The profile results are from separate independent veraPDF 1.30.3 tool runs.
 for kind in ('pdfa2b','pdfua1'):
  path=Path('/tmp/w12-dfe-qa/render/qa-'+kind+'.json')
  def result(path=path):
   j=json.loads(path.read_text())['report']['jobs'][0]['validationResult'][0]
   return j['compliant'] and j['details']['failedRules']==0 and j['details']['failedChecks']==0
  test('independent candidate '+kind+' validation',result)
for name,result,*error in CHECKS:print(result,name,' '.join(error))
print(f'QA_RESULT {sum(status=="PASS" for _,status,*_ in CHECKS)}/{len(CHECKS)}')
if any(status!='PASS' for _,status,*_ in CHECKS):raise SystemExit(1)
