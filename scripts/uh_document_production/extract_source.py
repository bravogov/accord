#!/usr/bin/env python3
"""Preserve a verified Google Docs DOCX revision as native Whitehall Govspeak.

Derive title, summary, issuing organisations, first and last publication dates
and all six sections solely from the exported original. Never paraphrase.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
VALID = {"Normal", "Title", "Subtitle", "Heading1"}

def visible_run_text(element):
    result = []
    for node in element.iter():
        if node.tag == f"{W}t":
            result.append(node.text or "")
        elif node.tag == f"{W}tab":
            result.append("\t")
        elif node.tag == f"{W}br":
            result.append("\n")
    return "".join(result)

def paragraphs(source: Path):
    with ZipFile(source) as docx:
        root = ET.fromstring(docx.read("word/document.xml"))
        relationships = ET.fromstring(docx.read("word/_rels/document.xml.rels"))
        links = {item.get("Id"): item.get("Target") for item in relationships}
        body = root.find(f"{W}body")
        if body is None:
            raise ValueError("Original DOCX has no Word body")
        if any(child.tag != f"{W}p" and child.tag != f"{W}sectPr" for child in body):
            raise ValueError("Original source contains a table or unsupported block; manual source-faithful conversion required")
        for paragraph in body.findall(f"{W}p"):
            ppr = paragraph.find(f"{W}pPr")
            pstyle = ppr.find(f"{W}pStyle") if ppr is not None else None
            style = pstyle.get(f"{W}val") if pstyle is not None else "Normal"
            if style not in VALID:
                raise ValueError(f"Unsupported source style: {style}")
            if paragraph.find(f".//{W}drawing") is not None:
                raise ValueError("Inline drawing requires a separate accessible text alternative")
            parts = []
            for child in paragraph:
                if child.tag == f"{W}pPr":
                    continue
                if child.tag == f"{W}hyperlink":
                    destination = links.get(child.get(f"{R}id"))
                    label = visible_run_text(child)
                    if not destination or not label or not destination.startswith(("https://","http://")):
                        raise ValueError("Unresolved or unsupported original Word hyperlink")
                    if any(x in label for x in "[]") or any(x in destination for x in " ()"):
                        raise ValueError("Hyperlink requires lossless Markdown encoding")
                    parts.append(f"[{label}]({destination})")
                else:
                    parts.append(visible_run_text(child))
            text = "".join(parts)
            if text.strip():
                yield style, text

def run(src: Path, govspeak_out: Path, manifest_out: Path,
        revision: str, source_uri: str, modified_at: str):
    items = list(paragraphs(src))
    if len(items) < 20:
        raise ValueError("Short source document")
    expected = ["Normal", "Title", "Subtitle", "Normal", "Normal", "Normal"]
    if [typ for typ, _ in items[:6]] != expected:
        raise ValueError("Missing original guide title, subtitle, organisation or date")
    label = items[0][1]
    title = items[1][1]
    summary = items[2][1]
    from_text = items[3][1]
    published = items[4][1]
    updated = items[5][1]
    if label != "Guidance" or not from_text.startswith("From: ") or        not published.startswith("Published: ") or        not updated.startswith("Last updated: "):
        raise ValueError("Original metadata labels have changed")
    organisations = [x.strip() for x in from_text[len("From: "):].split(";")]
    if len(organisations) != 3 or any(not x for x in organisations):
        raise ValueError("Issuing organisations cannot be inferred")
    body = items[6:]
    headings = [text for kind,text in body if kind == "Heading1"]
    if len(headings) != 6:
        raise ValueError(f"Expected six actual section headings, found {len(headings)}")
    for style, text in body:
        if style not in {"Heading1", "Normal"}:
            raise ValueError(f"Unexpected body formatting: {style}")
        if text.startswith("# ") or text.startswith("## "):
            raise ValueError("Pre-embedded Markdown requires explicit treatment")
    full_govspeak = "\n\n".join(("## " + text) if style == "Heading1" else text
                                for style, text in body) + "\n"
    manifest = {
      "status": "unpublished_candidate",
      "source_uri": source_uri,
      "source_revision": "google-drive-revision-" + revision,
      "source_modified_at": modified_at,
      "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
      "source_label": label,
      "native_content_type": "Publication",
      "publication_subtype": "guidance",
      "title": title,
      "description": summary,
      "organisations": organisations,
      "published_display": published[len("Published: "):],
      "updated_display": updated[len("Last updated: "):],
      "html_attachment": True,
      "pdf_required": True,
      "language": "en-GB"
    }
    govspeak_out.write_text(full_govspeak, encoding="UTF-8")
    manifest_out.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="UTF-8")
    print(json.dumps({
      "source_revision":revision,
      "source_sha256":manifest["source_sha256"],
      "title":title,
      "body_characters":len(full_govspeak),
      "sections":headings,
      "body_paragraphs":sum(1 for style,_ in body if style=="Normal"),
      "issuing_organisations":organisations,
      "published_display":manifest["published_display"],
      "updated_display":manifest["updated_display"]
    },ensure_ascii=False))

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    for field in ("source","govspeak","manifest"):
        p.add_argument(field,type=Path)
    p.add_argument("--revision",required=True)
    p.add_argument("--source-uri",required=True)
    p.add_argument("--modified-at",required=True)
    x=p.parse_args()
    run(x.source,x.govspeak,x.manifest,x.revision,x.source_uri,x.modified_at)
