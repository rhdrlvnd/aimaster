from pathlib import Path
p=Path('src/main.jsx');s=p.read_text(encoding='utf-8')
s=s.replace('DOCX·XLSX·PPTX의 텍스트와 표를 읽습니다. 이미지·차트는 제외됩니다. TXT·MD도 지원합니다(500KB).','PPT는 슬라이드 이미지와 텍스트를 함께 분석합니다(합계 20장). Word·Excel은 텍스트와 표를 읽습니다. TXT·MD도 지원합니다(500KB).')
s=s.replace("'문서 등록 중…'","'문서 처리·슬라이드 변환 중…'")
s=s.replace('원문 근거 {item.evidence.length>1?j+1:\'\'}',"{e.kind==='visual'?`슬라이드 ${e.slide} · 이미지 근거`:'원문 근거'} {item.evidence.length>1?j+1:''}")
s=s.replace('<span className="eyebrow">인용한 내용</span>', '<span className="eyebrow">{selected.kind===\'visual\'?\'AI가 이미지에서 해석한 근거 · 직접 확인 필요\':\'인용한 내용\'}</span>')
s=s.replace('<span className="eyebrow">추출한 문서 내용</span>', '''{docs.find(d=>d.id===selected.document_id)?.slide_count>0&&<section className="slide-preview"><label>슬라이드 <select aria-label="슬라이드 선택" value={selected.slide||1} onChange={e=>setSelected({...selected,slide:Number(e.target.value)})}>{Array.from({length:docs.find(d=>d.id===selected.document_id).slide_count},(_,i)=><option key={i+1} value={i+1}>{i+1}</option>)}</select></label><a href={`/api/documents/${selected.document_id}/slides/${selected.slide||1}`} target="_blank" rel="noreferrer">크게 보기</a><img key={`${selected.document_id}-${selected.slide||1}`} src={`/api/documents/${selected.document_id}/slides/${selected.slide||1}`} alt={`슬라이드 ${selected.slide||1}`} /></section>}<span className="eyebrow">추출한 문서 내용</span>''')
p.write_text(s,encoding='utf-8')
p=Path('src/styles.css');s=p.read_text();s+='\n.slide-preview{margin:18px 0 28px}.slide-preview img{width:100%;height:auto;border:1px solid #dce5e1;margin-top:12px}.slide-preview a{float:right;color:#137d69;font-size:12px}.slide-preview label{font-size:13px}.drawer:has(.slide-preview){width:min(960px,95vw)}\n';p.write_text(s)
