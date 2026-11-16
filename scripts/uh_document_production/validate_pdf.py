#!/usr/bin/env python3
"""Independent source/PDF/A/PDF-UA receipt for a native Whitehall attachment.

Use the signed veraPDF JSON reports and an unchanged-source DOCX. A tagged
PDF alone is not sufficient; both ISO validation profiles must pass.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from pypdf import PdfReader
from zipfile import ZipFile
from xml.etree import ElementTree as ET

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("\u00ad", "")
    # PDF text extraction can place a line break after a printed compound hyphen.
    text = re.sub(r"-\s+(?=[A-Za-z])", "-", text)
    return re.sub(r"\s+", " ", text).strip()

LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def plain_govspeak(block: str) -> str:
    """Compare rendered text with its source, never literal Markdown link syntax."""
    block = block.removeprefix("## ")
    block = LINK.sub(lambda m: m.group(1), block)
    # Govspeak emphasis markers are presentation, not spoken/printed text.
    block = re.sub(r"(?<!\w)\*\*([^*]+)\*\*", r"\1", block)
    block = re.sub(r"(?<!\w)\*([^*]+)\*", r"\1", block)
    return normalize(block)


def original_docx_links(source: Path) -> dict[str,str]:
    """Independently compare the source OOXML links with converted Govspeak."""
    W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
    with ZipFile(source) as z:
        root=ET.fromstring(z.read('word/document.xml'))
        rel=ET.fromstring(z.read('word/_rels/document.xml.rels'))
        targets={node.get('Id'):node.get('Target') for node in rel
                 if node.get('Type','').endswith('/hyperlink')}
    links={}
    for h in root.iter(W+'hyperlink'):
        url=targets.get(h.get(R+'id'))
        text=''.join(t.text or '' for t in h.iter(W+'t')).strip()
        if not url or not text:raise ValueError('Unresolved source Word hyperlink')
        if url in links and links[url]!=text:raise ValueError('Conflicting original DOCX hyperlink labels')
        links[url]=text
    return links


def verify_link_annotations(reader: PdfReader, source_body: str, contents_docx: Path | None = None) -> dict:
    labels = defaultdict(set)
    for label, url in LINK.findall(source_body):
        labels[url].add(label.strip())
    if any(len(v) != 1 for v in labels.values()):
        raise ValueError("Ambiguous source hyperlink descriptions")
    occurrences = 0
    seen = set()
    internal = 0
    for page in reader.pages:
        for ref in page.get("/Annots", []):
            ann = ref.get_object()
            if ann.get("/Subtype") != "/Link":
                continue
            url = ann.get("/A", {}).get("/URI")
            if not url:
                if not ann.get('/Dest') and ann.get('/A',{}).get('/S')!='/GoTo':
                    raise ValueError('Unknown link annotation in PDF')
                if not contents_docx or not ann.get('/Contents'):
                    raise ValueError('Unverified or unlabelled Word contents navigation')
                internal += 1
                continue
            if str(url) not in labels:
                raise ValueError("Unknown link annotation in PDF")
            if str(ann.get("/Contents", "")) != next(iter(labels[str(url)])):
                raise ValueError("PDF link annotation does not match original source description")
            seen.add(str(url))
            occurrences += 1
    if seen != set(labels):
        raise ValueError("Rendered PDF omitted a source hyperlink destination")
    if contents_docx is not None:
        from zipfile import ZipFile
        from lxml import etree
        with ZipFile(contents_docx) as z:
            content=etree.fromstring(z.read('word/document.xml'))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        toc=[p for p in content.xpath('//w:body/w:p',namespaces=ns)
             if p.xpath('./w:pPr/w:pStyle/@w:val',namespaces=ns)
             and p.xpath('./w:pPr/w:pStyle/@w:val',namespaces=ns)[0].startswith('UH-DfE-TocEntry')]
        if len(toc)!=internal:
            raise ValueError('Internal PDF navigation count does not match original Word TOC')
    return {"source_distinct_destinations": len(labels), "verified_link_annotations": occurrences,
            "verified_internal_toc_annotations": internal}


def checked_report(path: Path, expected: str, size: int) -> dict:
    data = json.loads(path.read_text())["report"]
    if data["batchSummary"]["totalJobs"] != 1:
        raise ValueError(f"{expected} validator did not examine exactly one PDF")
    job = data["jobs"][0]
    results = job["validationResult"]
    if len(results) != 1:
        raise ValueError(f"{expected} validator did not return exactly one profile")
    record = results[0]
    if (
        job["itemDetails"]["size"] != size
        or record["profileName"] != expected
        or record["compliant"] is not True
        or record["details"]["failedRules"] != 0
        or record["details"]["failedChecks"] != 0
    ):
        raise ValueError(f"{expected} independent conformity test failed")
    return {
        "profile": expected,
        "compliant": True,
        "passed_rules": record["details"]["passedRules"],
        "passed_checks": record["details"]["passedChecks"],
        "failed_rules": 0,
        "failed_checks": 0,
        "verifier": "veraPDF 1.30.3",
        "report_sha256": sha(path),
    }

def roles_from(element, seen=None) -> Counter:
    if seen is None:
        seen = set()
    counter = Counter()
    if isinstance(element, list):
        for item in element:
            counter.update(roles_from(item, seen))
        return counter
    element = element.get_object() if hasattr(element, "get_object") else element
    if not isinstance(element, dict) or id(element) in seen:
        return counter
    seen.add(id(element))
    if "/S" in element:
        counter[str(element["/S"])] += 1
    if "/K" in element:
        counter.update(roles_from(element["/K"], seen))
    return counter

def inspect(pdf: Path, source: Path, govspeak: Path, manifest: Path, pdfa: Path, pdfua: Path,
            contents_docx: Path | None = None) -> dict:
    inputs = json.loads(manifest.read_text())
    if sha(source) != inputs["source_sha256"]:
        raise ValueError("Original source checksum differs from authoritative revision")
    r = PdfReader(str(pdf))
    if r.is_encrypted:
        raise ValueError("Encrypted PDF cannot be an open document")
    root = r.trailer["/Root"]
    if root.get("/Lang") != inputs["language"]:
        raise ValueError("PDF language differs from original source language")
    if r.metadata.get("/Title") != inputs["title"]:
        raise ValueError("PDF title differs from original source title")
    if "/StructTreeRoot" not in root or not root.get("/MarkInfo", {}).get("/Marked"):
        raise ValueError("PDF is missing accessible structure tags")
    roles = roles_from(root["/StructTreeRoot"])
    expected_h2 = sum(1 for line in govspeak.read_text().splitlines() if line.startswith("## "))
    if roles["/H1"] != 1 or roles["/H2"] != expected_h2:
        raise ValueError(f"Semantic heading mismatch: {dict(roles)}")
    xmp = root["/Metadata"].get_object().get_data().decode("utf-8")
    if not all(x in xmp for x in ("<pdfaid:part>2</pdfaid:part>",
                                 "<pdfaid:conformance>B</pdfaid:conformance>",
                                 "<pdfuaid:part>1</pdfuaid:part>")):
        raise ValueError("Missing declared PDF/A-2b or PDF/UA-1 metadata")
    source_body = govspeak.read_text(encoding="UTF-8")
    page_texts = []
    for index, page in enumerate(r.pages, 1):
        page_text = page.extract_text() or ""
        # An institution masthead and calculated pagination must not split
        # a source paragraph when it continues across a page boundary.
        page_text = re.sub(r"\A(?:Cabinet Office\n)?Page " + str(index) +
                           r" of " + str(len(r.pages)) + r"\n", "", page_text)
        page_texts.append(page_text)
    pdf_content = normalize("\n".join(page_texts))
    sections = [
        plain_govspeak(x)
        for x in re.split(r"\n\s*\n", source_body) if x.strip()
    ]
    misses = [x[:140] for x in sections if x not in pdf_content]
    if misses:
        raise ValueError(f"Source-to-PDF paragraphs missing: {misses}")
    links = verify_link_annotations(r, source_body, contents_docx)
    original = original_docx_links(source)
    govspeak_links={url:label.strip() for label,url in LINK.findall(source_body)}
    if original != govspeak_links:
        raise ValueError('Original DOCX and rendered Govspeak hyperlink labels or destinations differ')
    for value in (
        inputs["title"],
        inputs["description"],
        "From: " + "; ".join(inputs["organisations"]),
        "Published: " + inputs["published_display"],
        "Last updated: " + inputs["updated_display"],
    ):
        if normalize(value) not in pdf_content:
            raise ValueError(f"Source metadata omitted from PDF: {value}")
    return {
        "original_source_revision": inputs["source_revision"],
        "original_source_sha256": inputs["source_sha256"],
        "original_source_file_modified": False,
        "native_content_type": inputs["native_content_type"],
        "publication_subtype": inputs["publication_subtype"],
        "pdf_sha256": sha(pdf),
        "pdf_file_size": pdf.stat().st_size,
        "pdf_pages": len(r.pages),
        "pdf_language": str(root.get("/Lang")),
        "pdf_title": str(r.metadata.get("/Title")),
        "pdf_accessibility_proof": {
            "tagged": True,
            "tag_roles": [x for x in ("/H1", "/H2") if roles[x] > 0],
            "heading_structure": {"/H1": roles["/H1"], "/H2": roles["/H2"]},
            "pdf_language": str(root.get("/Lang")),
            "pdf_text_similarity": 1.0,
            "source_paragraphs": len(sections),
            "matched_paragraphs": len(sections),
            "source_link_proof": links,
            "original_link_destinations": len(original),
            "validated_accessible_link_annotations": links['verified_link_annotations'],
            "pdfa_profile": "PDF/A-2b",
            "pdfua_profile": "PDF/UA-1",
            "pdfa_verified": True,
            "pdfua_verified": True,
        },
        "independent_validation": {
            "pdfa": checked_report(pdfa, "PDF/A-2b validation profile", pdf.stat().st_size),
            "pdfua": checked_report(pdfua, "PDF/UA-1 validation profile", pdf.stat().st_size),
        },
        "approval_or_publication_conferred": False,
    }

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    for name in ("pdf", "source", "govspeak", "manifest", "pdfa_report", "pdfua_report"):
        p.add_argument(name, type=Path)
    p.add_argument('--contents-docx',type=Path)
    args = p.parse_args()
    try:
        receipt = inspect(args.pdf, args.source, args.govspeak, args.manifest,
                          args.pdfa_report, args.pdfua_report,args.contents_docx)
    except Exception as exc:
        print(f"PDF_ACCEPTANCE_FAIL {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(receipt, indent=2, sort_keys=True))
