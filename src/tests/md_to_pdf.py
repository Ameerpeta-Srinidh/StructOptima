import os
import re
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

md_path = r"c:\Srinidh\civil\Extended_Structural_Calculation_Reference_Readable.md"
pdf_path = r"C:\Users\srini\.gemini\antigravity\brain\77a0a619-44c7-4aff-91bd-3ae20b7e3c46\Extended_Structural_Calculation_Reference.pdf"
pdf_workspace_path = r"c:\Srinidh\civil\Extended_Structural_Calculation_Reference.pdf"

with open(md_path, 'r', encoding='utf-8') as f:
    text = f.read()

doc = SimpleDocTemplate(pdf_path, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
styles = getSampleStyleSheet()

styles.add(ParagraphStyle(name='TitleStyle', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=16, spaceAfter=20, textColor=colors.HexColor("#2C3E50")))
styles.add(ParagraphStyle(name='H2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=13, spaceBefore=15, spaceAfter=10, textColor=colors.HexColor("#2980B9")))
styles.add(ParagraphStyle(name='NormalStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=10, spaceAfter=6, leading=14))
styles.add(ParagraphStyle(name='CodeStyle', parent=styles['Normal'], fontName='Courier', fontSize=9, spaceAfter=6, leading=12, leftIndent=15, textColor=colors.HexColor("#c0392b")))

elements = []

def process_inline(txt):
    txt = txt.replace('<', '&lt;').replace('>', '&gt;')
    txt = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', txt)
    return txt

blocks = text.split('\n\n')

in_list = False
list_items = []

def flush_list():
    global in_list, list_items
    if in_list and list_items:
        elements.append(ListFlowable(list_items, bulletType='bullet', leftIndent=15, spaceAfter=10))
        in_list = False
        list_items = []

for block in blocks:
    block = block.strip()
    if not block: continue
    
    if block.startswith('---'):
        flush_list()
        elements.append(Spacer(1, 10))
        continue
        
    if block.startswith('# '):
        flush_list()
        elements.append(Paragraph(process_inline(block[2:]), styles['TitleStyle']))
    elif block.startswith('## '):
        flush_list()
        elements.append(Paragraph(process_inline(block[3:]), styles['H2']))
    elif block.startswith('- '):
        lines = block.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('- '):
                list_items.append(ListItem(Paragraph(process_inline(line[2:]), styles['NormalStyle'])))
        in_list = True
    elif '  ' in block and not block.startswith('**'): # Using indent to signify code/math
        flush_list()
        # Preformatted math text
        lines = block.split('\n')
        for line in lines:
            elements.append(Paragraph(process_inline(line), styles['CodeStyle']))
    else:
        flush_list()
        # Normal text with bold
        lines = block.split('\n')
        for line in lines:
            if line.startswith('  '):
                elements.append(Paragraph(process_inline(line), styles['CodeStyle']))
            else:
                elements.append(Paragraph(process_inline(line), styles['NormalStyle']))

flush_list()
doc.build(elements)

import shutil
shutil.copy(pdf_path, pdf_workspace_path)
print(f"PDF generated successfully at {pdf_workspace_path}")
