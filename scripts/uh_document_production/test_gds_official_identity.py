#!/usr/bin/env python3
"""Non-live GDS Word identity test; source fixture is not official content."""
from __future__ import annotations
import os
import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree import ElementTree as ET
sys.dont_write_bytecode=True
from prepare_docx import run, GDS_CROWN_SHA256, GDS_CROWN_URL

ROOT=Path(os.environ.get('UH_DOCS_QA_FIXTURES',Path(__file__).resolve().parents[3]))
SOURCE=ROOT/'source/google-doc-revision-47-20261106.docx'
CROWN=Path(__file__).resolve().parent/'identity/uh-crown-black-20261014.png'
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

def denied(f):
    try:f()
    except ValueError:return True
    return False

results=[]
def check(label,f):
    try:
        assert f()
        results.append(('PASS',label))
    except Exception as e:results.append(('FAIL',label,type(e).__name__+': '+str(e)))

with TemporaryDirectory(prefix='gds-uh-word-test-') as td:
    base=Path(td)
    src=base/'gds-identity-fixture.docx'
    with ZipFile(SOURCE) as z:
        files={i.filename:z.read(i.filename) for i in z.infolist()}
    root=ET.fromstring(files['word/document.xml'])
    paras=list(root.iter(W+'p'))
    from_p=next(p for p in paras if 'From: Cabinet Office' in ''.join(t.text or '' for t in p.iter(W+'t')))
    ts=list(from_p.iter(W+'t'))
    for t in ts:t.text=''
    ts[0].text='From: Government Digital Service'
    files['word/document.xml']=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    with ZipFile(src,'w',ZIP_DEFLATED) as z:
        for path,value in files.items():z.writestr(path,value)
    title='Government across United Hampshire: central, devolved and local responsibilities'
    out=base/'gds-technical.docx'
    def valid():
        r=run(src,out,'en-GB',title,issuer='Government Digital Service',page_numbers=True,
             logo_path=CROWN,logo_sha=GDS_CROWN_SHA256,logo_evidence=GDS_CROWN_URL)
        with ZipFile(out) as z:
            head=z.read('word/header1.xml')
            head_rels=z.read('word/_rels/header1.xml.rels')
            media=z.read('word/media/uh-institutional-logo.png')
            foot=z.read('word/footer1.xml')
            header_root=ET.fromstring(head)
            para=header_root.find(W+'p')
            wp='{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
            ext=next(header_root.iter(wp+'extent'))
            if not (ext.get('cx','').isdigit() and ext.get('cy','').isdigit()):return False
            if para[0].tag!=W+'pPr' or b'{cx}' in head or b'{cy}' in head:return False
            if b'officeDocument/2006/relationships/image' not in head_rels:return False
        return (r['issuer_masthead']=='Government Digital Service' and
            r['source_paragraph_text_unchanged'] and r['issuer_logo_embedded'] and
            r['issuer_logo_approval_verified_in_native_editor'] is False and
            b'Government Digital Service' in head and b'16EEEE' in head and
            b'left' in head and b'PAGE' in foot and b'NUMPAGES' in foot and
            hashlib.sha256(media).hexdigest()==GDS_CROWN_SHA256)
    check('real GDS original crown and colour in Word header; page numbering',valid)
    check('wrong identity image digest denied',lambda:denied(lambda:run(src,base/'bad.docx','en-GB',title,issuer='Government Digital Service',logo_path=CROWN,logo_sha='f'*64,logo_evidence=GDS_CROWN_URL)))
    check('wrong identity authority URL denied',lambda:denied(lambda:run(src,base/'bad2.docx','en-GB',title,issuer='Government Digital Service',logo_path=CROWN,logo_sha=GDS_CROWN_SHA256,logo_evidence='https://invalid.test/uk_crest.png')))
    check('missing GDS crown denied',lambda:denied(lambda:run(src,base/'bad3.docx','en-GB',title,issuer='Government Digital Service')))
    check('source document untouched',lambda:hashlib.sha256(SOURCE.read_bytes()).hexdigest()=='a962112d1a94ab4f2b2f9df28f48e93b3ae97c39a2c3e4306ff4f978d16a029a')
for row in results:print(*row)
print('RESULT',sum(x[0]=='PASS' for x in results),'/',len(results))
if any(x[0]!='PASS' for x in results):raise SystemExit(1)
