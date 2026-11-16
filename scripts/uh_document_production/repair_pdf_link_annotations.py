#!/usr/bin/env python3
"""Make hyperlink annotations in a PDF/UA candidate screen-reader-readable.

The alternate link description comes exclusively from the source Google
Docs hyperlink text. No destination, link text or publication content is
invented, and all PDF/A and PDF/UA validators must be rerun after this step.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, TextStringObject

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

def source_links(docx: Path, allow_no_links: bool = False) -> dict[str,str]:
    labels = {}
    with ZipFile(docx) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        rel = ET.fromstring(z.read("word/_rels/document.xml.rels"))
        mappings = {node.get("Id"):node.get("Target") for node in rel}
        for node in root.iter(f"{W}hyperlink"):
            link_id = node.get(f"{R}id")
            url = mappings.get(link_id)
            text = "".join(t.text or "" for t in node.iter(f"{W}t")).strip()
            if not url or not text:
                raise ValueError(f"Unresolved source hyperlink {link_id}")
            if url in labels and labels[url] != text:
                raise ValueError("One URL has conflicting accessible labels in source")
            labels[url] = text
    if not labels and not allow_no_links:
        raise ValueError("No source hyperlinks to protect")
    return labels

def run(source:Path, input_pdf:Path, output_pdf:Path)->dict:
    if input_pdf.resolve() == output_pdf.resolve():
        raise ValueError("Cannot overwrite original PDF")
    links = source_links(source)
    reader = PdfReader(str(input_pdf))
    original_text = [p.extract_text() for p in reader.pages]
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    changed = 0
    annotation_urls = set()
    for page in writer.pages:
        for item in page.get("/Annots",[]):
            annotation = item.get_object()
            if annotation.get("/Subtype") != "/Link":
                continue
            action = annotation.get("/A")
            if not action or not action.get("/URI"):
                raise ValueError("Link without supported source document URI")
            uri = str(action["/URI"])
            if uri not in links:
                raise ValueError(f"PDF annotation has no matching source link: {uri}")
            annotation[NameObject("/Contents")] = TextStringObject(links[uri])
            changed += 1
            annotation_urls.add(uri)
    if set(links) != annotation_urls:
        raise ValueError("Source hyperlink absent from PDF annotation set")
    output_pdf.parent.mkdir(parents=True,exist_ok=True)
    with output_pdf.open("wb") as file:
        writer.write(file)
    result = PdfReader(str(output_pdf))
    if [p.extract_text() for p in result.pages] != original_text:
        raise ValueError("PDF body changed during technical annotation repair")
    return {
        "unchanged_source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
        "original_pdf_sha256":hashlib.sha256(input_pdf.read_bytes()).hexdigest(),
        "candidate_pdf_sha256":hashlib.sha256(output_pdf.read_bytes()).hexdigest(),
        "link_annotations_described":changed,
        "distinct_source_destinations":len(links),
        "pdf_body_text_unchanged":True,
        "approval_or_publication_conferred":False
    }

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("source",type=Path)
    p.add_argument("input_pdf",type=Path)
    p.add_argument("output_pdf",type=Path)
    x=p.parse_args()
    print(json.dumps(run(x.source,x.input_pdf,x.output_pdf),indent=2))
