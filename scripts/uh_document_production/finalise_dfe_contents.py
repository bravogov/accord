#!/usr/bin/env python3
"""Calculate page-accurate Word contents from independently rendered PDF pages.

This is a candidate-only iterative Word production stage. Source text, native
charts, footnotes and other attachments are never changed. Contents entries
are recreated from source Heading1..3 paragraphs and verified against actual
PDF pages on every render; full and Part One remain independent editions.
"""
import argparse,hashlib,json,re
from zipfile import ZipFile,ZIP_DEFLATED
from pathlib import Path
from lxml import etree
from pypdf import PdfReader
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS={'w':W}
def q(k):return '{'+W+'}'+k

def txt(p):return ''.join(p.xpath('.//w:t/text()',namespaces=NS))
def norm(s):return re.sub(r'\s+',' ',s).strip().casefold()
def render_pages(reader):return [norm(p.extract_text() or '') for p in reader.pages]
def heading_style(p):
    st=p.xpath('./w:pPr/w:pStyle/@w:val',namespaces=NS)
    v=st[0] if st else ''
    if v in ('Heading1','Heading2','Heading3'):
        return int(v[-1])
    return None

def update(source:Path,pdf:Path,dst:Path):
    if source.resolve()==dst.resolve():raise ValueError('Never overwrite source file')
    with ZipFile(source) as z:
        files={i.filename:z.read(i.filename) for i in z.infolist()}
    doc=etree.fromstring(files['word/document.xml']); body=doc.find(q('body'))
    items=list(body)
    toc=next((i for i,p in enumerate(items) if p.tag==q('p') and txt(p)=='Contents'),None)
    if toc is None:raise ValueError('Approved Word front matter has no contents section')
    br=next((i for i,p in enumerate(items[toc+1:],toc+1) if p.tag==q('p') and p.xpath('.//w:br[@w:type="page"]',namespaces=NS)),None)
    if br is None:raise ValueError('Expected page break after native Word TOC')
    heads=[]
    for p in items[br+1:]:
        if p.tag!=q('p'):continue
        level=heading_style(p)
        if level is None:continue
        value=txt(p)
        if not value:continue
        heads.append((level,value,p))
    if not heads:raise ValueError('Source lacks actual styled heading hierarchy')
    reader=PdfReader(str(pdf))
    pages=render_pages(reader)
    if len(pages)<2:raise ValueError('Cannot generate table of contents without whole PDF')
    # TOC entries repeat heading titles; begin searches at the first actual
    # source body paragraph, never on the contents page itself.
    body_fingerprints=[]
    for p in items[br+1:]:
        if p.tag==q('p') and heading_style(p) is None and len(norm(txt(p)))>=95:
            body_fingerprints.append(norm(txt(p))[:75])
    first_body_page=next((i for i,page in enumerate(pages) if any(f in page for f in body_fingerprints[:7])),None)
    if first_body_page is None:
        raise ValueError('Unable to distinguish the original body from TOC page')
    pageidx=first_body_page;matches=[]
    for lev,value,p in heads:
        n=norm(value)
        found=None
        for i in range(pageidx,len(pages)):
            if n in pages[i]:found=i+1;pageidx=i;break
        if found is None:raise ValueError('Source heading missing from rendered pages: '+value[:75])
        matches.append((lev,value,p,found))
    old=[p for p in items[toc+1:br]]
    old_listing=[txt(p) for p in old]
    for p in old:body.remove(p)
    anchor_id=6000
    insert_index=toc+1
    listings=[]
    for level,value,heading,pageno in matches:
        anchor='uh_dfe_heading_'+str(anchor_id)
        existing=heading.xpath('./w:bookmarkStart[@w:name="'+anchor+'"]',namespaces=NS)
        if not existing:
            start=etree.Element(q('bookmarkStart'));start.set(q('id'),str(anchor_id));start.set(q('name'),anchor)
            end=etree.Element(q('bookmarkEnd'));end.set(q('id'),str(anchor_id))
            heading.insert(0,start);heading.append(end)
        par=etree.Element(q('p'));props=etree.SubElement(par,q('pPr'))
        style=etree.SubElement(props,q('pStyle'));style.set(q('val'),'UH-DfE-TocEntry'+str(level))
        ind=etree.SubElement(props,q('ind'));ind.set(q('left'),str((level-1)*240))
        tabs=etree.SubElement(props,q('tabs'));tab=etree.SubElement(tabs,q('tab'))
        tab.set(q('val'),'right');tab.set(q('leader'),'dot');tab.set(q('pos'),'9310')
        hl=etree.SubElement(par,q('hyperlink'));hl.set(q('anchor'),anchor)
        run=etree.SubElement(hl,q('r'));t=etree.SubElement(run,q('t'));t.text=value
        rn=etree.SubElement(par,q('r'));etree.SubElement(rn,q('tab'))
        nr=etree.SubElement(par,q('r'));text=etree.SubElement(nr,q('t'));text.text=str(pageno)
        body.insert(insert_index,par);insert_index+=1
        listings.append(value+'\t'+str(pageno))
        anchor_id+=1
    files['word/document.xml']=etree.tostring(doc,encoding='UTF-8',xml_declaration=True)
    dst.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(dst,'w',ZIP_DEFLATED) as output:
        for name,data in files.items():output.writestr(name,data)
    return {'entries':len(listings),'headings':[{'level':lv,'heading':v,'page':n} for lv,v,_,n in matches],
            'previous_entries':old_listing,'current_entries':listings,
            'input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'output_sha256':hashlib.sha256(dst.read_bytes()).hexdigest()}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('docx',type=Path);p.add_argument('pdf',type=Path);p.add_argument('output',type=Path)
 a=p.parse_args();print(json.dumps(update(a.docx,a.pdf,a.output),indent=2))
