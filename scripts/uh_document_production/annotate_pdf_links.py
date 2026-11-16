#!/usr/bin/env python3
"""Preserve issued-source link semantics in a candidate PDF without changing its prose.

The document is never issued by this tool. Link descriptions are taken from the
exact source Govspeak, not inferred from destination URLs or model output.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, TextStringObject
from zipfile import ZipFile
from lxml import etree

SOURCE_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")

def toc_entries(docx: Path) -> list[str]:
    if not docx.is_file() or docx.suffix.lower() != '.docx':
        raise ValueError('Generated original candidate DOCX with contents is required')
    with ZipFile(docx) as z:
        document = etree.fromstring(z.read('word/document.xml'))
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    entries=[]
    for p in document.xpath('//w:body/w:p',namespaces=ns):
        styles=p.xpath('./w:pPr/w:pStyle/@w:val',namespaces=ns)
        if not styles or not styles[0].startswith('UH-DfE-TocEntry'):continue
        hl=p.xpath('./w:hyperlink',namespaces=ns)
        if len(hl)!=1:raise ValueError('Contents requires one live internal link per entry')
        title=''.join(hl[0].xpath('.//w:t/text()',namespaces=ns))
        if not title:raise ValueError('Empty navigation heading')
        entries.append(title)
    return entries


def source_footnotes(docx:Path)->list[str]:
    with ZipFile(docx) as z:
        doc=etree.fromstring(z.read('word/document.xml'))
        notes=doc.xpath('//*[local-name()="footnoteReference"]')
        if notes and 'word/footnotes.xml' not in z.namelist():
            raise ValueError('Word references footnotes but footnote source missing')
        w='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
        ids=[x.get(w+'id') for x in notes]
        if any(not id for id in ids):raise ValueError('Source footnote identifier missing')
        return ids


def fix(source_pdf: Path, govspeak: Path, destination_pdf: Path, contents_docx: Path | None = None) -> dict:
    if source_pdf.resolve() == destination_pdf.resolve():
        raise ValueError("Never overwrite an original source PDF")
    if not source_pdf.is_file() or not govspeak.is_file():
        raise ValueError("Both PDF and original Govspeak are required")
    labels = defaultdict(set)
    for label, url in SOURCE_LINK.findall(govspeak.read_text(encoding="utf-8")):
        labels[url].add(label.strip())
    if not labels:
        raise ValueError("No source-backed links")
    for url, descriptions in labels.items():
        if len(descriptions) != 1 or not next(iter(descriptions)):
            raise ValueError(f"Ambiguous or missing original description: {url}")
    reader = PdfReader(str(source_pdf))
    writer = PdfWriter(clone_from=reader)
    changed = 0
    represented = set()
    internal = []
    for page_number, page in enumerate(writer.pages, 1):
        for ref in page.get("/Annots", []):
            item = ref.get_object()
            if item.get("/Subtype") != "/Link":
                continue
            target = item.get("/A", {}).get("/URI")
            if target is None:
                if not item.get('/Dest') and item.get('/A',{}).get('/S')!='/GoTo':
                    raise ValueError("Unrecognised internal or remote link annotation")
                if contents_docx is None:
                    raise ValueError("Internal link requires original Word TOC provenance")
                rect=item.get('/Rect',[])
                if len(rect)!=4:
                    raise ValueError('Internal link has no usable page rectangle')
                internal.append((page_number,-float(rect[3]),item))
                continue
            target = str(target)
            if target not in labels:
                raise ValueError(f"Unmatched PDF link annotation: {target}")
            description = next(iter(labels[target]))
            existing = item.get("/Contents")
            if existing and str(existing) != description:
                raise ValueError(f"Contradictory existing link description for {target}")
            if not existing:
                item[NameObject("/Contents")] = TextStringObject(description)
                changed += 1
            represented.add(target)
    if represented != set(labels):
        raise ValueError("Source hyperlinks omitted from rendered PDF")
    if contents_docx is not None:
        toc=toc_entries(contents_docx)
        internal.sort(key=lambda record:(record[0],record[1]))
        footnote_ids=source_footnotes(contents_docx)
        if len(internal)!=len(toc)+2*len(footnote_ids):
            raise ValueError('Internal link count does not reconcile to source contents and footnotes')
        for name,(_,_,item) in zip(toc,internal[:len(toc)]):
            if item.get('/Contents') and str(item['/Contents'])!=name:
                raise ValueError('Existing internal link description contradicts Word source')
            if not item.get('/Contents'):
                item[NameObject('/Contents')]=TextStringObject(name)
                changed+=1
        for _,_,item in internal[len(toc):]:
            rect=item.get('/Rect')
            dest=item.get('/Dest')
            if not dest or len(dest)<4:
                raise ValueError('Footnote link lacks original document destination')
            start_y=(float(rect[1])+float(rect[3]))/2
            target_y=float(dest[3])
            existing=str(item.get('/Contents') or '')
            if existing and existing not in footnote_ids and not existing.startswith(('Go to footnote ', 'Return to footnote reference ')):
                raise ValueError('Contradictory original footnote navigation description')
            footnote_id=existing if existing in footnote_ids else (footnote_ids[0] if len(footnote_ids)==1 else None)
            if footnote_id is None:
                raise ValueError('Footnote navigation lacks an unambiguous identifier')
            description=('Go to footnote ' if target_y<start_y else 'Return to footnote reference ')+footnote_id
            if existing!=description:
                item[NameObject('/Contents')]=TextStringObject(description)
                changed+=1
    elif internal:
        raise ValueError('Internal links require verified Word TOC')
    destination_pdf.parent.mkdir(parents=True,exist_ok=True)
    with destination_pdf.open("wb") as dest:
        writer.write(dest)
    original_sha = hashlib.sha256(source_pdf.read_bytes()).hexdigest()
    repaired_sha = hashlib.sha256(destination_pdf.read_bytes()).hexdigest()
    if original_sha == repaired_sha and changed:
        raise ValueError("Annotation correction not serialized")
    return {"original_pdf_sha256":original_sha,"candidate_pdf_sha256":repaired_sha,
            "source_distinct_links":len(labels),"toc_internal_links":len(internal),"annotation_descriptions_added":changed,
            "complete_source_link_coverage":True,"original_file_unchanged":True,
            "editorial_or_publication_approval":False}

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('pdf',type=Path)
    parser.add_argument('govspeak',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--contents-docx',type=Path)
    args=parser.parse_args()
    try: print(json.dumps(fix(args.pdf,args.govspeak,args.output,args.contents_docx),sort_keys=True))
    except Exception as e:
        print(f"LINK_ACCESSIBILITY_DENIED {type(e).__name__}: {e}",file=sys.stderr)
        sys.exit(1)
