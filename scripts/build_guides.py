#!/usr/bin/env python3
"""Build Controller Router's printable guides from maintained Markdown sources."""
from pathlib import Path
from datetime import date
import re
from html import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Preformatted, LongTable, TableStyle, KeepTogether, Image
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Polygon

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/pdf'
NAVY = colors.HexColor('#102738')
TEAL = colors.HexColor('#168e9a')
CORAL = colors.HexColor('#df684e')
WIDTH = A4[0] - 96
STYLES = getSampleStyleSheet()
STYLES.add(ParagraphStyle(name='BodyCopy',fontName='Helvetica',fontSize=9.5,leading=12.5,spaceAfter=6,textColor=NAVY))
STYLES.add(ParagraphStyle(name='Section',fontName='Helvetica-Bold',fontSize=16,leading=20,spaceBefore=15,spaceAfter=9,textColor=NAVY,keepWithNext=True))
STYLES.add(ParagraphStyle(name='Subsection',fontName='Helvetica-Bold',fontSize=12,leading=16,spaceBefore=10,spaceAfter=7,textColor=TEAL,keepWithNext=True))
STYLES.add(ParagraphStyle(name='Cell',fontName='Helvetica',fontSize=7.5,leading=10,textColor=NAVY))
STYLES.add(ParagraphStyle(name='CodeBlock',fontName='Courier',fontSize=7,leading=10,spaceBefore=5,spaceAfter=10,textColor=NAVY,backColor=colors.HexColor('#f0f5f7'),borderPadding=8))

def inline(s):
    s=escape(s)
    s=re.sub(r'`([^`]+)`',r'<font face="Courier">\1</font>',s)
    s=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',s)
    s=re.sub(r'\[([^]]+)\]\((https?://[^)]+)\)', r'<link href="\2" color="#168e9a">\1</link>', s)
    return s

def architecture():
    d=Drawing(WIDTH,265)
    def box(x,y,w,h,title,detail):
        d.add(Rect(x,y,w,h,rx=5,ry=5,fillColor=colors.HexColor('#eaf3f5'),strokeColor=TEAL))
        d.add(String(x+w/2,y+h-17,title,fontName='Helvetica-Bold',fontSize=9,textAnchor='middle',fillColor=NAVY))
        d.add(String(x+w/2,y+12,detail,fontName='Helvetica',fontSize=8,textAnchor='middle',fillColor=NAVY))
    def arrow(x,y,x2,y2):
        d.add(Line(x,y,x2,y2,strokeColor=TEAL,strokeWidth=1.2))
        if y==y2:d.add(Polygon([x2,y2,x2-5,y2+3,x2-5,y2-3],fillColor=TEAL,strokeColor=TEAL))
        else:d.add(Polygon([x2,y2,x2-3,y2+5,x2+3,y2+5],fillColor=TEAL,strokeColor=TEAL))
    box(0,213,155,45,'Console sessions','Authenticated product reports')
    box(185,213,WIDTH-185,45,'Product services','VirtualGlove and R.O.B. Vision')
    arrow(155,235,185,235)
    box(185,145,WIDTH-185,45,'UNO Q Controller Router','Port 80 chooser and host broker')
    arrow(335,213,335,190)
    box(0,75,155,45,'Shared Matrix','Sole App Lab sketch')
    box(185,75,WIDTH-185,45,'Selected product and receiver','One renewable input lease')
    arrow(185,167,77,120);arrow(335,145,335,120)
    box(0,5,155,45,'Physical gamepads','EmulationStation mappings')
    box(185,5,WIDTH-185,45,'Console Router outputs','Merged players to RetroArch / libretro')
    arrow(335,75,335,50);arrow(155,27,185,27)
    return d

def story(path):
    lines=path.read_text().splitlines();out=[];i=0
    while i<len(lines):
        s=lines[i].strip()
        if not s:i+=1;continue
        if s.startswith('# '):i+=1;continue
        if s=='<!-- pagebreak -->':out.append(PageBreak());i+=1;continue
        picture = re.fullmatch(r'!\[([^]]*)\]\(([^)]+)\)', s)
        if picture:
            image = Image(str(path.parent / picture.group(2)))
            scale = min(WIDTH / image.imageWidth, 310 / image.imageHeight)
            image.drawWidth, image.drawHeight = image.imageWidth * scale, image.imageHeight * scale
            out.extend([image, Spacer(1, 8)])
            i += 1
            continue
        if s.startswith('```'):
            lang=s[3:];buf=[];i+=1
            while i<len(lines) and not lines[i].startswith('```'):buf.append(lines[i]);i+=1
            if lang=='mermaid':out.append(architecture())
            else:
                wrapped=[]
                for line in buf:
                    if len(line)>115: raise ValueError('Code line exceeds printable width: ' + line)
                    wrapped.append(line)
                out.append(Preformatted('\n'.join(wrapped),STYLES['CodeBlock']))
            i+=1;continue
        if s.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                row=lines[i].strip()
                if not re.fullmatch(r'[| :\-]+',row):rows.append([Paragraph(inline(cell.strip()),STYLES['Cell']) for cell in row.strip('|').split('|')])
                i+=1
            n=len(rows[0]);widths=[WIDTH/n]*n
            t=LongTable(rows,colWidths=widths,repeatRows=1,hAlign='LEFT')
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dcecef')),('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#cbd9df'))]))
            out.extend([t,Spacer(1,10)]);continue
        if s.startswith('## '):out.append(Paragraph(inline(s[3:]),STYLES['Section']));i+=1;continue
        if s.startswith('### '):out.append(Paragraph(inline(s[4:]),STYLES['Subsection']));i+=1;continue
        bullet=None
        if s.startswith('- '):bullet='•';s=s[2:]
        elif re.match(r'^\d+\. ',s):bullet=s.split(' ',1)[0];s=s.split(' ',1)[1]
        out.append(Paragraph(inline(s),STYLES['BodyCopy'],bulletText=bullet));i+=1
    return out

def cover(canvas,doc,title,subtitle):
    canvas.saveState();canvas.setFillColor(NAVY);canvas.rect(0,0,*A4,fill=1,stroke=0)
    canvas.setFillColor(TEAL);canvas.rect(48,100,8,A4[1]-200,fill=1,stroke=0)
    canvas.setFillColor(colors.white);canvas.setFont('Helvetica-Bold',26);canvas.drawString(76,640,'CONTROLLER ROUTER')
    canvas.setFont('Helvetica-Bold',23);canvas.drawString(76,575,title)
    canvas.setFont('Helvetica',12)
    for j,line in enumerate(subtitle):canvas.drawString(76,536-j*20,line)
    canvas.setFillColor(CORAL);canvas.setFont('Helvetica-Bold',11);canvas.drawString(76,180,'VIRTUALGLOVE  /  R.O.B. VISION  /  MAKER CONTROLLERS')
    canvas.setFillColor(colors.HexColor('#a8c3cc'));canvas.setFont('Helvetica',10);canvas.drawString(76,149,'Current source edition | ' + date.today().strftime('%d %B %Y'))
    canvas.restoreState()

def body_page(canvas,doc,title):
    canvas.saveState();canvas.setStrokeColor(TEAL);canvas.line(48,800,A4[0]-48,800)
    canvas.setFillColor(NAVY);canvas.setFont('Helvetica-Bold',8);canvas.drawString(48,811,'CONTROLLER ROUTER')
    canvas.setFont('Helvetica',8);canvas.drawRightString(A4[0]-48,811,title)
    canvas.setFillColor(colors.HexColor('#627986'));canvas.drawString(48,28,'Current source edition | ' + date.today().strftime('%d %B %Y'));canvas.drawRightString(A4[0]-48,28,str(doc.page))
    canvas.restoreState()

GUIDES=[('PAIRING_GUIDE.md','Controller-Router-Pairing-Guide.pdf','Pairing Guide',['Connect your console once,','then play with either controller app.']),('USER_GUIDE.md','Controller-Router-User-Guide.pdf','User Guide',['Choose players and systems, test your pads,','and get back to your game.']),('INTEGRATION_GUIDE.md','Controller-Router-Integration-Guide.pdf','Integration Guide',['Build a unique controller for your game,','using shared routing and display APIs.']),('DEPLOYMENT_GUIDE.md','Controller-Router-Deployment-Guide.pdf','Deployment Guide',['Package the library and optional UNO Q runtime,','with safe upgrades and recovery.']),('TECHNICAL_REFERENCE.md','Controller-Router-Technical-Reference.pdf','Technical Reference',['Architecture, input leases, Matrix protocol,','console routing, and reusable integration.'])]

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for source,name,title,subtitle in GUIDES:
        p=OUT/name
        doc=SimpleDocTemplate(str(p),pagesize=A4,rightMargin=48,leftMargin=48,topMargin=57,bottomMargin=48,title=f'Controller Router {title}',author='Iain Bennett')
        doc.build([Spacer(1,1),PageBreak()]+story(ROOT/'docs'/source),onFirstPage=lambda c,d,t=title,s=subtitle:cover(c,d,t,s),onLaterPages=lambda c,d,t=title:body_page(c,d,t))
        import shutil
        bundled = ROOT / "uno_portal/python/guides"
        bundled.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, bundled / name)
        print(p)

if __name__=='__main__':main()
