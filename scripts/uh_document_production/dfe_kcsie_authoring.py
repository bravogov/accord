#!/usr/bin/env python3
"""Source-faithful DfE KCSIE Word publication production, candidate only.

Use ONLY independently approved DfE heraldic art; never use the GOV.UK crest
or infer approval from a public page CSS class. Authoritative text, tables,
images, footnotes, fields and diagrams remain in the input Word body. The
application adds cover, calculated contents, consistent styles and pagination.
The original source is never overwritten and nothing is published.
"""
from __future__ import annotations
import argparse, hashlib, json, re, struct
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree

W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG='http://schemas.openxmlformats.org/package/2006/relationships'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
PIC='http://schemas.openxmlformats.org/drawingml/2006/picture'
WP='http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'
NS={'w':W}
def q(k):return '{'+W+'}'+k

def elem(parent,tag,text=None,**attrs):
    e=etree.SubElement(parent,q(tag)) if parent is not None else etree.Element(q(tag))
    for k,v in attrs.items():e.set(q(k),str(v))
    if text is not None:e.text=str(text)
    return e

def ptext(p): return ''.join(p.xpath('.//w:t/text()',namespaces=NS))
def verify_original(source, manifest):
    if not source.is_file() or source.suffix.lower()!='.docx':raise ValueError('An original DOCX source is required')
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != manifest.get('source_sha256'):raise ValueError('Source checksum differs from approved revision')
    if manifest.get('status')!='unpublished_candidate':raise ValueError('Only an unpublished candidate is supported')
    if manifest.get('organisation')!='Department for Education':raise ValueError('Wrong issuing organisation')
    if manifest.get('kind') not in ('full','part-one'):raise ValueError('Only full guidance or Part One are supported')
    if not manifest.get('title') or not manifest.get('subtitle') or not manifest.get('edition_month'):raise ValueError('Document identity fields missing')
    if not re.fullmatch(r'[A-Z][a-z]+ 20\d{2}',manifest['edition_month']):raise ValueError('Edition month not in publication format')
    if manifest.get('contains_official_content') is not True:raise ValueError('Requires source worker acknowledgement of substantive original')
    if not manifest.get('qa_only_fixture'):
        if (manifest.get('source_content_status')!='legislation_verified' or
            manifest.get('uk_source_adaptations_verified') is not True or
            manifest.get('unapproved_uk_heraldry_removed') is not True or
            not manifest.get('competent_issuing_department_source_url','').startswith('https://')):
            raise ValueError('Original UH DfE law, territorial references and legacy UK branding not yet verified')
    with ZipFile(source) as z:
        names=set(z.namelist())
        root=etree.fromstring(z.read('word/document.xml'))
        para=[ptext(x) for x in root.xpath('//w:body/w:p',namespaces=NS)]
        if not manifest.get('qa_only_fixture'):
            required=['Summary','The status of this guidance','About this guidance','Part one']
            if manifest['kind']=='full':
                required+=['Part two','Part three','Part four','Part five','Annex A','Annex B','Annex C']
            absent=[x for x in required if not any(x.casefold() in p.casefold() for p in para)]
            if absent:raise ValueError('KCSIE source lacks necessary structural sections: '+', '.join(absent))
        for node in root.xpath('//*[local-name()="docPr"]'):
            # The W12 identity added later is decorative and the issuer is text.
            description=(node.get('descr') or node.get('title') or '').strip()
            if not description:
                raise ValueError('Source diagram or image has no accessible alternative text')
        for ref in root.xpath('//*[local-name()="footnoteReference"]'):
            if 'word/footnotes.xml' not in names:raise ValueError('Missing original footnote definitions')
        for ref in root.xpath('//*[local-name()="endnoteReference"]'):
            if 'word/endnotes.xml' not in names:raise ValueError('Missing original endnote definitions')
    return digest

def approved_identity(path,record):
    if not path or not record:raise ValueError('No authenticated UH DfE heraldic logo source')
    if record.get('institution')!='Department for Education' or record.get('approved_for')!='official_word_pdf_documents' or record.get('approval_status')!='approved':
        raise ValueError('DfE document identity not approved by competent source')
    if not record.get('approval_record_url','').startswith('https://') or not record.get('competent_issuer'):
        raise ValueError('Identity authority and approval record missing')
    if not path.is_file() or not path.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('Identity must be a genuine raster PNG from approved original')
    data=path.read_bytes()
    if hashlib.sha256(data).hexdigest()!=record.get('sha256'):
        raise ValueError('Approved logo checksum differs from original')
    width,height=struct.unpack('>II',data[16:24])
    if not (32<=width<=8000 and 32<=height<=8000):raise ValueError('Logo dimensions invalid')
    return data,width,height

def set_style(styles,styleid,size,color='111111',bold=False,space_before=0,space_after=100,keep=False):
    # Edit actual Word paragraph style, preserving any unrelated original settings.
    style=styles.xpath(f'./w:style[@w:styleId="{styleid}"]',namespaces=NS)
    if style:st=style[0]
    else:
        st=elem(styles,'style',type='paragraph',styleId=styleid)
        elem(st,'name',val=styleid)
    rp=st.find(q('rPr'))
    if rp is None:rp=elem(st,'rPr')
    for tag in ('sz','szCs','color','b','rFonts'):
        e=rp.find(q(tag))
        if e is not None:rp.remove(e)
    elem(rp,'rFonts',ascii='Arial',hAnsi='Arial',cs='Arial')
    elem(rp,'sz',val=size*2)
    elem(rp,'szCs',val=size*2)
    elem(rp,'color',val=color)
    if bold:elem(rp,'b')
    pp=st.find(q('pPr'))
    if pp is None:pp=elem(st,'pPr')
    sp=pp.find(q('spacing'))
    if sp is None:sp=elem(pp,'spacing')
    sp.set(q('before'),str(space_before));sp.set(q('after'),str(space_after))
    if keep and pp.find(q('keepNext')) is None:elem(pp,'keepNext')
    return st

def para(text,style=None,before=None,after=None,breakpage=False):
    p=etree.Element(q('p'))
    pp=elem(p,'pPr')
    if style:elem(pp,'pStyle',val=style)
    if before is not None or after is not None:
        sp=elem(pp,'spacing')
        if before is not None:sp.set(q('before'),str(before))
        if after is not None:sp.set(q('after'),str(after))
    r=elem(p,'r')
    if breakpage:elem(r,'br',type='page')
    else:elem(r,'t',text)
    return p

def add_text_to_p(p,text):elem(elem(p,'r'),'t',text)
def field_p(instruction,style=None):
    p=para('',style)
    r=p.find(q('r'));r.remove(r.find(q('t')))
    ch=elem(r,'fldChar',fldCharType='begin')
    instr=elem(elem(p,'r'),'instrText',instruction)
    instr.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
    elem(elem(p,'r'),'fldChar',fldCharType='separate')
    elem(elem(p,'r'),'t','Update field in Word before editorial sign-off')
    elem(elem(p,'r'),'fldChar',fldCharType='end')
    return p

def make_image_part(logo,width,height,relid):
    cx=1600000;cy=int(cx*height/width)
    inline=etree.fromstring((f'<w:r xmlns:w="{W}" xmlns:r="{R}" xmlns:wp="{WP}" xmlns:a="{A}" xmlns:pic="{PIC}">'
      f'<w:drawing><wp:inline><wp:extent cx="{cx}" cy="{cy}"/><wp:docPr id="2" name="DfE official identity" descr=""/>'
      '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic>'
      '<pic:nvPicPr><pic:cNvPr id="1" name="Official DfE heraldic identity"/><pic:cNvPicPr/></pic:nvPicPr>'
      f'<pic:blipFill><a:blip r:embed="{relid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
      f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
      '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r>').encode())
    return inline

def build(source:Path,manifest_path:Path,identity_path:Path,approval_path:Path,destination:Path,test_fixture:bool=False):
    manifest=json.loads(manifest_path.read_text())
    sha=verify_original(source,manifest)
    if test_fixture:
        if manifest.get('qa_only_fixture') is not True:raise ValueError('Fixture mode requires QA-only source manifest')
        logo=identity_path.read_bytes()
        if not logo.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Fixture image must be PNG')
        width,height=struct.unpack('>II',logo[16:24])
        ident={'approval_status':'NOT APPROVED - QA ONLY','sha256':hashlib.sha256(logo).hexdigest()}
    else:
        ident=json.loads(approval_path.read_text())
        logo,width,height=approved_identity(identity_path,ident)
    with ZipFile(source) as z:
        members={i.filename:z.read(i.filename) for i in z.infolist()}
    for part in ('word/document.xml','word/styles.xml','[Content_Types].xml','word/_rels/document.xml.rels'):
        if part not in members:raise ValueError('Word original package incomplete')
    doc=etree.fromstring(members['word/document.xml']);body=doc.find(q('body'))
    original_paragraphs=[ptext(p) for p in body.xpath('./w:p',namespaces=NS)]
    original_tables=len(body.xpath('.//w:tbl',namespaces=NS))
    # Source worker must provide its final legislation-verified original, not a PDF copy.
    styles=etree.fromstring(members['word/styles.xml'])
    set_style(styles,'Normal',11,space_after=120)
    for style,size,before,after in [('Heading1',17,300,130),('Heading2',14,250,100),('Heading3',12,185,80),('Heading4',11,150,55)]:
        set_style(styles,style,size,'13577A',True,before,after,True)
    set_style(styles,'UH-DfE-CoverTitle',32,'145477',True,4600,250,True)
    set_style(styles,'UH-DfE-CoverSubtitle',17,'145477',True,0,250,True)
    set_style(styles,'UH-DfE-CoverPart',16,'145477',True,500,350,True)
    set_style(styles,'UH-DfE-CoverDate',14,'224D85',True,1300,150)
    set_style(styles,'UH-DfE-Contents',17,'145477',True,0,170,True)
    for j in (1,2,3): set_style(styles,'UH-DfE-TocEntry'+str(j),10,'111111',False,0,65,False)
    members['word/styles.xml']=etree.tostring(styles,encoding='UTF-8',xml_declaration=True)
    # No text is adapted, translated or edited: insert genuine front matter before original body.
    front=[para(manifest['title'],'UH-DfE-CoverTitle')]
    front.append(para(manifest['subtitle'],'UH-DfE-CoverSubtitle'))
    if manifest['kind']=='part-one':
        front.append(para(manifest.get('part_label','Part one: Information for all school and college staff'),'UH-DfE-CoverPart'))
    front.extend([para(manifest['edition_month'],'UH-DfE-CoverDate'),para('Contents','UH-DfE-Contents'),field_p(' TOC \\o "1-3" \\h \\z \\u '),para('',breakpage=True)])
    for i,item in enumerate(front):body.insert(i,item)
    sect=body.find(q('sectPr'))
    if sect is None:sect=elem(body,'sectPr')
    pg=sect.find(q('pgSz'))
    if pg is None:pg=elem(sect,'pgSz')
    pg.set(q('w'),'11907');pg.set(q('h'),'16840') # A4
    mar=sect.find(q('pgMar'))
    if mar is None:mar=elem(sect,'pgMar')
    for attr,val in [('top',1050),('bottom',950),('left',1110),('right',960),('header',450),('footer',450)]:mar.set(q(attr),str(val))
    # Separate cover section: Word/PDF first page has no page numeral.
    # Body section owns the footer and does not inherit the cover header.
    cover_date=front[3] if manifest['kind']=='part-one' else front[2]
    cover_props=cover_date.find(q('pPr'))
    cover_sect=elem(cover_props,'sectPr')
    elem(cover_sect,'type',val='nextPage')
    cover_pg=elem(cover_sect,'pgSz',w=11907,h=16840)
    cover_mar=elem(cover_sect,'pgMar',top=1050,bottom=950,left=1110,right=960,header=450,footer=450)
    # The contents is the second physical page of the publication, even though
    # the first (cover) deliberately has no printed numeral.
    body_num=sect.find(q('pgNumType'))
    if body_num is None:body_num=elem(sect,'pgNumType')
    body_num.set(q('start'),'2')
    # Footer with physical page count. Header appears on the cover only.
    header=etree.Element(q('hdr'))
    brandline=elem(header,'p');elem(brandline,'pPr');brandline.append(make_image_part(logo,width,height,'rId1'))
    footer=etree.Element(q('ftr'));p=elem(footer,'p');pp=elem(p,'pPr');elem(pp,'jc',val='center')
    elem(elem(p,'r'),'t','')
    fld=elem(p,'fldSimple',instr='PAGE');elem(elem(fld,'r'),'t','1')
    # Preserve section attributes and all existing drawings/footnotes/source relationships.
    members['word/document.xml']=etree.tostring(doc,encoding='UTF-8',xml_declaration=True)
    members['word/header_dfe1.xml']=etree.tostring(header,encoding='UTF-8',xml_declaration=True)
    members['word/footer_dfe1.xml']=etree.tostring(footer,encoding='UTF-8',xml_declaration=True)
    blank_header=etree.Element(q('hdr'));elem(blank_header,'p')
    members['word/header_dfe_body.xml']=etree.tostring(blank_header,encoding='UTF-8',xml_declaration=True)
    members['word/media/uh-dfe-official-identity.png']=logo
    members['word/_rels/header_dfe1.xml.rels']=(f'<Relationships xmlns="{PKG}"><Relationship Id="rId1" Type="{R}/image" Target="media/uh-dfe-official-identity.png"/></Relationships>').encode()
    rel=etree.fromstring(members['word/_rels/document.xml.rels'])
    ids={r.get('Id') for r in rel}
    def newid():
        n=500
        while 'rId'+str(n) in ids:n+=1
        out='rId'+str(n);ids.add(out);return out
    for tag,kind,target,scope,owner in [
            ('headerReference','header','header_dfe1.xml','default',cover_sect),
            ('headerReference','header','header_dfe_body.xml','default',sect),
            ('footerReference','footer','footer_dfe1.xml','default',sect)]:
        rid=newid();r=etree.SubElement(rel,'{'+PKG+'}Relationship');r.set('Id',rid);r.set('Type',R+'/'+kind);r.set('Target',target)
        ref=etree.Element(q(tag));ref.set(q('type'),scope);ref.set('{'+R+'}id',rid);owner.insert(0,ref)
    members['word/_rels/document.xml.rels']=etree.tostring(rel,encoding='UTF-8',xml_declaration=True)
    members['word/document.xml']=etree.tostring(doc,encoding='UTF-8',xml_declaration=True)
    ct=etree.fromstring(members['[Content_Types].xml'])
    cns='{http://schemas.openxmlformats.org/package/2006/content-types}'
    for kind,target in [('header','header_dfe1.xml'),('header','header_dfe_body.xml'),('footer','footer_dfe1.xml')]:
        override=etree.SubElement(ct,cns+'Override')
        override.set('PartName','/word/'+target)
        override.set('ContentType','application/vnd.openxmlformats-officedocument.wordprocessingml.'+kind+'+xml')
    if not any(x.get('Extension')=='png' for x in ct):
        ext=etree.SubElement(ct,cns+'Default');ext.set('Extension','png');ext.set('ContentType','image/png')
    # A real accessible PDF requires Dublin Core title metadata. The issuer
    # and exact edition title come only from the verified manifest.
    core_path='docProps/core.xml'
    cp='http://schemas.openxmlformats.org/package/2006/metadata/core-properties'
    dc='http://purl.org/dc/elements/1.1/'
    core=etree.fromstring(members[core_path]) if core_path in members else etree.Element('{'+cp+'}coreProperties',nsmap={'cp':cp,'dc':dc})
    for tag,value in [('title',manifest['title']),('creator','Department for Education')]:
        node=core.find('{'+dc+'}'+tag)
        if node is None:node=etree.SubElement(core,'{'+dc+'}'+tag)
        node.text=value
    members[core_path]=etree.tostring(core,encoding='UTF-8',xml_declaration=True)
    if not any(x.get('PartName')=='/'+core_path for x in ct):
        x=etree.SubElement(ct,cns+'Override');x.set('PartName','/'+core_path)
        x.set('ContentType','application/vnd.openxmlformats-package.core-properties+xml')
    rootrels=etree.fromstring(members['_rels/.rels'])
    if not any(x.get('Type','').endswith('/metadata/core-properties') for x in rootrels):
        x=etree.SubElement(rootrels,'{'+PKG+'}Relationship')
        used={item.get('Id') for item in rootrels};n=800
        while 'rId'+str(n) in used:n+=1
        x.set('Id','rId'+str(n));x.set('Type',PKG+'/metadata/core-properties');x.set('Target',core_path)
    members['_rels/.rels']=etree.tostring(rootrels,encoding='UTF-8',xml_declaration=True)
    members['[Content_Types].xml']=etree.tostring(ct,encoding='UTF-8',xml_declaration=True)
    settings='word/settings.xml'
    root=etree.fromstring(members[settings]) if settings in members else etree.Element(q('settings'))
    if root.find(q('updateFields')) is None:elem(root,'updateFields',val='true')
    members[settings]=etree.tostring(root,encoding='UTF-8',xml_declaration=True)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(destination,'w',ZIP_DEFLATED) as out:
        for name,value in members.items():out.writestr(name,value)
    with ZipFile(destination) as after:
        actual=etree.fromstring(after.read('word/document.xml'))
        paras=[ptext(p) for p in actual.xpath('./w:body/w:p',namespaces=NS)]
        if paras[len(front):]!=original_paragraphs:raise ValueError('Original source paragraph content changed')
        if len(actual.xpath('.//w:tbl',namespaces=NS))!=original_tables:raise ValueError('Native source tables lost')
        for k,v in members.items():
            if k.startswith('word/footnotes') or k.startswith('word/charts/') or k.startswith('word/media/') and k!='word/media/uh-dfe-official-identity.png':
                if after.read(k)!=v:raise ValueError('Source footnote, diagram or image changed')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=sha:raise ValueError('Original source changed')
    return {'status':'UNPUBLISHED QA FIXTURE' if test_fixture else 'UNPUBLISHED AUTHORISED IDENTITY CANDIDATE',
            'kind':manifest['kind'],'source_sha256':sha,'candidate_sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),
            'source_paragraphs_preserved':len(original_paragraphs),'source_tables_preserved':original_tables,
            'page_numbers':'native PAGE field','contents':'native dynamic TOC field','identity_sha256':hashlib.sha256(logo).hexdigest(),
            'approval_record':None if test_fixture else ident['approval_record_url'],
            'QA_fixture_not_for_issue':test_fixture,'editor_approval':False,'publisher_save':False}

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('source',type=Path);a.add_argument('manifest',type=Path)
    a.add_argument('identity_png',type=Path);a.add_argument('identity_authority',type=Path)
    a.add_argument('output',type=Path);a.add_argument('--qa-fixture',action='store_true')
    x=a.parse_args();print(json.dumps(build(x.source,x.manifest,x.identity_png,x.identity_authority,x.output,x.qa_fixture),indent=2))
