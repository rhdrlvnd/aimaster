"""Signed handover export from confirmed data only; no LLM rewriting."""
from io import BytesIO
from datetime import datetime
from docx import Document
from docx.shared import Pt, Inches
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def build_docx(state,signature):
    doc=Document()
    section=doc.sections[0]
    section.top_margin=section.bottom_margin=Inches(.75)
    normal=doc.styles['Normal'];normal.font.name='맑은 고딕';normal.font.size=Pt(10)
    normal.element.rPr.rFonts.set(qn('w:eastAsia'),'맑은 고딕')
    for name in ('Title','Heading 1','Heading 2'):
        style=doc.styles[name];style.font.name='맑은 고딕';style.element.rPr.rFonts.set(qn('w:eastAsia'),'맑은 고딕')
        from docx.shared import RGBColor
        style.font.color.rgb=RGBColor(0,0,0)
    h=state['handover']
    doc.add_heading(h['name']+' 인수인계서',0)
    doc.add_paragraph('확정된 업무 내용과 일정, 인계자의 서명을 기록한 문서입니다.')
    for text in [f"담당 업무: {h.get('scope','')}",f"인계자: {h['owner']} / 인수자: {h['successor']}",f"기간: {h.get('start_date','')} ~ {h.get('end_date','')}"]:
        doc.add_paragraph(text)
    schedule={r['item_id']:r for r in state.get('schedule',{}).get('confirmed',[])}
    docs={d['id']:d for d in state['documents']}
    doc.add_heading('업무 및 일정',1)
    for n,item in enumerate(state['items'],1):
        doc.add_heading(f"{n}. {item['title']}",2)
        doc.add_paragraph(f"분류: {item['category']} / 중요도: {item['priority']}")
        doc.add_paragraph(item['description'])
        row=schedule.get(item['id'])
        if row: doc.add_paragraph(f"일정: {row['start']} {row.get('start_time') or ''} ~ {row['end']} {row.get('end_time') or ''}")
        status=state.get('progress',{}).get(item['id'],{}).get('status','todo')
        doc.add_paragraph('인수 상태 (출력 시점): '+{'todo':'미시작','doing':'진행 중','done':'완료'}.get(status,'미시작'))
        for e in item.get('evidence',[]):
            source=docs.get(e['document_id'],{}).get('name','문서')
            label=f" / 슬라이드 {e['slide']}" if e.get('kind')=='visual' else ''
            doc.add_paragraph(f"근거: {source}{label}\n{e['quote']}")
    doc.add_heading('인계 확인 및 서명',1)
    doc.add_paragraph('위 내용과 일정으로 인계 내용을 확인합니다.')
    doc.add_paragraph('서명자: '+signature['name'])
    doc.add_paragraph('서명 방식: 성명 입력 및 확인 동의')
    doc.add_paragraph('서명 시각: '+signature['signed_at'])
    doc.add_paragraph('서명 대상 자료 식별값: '+signature['fingerprint'][:16])
    # Prevent headings being stranded and repeat page numbers.
    footer=section.footer.paragraphs[0];footer.alignment=2
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
    output=BytesIO();doc.save(output);return output.getvalue()
