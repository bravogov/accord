#!/usr/bin/env python3
"""Isolated normal/negative/restore checks for the native source adapter."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import shutil
root=Path(__file__).resolve().parents[2]
script=root/"accord/scripts/uh_document_production_source.py"
spec=importlib.util.spec_from_file_location("uh_source",script)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
source=root/"source/original-google-doc-revision.docx"
manifest=json.loads((root/"sample/source-manifest.json").read_text())
expected=manifest["source_sha256"]
checks=[]

def check(name,fn):
    try:
        assert fn() is True
        checks.append([name,"PASS"])
    except Exception as e:
        checks.append([name,"FAIL",str(e)])

def denied(changes):
    m=manifest|changes
    with tempfile.TemporaryDirectory() as td:
        mf=Path(td)/"manifest.json";mf.write_text(json.dumps(m))
        try:module.build(source,mf,Path(td)/"out")
        except (ValueError,KeyError):return True
        return False

def normal():
    with tempfile.TemporaryDirectory() as td:
        mf=Path(td)/"manifest.json";mf.write_text(json.dumps(manifest))
        module.build(source,mf,Path(td)/"out")
        a=Path(td)/"out/native-govspeak.txt"
        h=Path(td)/"out/accessible-html-preview.html"
        return a.is_file() and h.is_file() and a.read_text().count("## ")==6 and h.read_text().count("<h2>")==6
check("normal source conversion", normal)
check("source SHA integrity",lambda:hashlib.sha256(source.read_bytes()).hexdigest()==expected)
check("wrong source checksum denied",lambda:denied({"source_sha256":"0"*64}))
check("published state denied",lambda:denied({"status":"published"}))
check("news HTML attachment denied",lambda:denied({"native_content_type":"NewsArticle"}))
check("manual HTML attachment denied",lambda:denied({"native_content_type":"Manual"}))
check("incorrect provenance denied",lambda:denied({"published_display":"19 November 2026"}))
check("missing owner denied",lambda:denied({"organisations":["Incorrect"]}))
def restore():
    with tempfile.TemporaryDirectory() as td:
        mf=Path(td)/"manifest.json";mf.write_text(json.dumps(manifest))
        path=Path(td)/"out";module.build(source,mf,path)
        before={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in path.iterdir()}
        backup=Path(td)/"backup";shutil.copytree(path,backup)
        shutil.rmtree(path);shutil.copytree(backup,path)
        after={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in path.iterdir()}
        return before==after and hashlib.sha256(source.read_bytes()).hexdigest()==expected
check("isolated artifact backup and restore",restore)
for c in checks:print(*c)
print(f"{sum(c[1]=='PASS' for c in checks)}/{len(checks)}")
if any(c[1]!="PASS" for c in checks):raise SystemExit(1)

# Preserve complex source structures; never silently flatten tables/links/lists.
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
def q(tag): return '{'+W+'}'+tag

def enriched_source(doc_change, rel_change=None):
    with tempfile.TemporaryDirectory() as td:
        tmp=Path(td); src=tmp/'rich.docx'; mf=tmp/'manifest.json'; out=tmp/'output'
        with ZipFile(source) as z:
            doc=etree.fromstring(z.read('word/document.xml'))
            doc_change(doc)
            rel=etree.fromstring(z.read('word/_rels/document.xml.rels'))
            if rel_change: rel_change(rel)
            with ZipFile(src,'w',ZIP_DEFLATED) as dest:
                for entry in z.infolist():
                    payload=(etree.tostring(doc) if entry.filename=='word/document.xml' else
                             etree.tostring(rel) if entry.filename=='word/_rels/document.xml.rels' else z.read(entry.filename))
                    dest.writestr(entry,payload)
        mf.write_text(json.dumps(manifest|{'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest()}))
        return src,mf,out,module.build(src,mf,out)

def add_structured_content(doc):
    body=doc.find(q('body'))
    # Insert immediately after an existing first section heading, leaving original metadata intact.
    idx=next(i for i,p in enumerate(body) if p.find('./'+q('pPr')+'/'+q('pStyle')) is not None and
             p.find('./'+q('pPr')+'/'+q('pStyle')).get(q('val'))=='Heading1')+1
    para=etree.Element(q('p'))
    r1=etree.SubElement(para,q('r')); t1=etree.SubElement(r1,q('t'));t1.text='A '
    r2=etree.SubElement(para,q('r'));pr=etree.SubElement(r2,q('rPr'));etree.SubElement(pr,q('b'));t2=etree.SubElement(r2,q('t'));t2.text='bold'
    r3=etree.SubElement(para,q('r'));t3=etree.SubElement(r3,q('t'));t3.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t3.text=' section with '
    hyperlink=etree.SubElement(para,q('hyperlink'));hyperlink.set('{'+R+'}id','rId900')
    rh=etree.SubElement(hyperlink,q('r'));ht=etree.SubElement(rh,q('t'));ht.text='linked guidance'
    body.insert(idx,para)
    tbl=etree.Element(q('tbl'))
    for row in [['Topic','Status'],['Safeguarding','Required']]:
        tr=etree.SubElement(tbl,q('tr'))
        for cell in row:
            tc=etree.SubElement(tr,q('tc'));p=etree.SubElement(tc,q('p'));r=etree.SubElement(p,q('r'));etree.SubElement(r,q('t')).text=cell
    body.insert(idx+1,tbl)
    bullet=etree.Element(q('p'));ppr=etree.SubElement(bullet,q('pPr'));etree.SubElement(ppr,q('pStyle')).set(q('val'),'ListBullet')
    r=etree.SubElement(bullet,q('r'));etree.SubElement(r,q('t')).text='Retain the record'
    body.insert(idx+2,bullet)

def structured():
    with tempfile.TemporaryDirectory() as td:
        tmp=Path(td);src=tmp/'structured.docx'; mf=tmp/'manifest.json';out=tmp/'output'
        with ZipFile(source) as z:
            doc=etree.fromstring(z.read('word/document.xml'))
            add_structured_content(doc)
            rel=etree.fromstring(z.read('word/_rels/document.xml.rels'))
            entry=etree.SubElement(rel,'{http://schemas.openxmlformats.org/package/2006/relationships}Relationship')
            entry.set('Id','rId900')
            entry.set('Type','http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink')
            entry.set('Target','https://www.gov.uhrblx.com/guidance/test')
            entry.set('TargetMode','External')
            with ZipFile(src,'w',ZIP_DEFLATED) as dest:
                for item in z.infolist():
                    payload=etree.tostring(doc) if item.filename=='word/document.xml' else etree.tostring(rel) if item.filename=='word/_rels/document.xml.rels' else z.read(item.filename)
                    dest.writestr(item,payload)
        mf.write_text(json.dumps(manifest|{'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest()}))
        module.build(src,mf,out)
        md=(out/'native-govspeak.txt').read_text();preview=(out/'accessible-html-preview.html').read_text()
        # Exact source PDF is not generated from this synthetic fixture.
        return ('**bold**' in md and '| Topic | Status |' in md and '* Retain the record' in md and
                '<table>' in preview and '<th scope=' in preview and '<strong>bold</strong>' in preview and
                '<ul>' in preview and 'linked guidance' in md and '[linked guidance](https://www.gov.uhrblx.com/guidance/test)' in md)

check('source-rich bold, linked, table and list conversion', structured)

def negative_feature(tag):
    with tempfile.TemporaryDirectory() as td:
        tmp=Path(td);src=tmp/'invalid.docx';mf=tmp/'manifest.json';out=tmp/'output'
        with ZipFile(source) as z:
            doc=etree.fromstring(z.read('word/document.xml'));p=next(p for p in doc.xpath('//*[local-name()="body"]/*[local-name()="p"]') if p.xpath('.//*[local-name()="t"]'))
            r=etree.SubElement(p,q('r'));etree.SubElement(r,q(tag))
            with ZipFile(src,'w',ZIP_DEFLATED) as dest:
                for entry in z.infolist():dest.writestr(entry,etree.tostring(doc) if entry.filename=='word/document.xml' else z.read(entry.filename))
        mf.write_text(json.dumps(manifest|{'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest()}))
        try:module.build(src,mf,out)
        except ValueError:return not out.exists()
        return False
check('image is rejected rather than silently omitted',lambda:negative_feature('drawing'))
check('footnote is rejected rather than silently omitted',lambda:negative_feature('footnoteReference'))
print('EXTENDED:',checks[-3:])
if any(x[1]!='PASS' for x in checks):raise SystemExit(1)
