#!/usr/bin/env python3
"""Prepare an unchanged-source-body, semantically tagged DOCX for PDF/A export.

Only the temporary copy's style, language and verified title metadata change.
The original document, including its text and historical source file, is immutable.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
import struct
from urllib.parse import urlparse
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P = "http://schemas.openxmlformats.org/package/2006/relationships"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC = "http://purl.org/dc/elements/1.1/"
ET.register_namespace("w", W)
ET.register_namespace("r", R)
ET.register_namespace("wp", WP)
ET.register_namespace("a", A)
ET.register_namespace("pic", PIC)
ET.register_namespace("dc", DC)
ET.register_namespace("cp", CP)

# Approved GDS organisational identity is specified in the operative 11 Nov
# GDS service delivery plan. It is not a generic cross-department emblem.
GDS_IDENTITY = "Government Digital Service"
GDS_CROWN_URL = "https://www.gov.uhrblx.com/uh-brand/uh-crown-black-20261014.png"
GDS_CROWN_SHA256 = "e916d2f59d4114d99e16158d52a250f8a1aaf14f4266936211bbbedb68740100"
GDS_BORDER_RGB = "16EEEE"  # verified compiled GOV.UH GDS identity border

def q(ns: str, key: str) -> str:
    return f"{{{ns}}}{key}"

def xml(root: ET.Element) -> bytes:
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)

def _new_id(rels: bytes) -> str:
    import re
    used = set(re.findall(rb'Id="(rId[0-9]+)"', rels))
    index = 1
    while f"rId{index}".encode() in used:
        index += 1
    return f"rId{index}"


def _paragraph_texts(root: ET.Element) -> list[str]:
    return ["".join(x.text or "" for x in p.iter(q(W,"t"))) for p in root.iter(q(W,"p"))]


def _identity_parts(document, source_names, source_read, issuer: str, page_numbers: bool,
                    logo_path: Path | None, logo_sha: str | None, logo_evidence: str | None) -> dict:
    """Add an issuer masthead and calculated pagination to a temporary Word copy.

    Issuer must already be stated in the authoritative source. The asset is only
    accepted against its exact bytes and an externally verified approval record.
    """
    rel_path = "word/_rels/document.xml.rels"
    rels = source_read(rel_path)
    ctype = source_read("[Content_Types].xml")
    if b"</Relationships>" not in rels or b"</Types>" not in ctype:
        raise ValueError("Unsupported DOCX relationship serialization")
    parts = {}
    sect = document.find(f"./{q(W,'body')}/{q(W,'sectPr')}")
    if sect is None:
        raise ValueError("Source document has no identifiable section formatting")
    def add_section_part(kind: str, payload: bytes):
        nonlocal rels, ctype
        filename = f"{kind}1.xml"
        if f"word/{filename}" in source_names:
            raise ValueError("Source already has this section part; do not overwrite it")
        rid = _new_id(rels)
        typ = f"{REL}/{kind}"
        rel = (f'<Relationship Id="{rid}" Type="{typ}" Target="{filename}"/>').encode()
        rels = rels.replace(b"</Relationships>", rel+b"</Relationships>", 1)
        ct = (f'<Override PartName="/word/{filename}" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.{kind}+xml"/>').encode()
        ctype = ctype.replace(b"</Types>", ct+b"</Types>", 1)
        ref = ET.Element(q(W,kind+"Reference"))
        ref.set(q(W,"type"),"default")
        ref.set(q(R,"id"),rid)
        sect.insert(0,ref)
        parts[f"word/{filename}"] = payload
        return filename
    if issuer:
        hdr = ET.Element(q(W,"hdr"))
        para = ET.SubElement(hdr,q(W,"p"))
        if issuer == GDS_IDENTITY:
            # Source-verified crown + brand border + natural readable name,
            # rather than the inherited UK government crest.
            pr = ET.SubElement(para, q(W,"pPr"))
            border = ET.SubElement(pr, q(W,"pBdr"))
            left = ET.SubElement(border, q(W,"left"))
            for key,value in (("val","single"),("color",GDS_BORDER_RGB),("sz","18"),("space","8")):
                left.set(q(W,key),value)
        rp = ET.SubElement(para,q(W,"r"))
        rpr = ET.SubElement(rp,q(W,"rPr")); ET.SubElement(rpr,q(W,"b"))
        if issuer == GDS_IDENTITY:
            ET.SubElement(rpr,q(W,"sz")).set(q(W,"val"),"24")
        ET.SubElement(rp,q(W,"t")).text = ("  " if issuer == GDS_IDENTITY else "") + issuer
        if issuer == GDS_IDENTITY and not logo_path:
            raise ValueError("GDS publisher identity requires its verified UH crown asset")
        if logo_path:
            if not logo_sha or not logo_evidence or urlparse(logo_evidence).scheme != 'https':
                raise ValueError("Approved identity requires checksum and competent approval record URI")
            logo = logo_path.read_bytes()
            if issuer == GDS_IDENTITY and (logo_sha != GDS_CROWN_SHA256 or logo_evidence != GDS_CROWN_URL):
                raise ValueError("GDS official source requires its original verified UH crown, not an arbitrary crest")
            if not logo.startswith(b"\x89PNG\r\n\x1a\n") or hashlib.sha256(logo).hexdigest() != logo_sha:
                raise ValueError("Issuer identity image is missing, unsafe or fails its source checksum")
            if 'word/media/uh-institutional-logo.png' in source_names:
                raise ValueError("Original already has this identity asset")
            width, height = struct.unpack('>II',logo[16:24])
            if not (16 <= width <= 10000 and 16 <= height <= 10000):
                raise ValueError("Issuer logo PNG dimensions are invalid")
            cx = (340000 if issuer == GDS_IDENTITY else min(1400000, int(750000*width/height)))
            cy = int(cx*height/width)
            # The image is decorative here: issuer is also readable as text.
            wp = (f'<w:r xmlns:w="{W}" xmlns:r="{R}" xmlns:wp="{WP}" xmlns:a="{A}" xmlns:pic="{PIC}">'
                  f'<w:drawing><wp:inline><wp:extent cx="{cx}" cy="{cy}"/>'
                  '<wp:docPr id="22" name="Institutional identity" descr=""/>'
                  '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
                  '<pic:pic><pic:nvPicPr><pic:cNvPr id="1" name="Issuer logo"/><pic:cNvPicPr/></pic:nvPicPr>'
                  '<pic:blipFill><a:blip r:embed="rId1"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
                  f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
                  '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>')
            para.insert(1 if issuer == GDS_IDENTITY else 0, ET.fromstring(wp))
            parts['word/media/uh-institutional-logo.png'] = logo
            parts['word/_rels/header1.xml.rels'] = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<Relationships xmlns="{P}"><Relationship Id="rId1" Type="{R}/image" Target="media/uh-institutional-logo.png"/></Relationships>').encode()
            if b'Extension="png"' not in ctype:
                ctype=ctype.replace(b'</Types>',b'<Default Extension="png" ContentType="image/png"/></Types>',1)
        add_section_part('header',xml(hdr))
    if page_numbers:
        ftr = ET.Element(q(W,"ftr"))
        para=ET.SubElement(ftr,q(W,"p"))
        pr=ET.SubElement(para,q(W,"pPr")); ET.SubElement(pr,q(W,"jc")).set(q(W,"val"),"right")
        def word_run(value):
            run = ET.SubElement(para,q(W,"r")); text=ET.SubElement(run,q(W,"t")); text.text=value
            text.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
        word_run('Page ')
        for field,trailer in (("PAGE"," of "),("NUMPAGES",None)):
            fld=ET.SubElement(para,q(W,"fldSimple"));fld.set(q(W,"instr"),field)
            rv=ET.SubElement(fld,q(W,"r")); ET.SubElement(rv,q(W,"t")).text='1'
            if trailer:word_run(trailer)
        add_section_part('footer',xml(ftr))
    parts[rel_path]=rels
    parts['[Content_Types].xml']=ctype
    parts['word/document.xml']=xml(document)
    return parts


def run(src: Path, dst: Path, language: str, title: str, *, issuer: str = "",
        page_numbers: bool = False, logo_path: Path | None = None,
        logo_sha: str | None = None, logo_evidence: str | None = None) -> dict:
    if src.resolve() == dst.resolve():
        raise ValueError("Cannot overwrite original source")
    if not src.is_file() or not src.read_bytes().startswith(b"PK"):
        raise ValueError("A genuine DOCX source is required")
    if language != "en-GB":
        raise ValueError("Source language must be en-GB")
    if not title.strip():
        raise ValueError("Authoritative source title is required")
    source_sha = hashlib.sha256(src.read_bytes()).hexdigest()
    with ZipFile(src) as source:
        names = set(source.namelist())
        required = {"word/styles.xml", "word/document.xml", "[Content_Types].xml", "_rels/.rels"}
        if required - names:
            raise ValueError("Source is missing Word document package elements")
        document_bytes = source.read("word/document.xml")
        document = ET.fromstring(document_bytes)
        original_paragraphs = _paragraph_texts(document)
        first_title = []
        for paragraph in document.iter(q(W, "p")):
            style = paragraph.find(f"./{q(W,'pPr')}/{q(W,'pStyle')}")
            if style is None or style.get(q(W, "val")) != "Title":
                continue
            first_title.append("".join(node.text or "" for node in paragraph.iter(q(W, "t"))))
        if title not in first_title:
            raise ValueError("Declared title does not match the original Title paragraph")

        styles = ET.fromstring(source.read("word/styles.xml"))
        style_by_id = {s.get(q(W, "styleId")): s for s in styles.findall(q(W, "style"))}
        if "Title" not in style_by_id or "Heading1" not in style_by_id:
            raise ValueError("Original source lacks Title or Heading1 styles")
        for style_id, level in (("Title", "0"), ("Heading1", "1")):
            style = style_by_id[style_id]
            ppr = style.find(q(W, "pPr"))
            if ppr is None:
                ppr = ET.SubElement(style, q(W, "pPr"))
            outline = ppr.find(q(W, "outlineLvl"))
            if outline is None:
                outline = ET.SubElement(ppr, q(W, "outlineLvl"))
            outline.set(q(W, "val"), level)

        defaults = styles.find(f".//{q(W,'docDefaults')}/{q(W,'rPrDefault')}/{q(W,'rPr')}")
        if defaults is None:
            wrapper = styles.find(q(W, "docDefaults"))
            if wrapper is None:
                wrapper = ET.SubElement(styles, q(W, "docDefaults"))
            r_default = wrapper.find(q(W, "rPrDefault"))
            if r_default is None:
                r_default = ET.SubElement(wrapper, q(W, "rPrDefault"))
            defaults = r_default.find(q(W, "rPr"))
            if defaults is None:
                defaults = ET.SubElement(r_default, q(W, "rPr"))
        lang = defaults.find(q(W, "lang"))
        if lang is None:
            lang = ET.SubElement(defaults, q(W, "lang"))
        for attr in ("val", "eastAsia", "bidi"):
            lang.set(q(W, attr), language)

        changes = {"word/styles.xml": xml(styles)}
        if issuer or page_numbers:
            if issuer and not any(issuer in text for text in original_paragraphs[:8]):
                raise ValueError("Issuer is not present in the original source metadata")
            changes.update(_identity_parts(document,names,source.read,issuer,page_numbers,logo_path,logo_sha,logo_evidence))
        # Metadata is absent in this Google Docs export. Supply the verified
        # title only; never invent an original named author or publication date.
        if "docProps/core.xml" in names:
            props = ET.fromstring(source.read("docProps/core.xml"))
        else:
            props = ET.Element(q(CP, "coreProperties"))
        title_element = props.find(q(DC, "title"))
        if title_element is None:
            title_element = ET.SubElement(props, q(DC, "title"))
        title_element.text = title
        changes["docProps/core.xml"] = xml(props)

        if "docProps/core.xml" not in names:
            # Preserve the package root's default XML namespace. LibreOffice's
            # Word importer rejects otherwise valid ns0-prefixed relationship
            # roots in some DOCX packages, so do not reserialize these files.
            types_raw = source.read("[Content_Types].xml")
            rels_raw = source.read("_rels/.rels")
            if b"</Types>" not in types_raw or b"</Relationships>" not in rels_raw:
                raise ValueError("Unsupported DOCX relationship namespace layout")
            relationships = ET.fromstring(rels_raw)
            used = {r.get("Id") for r in relationships}
            index = 1
            while f"rId{index}" in used:
                index += 1
            new_type = (
                b'<Override PartName="/docProps/core.xml" '
                b'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
            )
            new_relationship = (
                f'<Relationship Id="rId{index}" Type="{REL}/metadata/core-properties" '
                'Target="docProps/core.xml"/>'
            ).encode("utf-8")
            changes["[Content_Types].xml"] = types_raw.replace(
                b"</Types>", new_type + b"</Types>", 1
            )
            changes["_rels/.rels"] = rels_raw.replace(
                b"</Relationships>", new_relationship + b"</Relationships>", 1
            )
        dst.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(dst, "w", compression=ZIP_DEFLATED) as target:
            for item in source.infolist():
                target.writestr(item, changes.pop(item.filename, source.read(item.filename)))
            for filename, data in changes.items():
                target.writestr(filename, data)

    with ZipFile(dst) as ready:
        if issuer or page_numbers:
            if _paragraph_texts(ET.fromstring(ready.read("word/document.xml"))) != original_paragraphs:
                raise ValueError("Original paragraph content was modified by page identity fields")
        elif ready.read("word/document.xml") != document_bytes:
            raise ValueError("Original text, date or section layout changed")
    if hashlib.sha256(src.read_bytes()).hexdigest() != source_sha:
        raise ValueError("Original source was modified")
    return {
        "original_sha256": source_sha,
        "prepared_sha256": hashlib.sha256(dst.read_bytes()).hexdigest(),
        "language": language,
        "title": title,
        "semantic_headings": {"Title": "H1", "Heading1": "H2"},
        "body_xml_unchanged": not (issuer or page_numbers),
        "source_paragraph_text_unchanged": True,
        "issuer_masthead": issuer or None,
        "pagination_fields": bool(page_numbers),
        "issuer_logo_embedded": bool(logo_path),
        "issuer_logo_sha256": logo_sha if logo_path else None,
        "issuer_logo_evidence": logo_evidence if logo_path else None,
        "issuer_logo_approval_verified_in_native_editor": False,
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("original", type=Path)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("--language", default="en-GB")
    parser.add_argument("--title", required=True)
    parser.add_argument("--issuer", default="")
    parser.add_argument("--page-numbers", action="store_true")
    parser.add_argument("--logo-file", type=Path)
    parser.add_argument("--logo-sha256")
    parser.add_argument("--logo-evidence")
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.original, args.prepared, args.language, args.title,
            issuer=args.issuer, page_numbers=args.page_numbers,
            logo_path=args.logo_file, logo_sha=args.logo_sha256,
            logo_evidence=args.logo_evidence), sort_keys=True))
    except Exception as exc:
        print(f"SOURCE_PREP_FAIL {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
