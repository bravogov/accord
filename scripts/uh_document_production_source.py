#!/usr/bin/env python3
"""Build candidate Whitehall HTML/Govspeak from a preserved OOXML revision.

No publishing, database, account access or substantive text rewriting.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
from lxml import etree
from zipfile import ZipFile
from urllib.parse import urlparse

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"w": W, "r": R}


def inline_markup(paragraph, links, mode="govspeak"):
    """Preserve text, strong/emphasis and real hyperlink targets; never drop unsupported fields."""
    output = []
    for element in paragraph:
        tag = etree.QName(element).localname
        if tag in ("pPr", "bookmarkStart", "bookmarkEnd", "proofErr"):
            continue
        if tag not in ("r", "hyperlink"):
            raise ValueError(f"Unsupported paragraph content: {tag}")
        url = None
        if tag == "hyperlink":
            key = element.get(f"{{{R}}}id")
            if not key or key not in links:
                raise ValueError("Unresolved hyperlink in source")
            url = links[key]
            if urlparse(url).scheme not in ("https", "http"):
                raise ValueError("Unsafe hyperlink target")
        segments = []
        for run in ([element] if tag == "r" else element):
            if etree.QName(run).localname != "r":
                raise ValueError("Unsupported hyperlink child")
            pieces = []
            for child in run:
                kind = etree.QName(child).localname
                if kind == "t":
                    pieces.append(child.text or "")
                elif kind == "tab":
                    pieces.append("\t")
                elif kind in ("rPr",):
                    continue
                elif kind in ("br", "cr"):
                    pieces.append("\n")
                else:
                    raise ValueError(f"Unsupported inline document feature: {kind}")
            part = "".join(pieces)
            props = run.find(f"{{{W}}}rPr")
            if part and props is not None:
                bold = props.find(f"{{{W}}}b")
                italics = props.find(f"{{{W}}}i")
                if bold is not None and bold.get(f"{{{W}}}val", "1") not in ("0", "false", "off"):
                    part = f"**{part}**" if mode == "govspeak" else f"<strong>{html.escape(part)}</strong>"
                elif mode == "html":
                    part = html.escape(part)
                if italics is not None and italics.get(f"{{{W}}}val", "1") not in ("0", "false", "off"):
                    part = f"*{part}*" if mode == "govspeak" else f"<em>{part}</em>"
            elif mode == "html":
                part = html.escape(part)
            segments.append(part)
        value = "".join(segments)
        if url is not None:
            if mode == "govspeak":
                value = f"[{value}]({url})"
            else:
                value = f'<a href="{html.escape(url, quote=True)}">{value}</a>'
        output.append(value)
    return "".join(output)


def source_links(archive):
    path = "word/_rels/document.xml.rels"
    if path not in archive.namelist():
        return {}
    root = etree.fromstring(archive.read(path))
    return {node.get("Id"): node.get("Target") for node in root
            if node.get("Type", "").endswith("/hyperlink") and node.get("TargetMode") == "External"}


def build(source, manifest, destination):
    data = json.loads(Path(manifest).read_text())
    src = Path(source)
    if data.get("status") != "unpublished_candidate":
        raise ValueError("Not an unpublished candidate")
    if src.suffix.lower() != ".docx" or not src.is_file():
        raise ValueError("Not an original OOXML file")
    actual = hashlib.sha256(src.read_bytes()).hexdigest()
    if actual != data.get("source_sha256"):
        raise ValueError("Source revision mismatch")
    if data.get("native_content_type") not in ("Publication", "Consultation", "CallForEvidence"):
        raise ValueError("Native HTML attachments unavailable for this product type")
    if src.stat().st_size > 30 * 1024 * 1024:
        raise ValueError("Source too large")
    with ZipFile(src) as archive:
        entries = archive.infolist()
        if archive.testzip() is not None or sum(x.file_size for x in entries) > 150*1024*1024:
            raise ValueError("Unsafe or damaged source")
        if any(x.filename.startswith("/") or ".." in x.filename.split("/") for x in entries):
            raise ValueError("Unsafe archive path")
        root = etree.fromstring(archive.read("word/document.xml"))
        links = source_links(archive)
    blocks = []
    for node in root.xpath("//w:body/*", namespaces=NS):
        kind = etree.QName(node).localname
        if kind == "sectPr":
            continue
        if kind == "tbl":
            rows = []
            for tr in node.xpath("./w:tr", namespaces=NS):
                cells = []
                for tc in tr.xpath("./w:tc", namespaces=NS):
                    paragraphs = tc.xpath("./w:p", namespaces=NS)
                    if len(paragraphs) != 1 or tc.xpath("./w:tbl", namespaces=NS):
                        raise ValueError("Complex tables require native editorial handling")
                    cells.append((inline_markup(paragraphs[0],links),inline_markup(paragraphs[0],links,"html")))
                if rows and len(cells) != len(rows[0]):
                    raise ValueError("Irregular table requires native editorial handling")
                rows.append(cells)
            if len(rows) < 2 or not rows[0]:
                raise ValueError("Tables require a header and body")
            blocks.append(("Table", rows, None, None))
            continue
        if kind != "p":
            raise ValueError(f"Unsupported source block: {kind}")
        value = "".join(node.xpath(".//w:t/text()", namespaces=NS))
        if not value.strip():
            continue
        styles = node.xpath("./w:pPr/w:pStyle/@w:val", namespaces=NS)
        style = styles[0] if styles else "Normal"
        if node.xpath(".//w:drawing|.//w:pict|.//w:footnoteReference|.//w:endnoteReference|.//w:instrText|.//w:fldChar|.//w:ins|.//w:del|.//w:oMath",namespaces=NS):
            raise ValueError("Source has an image, note, field, revision or equation requiring native review")
        number = node.xpath("./w:pPr/w:numPr/w:numId/@w:val",namespaces=NS)
        list_type = "ol" if (number and style.lower().find("number")>=0) else ("ul" if number or style.lower().startswith("listbullet") else None)
        blocks.append((style, value, inline_markup(node,links), (inline_markup(node,links,"html"), list_type)))
    expected = [
        data["source_label"], data["title"], data["description"],
        "From: " + "; ".join(data["organisations"]),
        "Published: " + data["published_display"],
        "Last updated: " + data["updated_display"]]
    if [v for _,v,_,_ in blocks[:6]] != expected:
        raise ValueError("Source metadata is not verbatim")
    if not any(s == "Heading1" for s,_,_,_ in blocks):
        raise ValueError("No semantically styled heading")
    body, page = [], []
    in_body = False
    current_list = None
    for style, value, rich, extra in blocks[6:]:
        if style == "Table":
            if not in_body:
                raise ValueError("Table before the first section heading")
            rows = value
            safe = lambda x: x.replace("|", "\\|").replace("\n", " ")
            body.append("| " + " | ".join(safe(x[0]) for x in rows[0]) + " |\n| " + " | ".join("---" for _ in rows[0]) + " |\n" + "\n".join("| " + " | ".join(safe(x[0]) for x in row) + " |" for row in rows[1:]))
            page.append("<table><thead><tr>"+"".join("<th scope='col'>"+x[1]+"</th>" for x in rows[0])+"</tr></thead><tbody>"+"".join("<tr>"+"".join("<td>"+x[1]+"</td>" for x in row)+"</tr>" for row in rows[1:])+"</tbody></table>")
            continue
        html_rich, list_type = extra
        if current_list and list_type != current_list:
            page.append(f"</{current_list}>")
            current_list = None
        if style.startswith("Heading"):
            in_body = True
            original = int(style.replace("Heading", ""))
            level = original + 1
            if level > 6:
                raise ValueError("Too-deep heading")
            body.append("#"*level + " " + rich)
            page.append(f"<h{level}>{html_rich}</h{level}>")
        elif in_body:
            if list_type:
                if not current_list:
                    page.append(f"<{list_type}>")
                    current_list = list_type
                body.append(("1. " if list_type == "ol" else "* ")+rich)
                page.append("<li>"+html_rich+"</li>")
            else:
                body.append(rich)
                page.append("<p>"+html_rich+"</p>")
    if current_list:
        page.append(f"</{current_list}>")
    if not in_body:
        raise ValueError("No section body")
    out = Path(destination)
    out.mkdir(parents=True,exist_ok=True)
    (out/"native-govspeak.txt").write_text("\n\n".join(body)+"\n", encoding="utf-8")
    preview = "<!doctype html><html lang='en-GB'><head><meta charset='utf-8'><title>"+html.escape(data["title"])+"</title></head><body><main><article>"
    preview += "<p>"+html.escape(data["source_label"])+"</p><h1>"+html.escape(data["title"])+"</h1>"
    preview += "<p>"+html.escape(data["description"])+"</p>"
    preview += "<p>"+html.escape(expected[3])+"</p><p>"+html.escape(expected[4])+"</p><p>"+html.escape(expected[5])+"</p>"
    preview += "".join(page)+"</article></main></body></html>"
    (out/"accessible-html-preview.html").write_text(preview,encoding="utf-8")
    receipt = {
        "status":"unpublished_candidate", "type":data["native_content_type"],
        "source_revision":data["source_revision"], "source_sha256":actual,
        "source_uri":data["source_uri"],"original_published_date":data["published_display"],
        "original_updated_date":data["updated_display"],
        "native_cms_document_id":None, "native_edition_id":None,
        "native_html_attachment_id":None,"native_file_attachment_id":None,
        "asset_manager_id":None,"public_url":None,
        "note":"Preview files, not native publishing IDs or editorial approval",
    }
    (out/"source-receipt.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
    return receipt

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("source")
    p.add_argument("manifest")
    p.add_argument("output")
    a = p.parse_args()
    print(json.dumps(build(a.source,a.manifest,a.output)))
