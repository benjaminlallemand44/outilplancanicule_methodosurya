#!/usr/bin/env bash
# Génère docs/points_a_trancher.docx et .pdf (charte ACTEE) à partir de docs/points_a_trancher.md.
# Prérequis : pandoc, python-docx, LibreOffice (soffice). À lancer depuis la racine du dépôt.
set -e
S=$(mktemp -d)
pandoc -o $S/ref.docx --print-default-data-file reference.docx
python - <<PY
from docx import Document
from docx.shared import Pt, RGBColor, Mm
from docx.oxml.ns import qn
S="$S"
d=Document(S+"/ref.docx")
st={s.name:s for s in d.styles}
def police(s, nom, taille=None, gras=None):
    s.font.name=nom; rpr=s.element.get_or_add_rPr(); rf=rpr.find(qn('w:rFonts'))
    for a in ('w:asciiTheme','w:hAnsiTheme','w:cstheme','w:eastAsiaTheme'):
        if rf is not None and rf.get(qn(a)) is not None: del rf.attrib[qn(a)]
    rf=rpr.find(qn('w:rFonts'))
    for a in ('w:ascii','w:hAnsi','w:cs','w:eastAsia'): rf.set(qn(a),nom)
    if taille: s.font.size=Pt(taille)
    if gras is not None: s.font.bold=gras
    s.font.color.rgb=RGBColor(0,0,0)
for n in ("Normal","Body Text","First Paragraph","Compact","Block Text"):
    if n in st: police(st[n],"Schibsted Grotesk Medium",10)
for n,t in (("Title",24),("Heading 1",18),("Heading 2",14),("Heading 3",12),("Heading 4",11)):
    police(st[n],"Bitter Black" if t>=14 else "Schibsted Grotesk ExtraBold",t,True)
if "Hyperlink" in st: st["Hyperlink"].font.color.rgb=RGBColor(0x0a,0x17,0xa6)
for s in d.sections: s.left_margin=s.right_margin=Mm(20)
d.save(S+"/ref.docx")
PY
pandoc docs/points_a_trancher.md -o $S/pat.docx --reference-doc=$S/ref.docx
python - <<PY
from docx import Document
from docx.shared import Mm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
S="$S"
d=Document(S+"/pat.docx")
h=d.sections[0].header.paragraphs[0]; h.alignment=WD_ALIGN_PARAGRAPH.LEFT
h.add_run().add_picture("static/logos/actee-fnccr-couleur.png", width=Mm(45))
for p in d.paragraphs:
    if p.style.name in ("Heading 1","Title"):
        pPr=p._p.get_or_add_pPr(); b=OxmlElement('w:pBdr'); bt=OxmlElement('w:bottom')
        for k,v in (('val','single'),('sz','24'),('space','4'),('color','000000')): bt.set(qn('w:'+k),v)
        b.append(bt); pPr.append(b)
for t in d.tables:
    tblPr=t._tbl.tblPr; bd=OxmlElement('w:tblBorders')
    for e in ('top','left','bottom','right','insideH','insideV'):
        x=OxmlElement('w:'+e)
        for k,v in (('val','single'),('sz','4'),('color','9AA39A')): x.set(qn('w:'+k),v)
        bd.append(x)
    tblPr.append(bd)
    for c in t.rows[0].cells:
        tcPr=c._tc.get_or_add_tcPr(); sh=OxmlElement('w:shd')
        for k,v in (('val','clear'),('color','auto'),('fill','0A17A6')): sh.set(qn('w:'+k),v)
        tcPr.append(sh)
        for p in c.paragraphs:
            for r in p.runs: r.font.bold=True; r.font.color.rgb=RGBColor(255,255,255)
d.save("docs/points_a_trancher.docx")
PY
timeout 150 soffice --headless --convert-to pdf --outdir docs docs/points_a_trancher.docx >/dev/null 2>&1
pdfinfo docs/points_a_trancher.pdf | grep Pages
