const {chromium}=require('C:/Users/dawoon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{const b=await chromium.launch({channel:'msedge',headless:true});try{
const p=await b.newPage({viewport:{width:1440,height:900}});p.on('pageerror',e=>console.log('PAGE ERROR',e.message));
await p.addInitScript(()=>{const original=window.fetch;const state={revision:1,documents:[],items:[],status:'ready',llm_configured:true};let number=0;
window.fetch=(url,options)=>{
if(url==='/api/workspace')return Promise.resolve(Response.json(state));
if(url!=='/api/documents/stream')return original(url,options);
const n=++number,name=options.body.get('file').name;
return Promise.resolve(new Response(new ReadableStream({start(c){const send=(stage,detail)=>c.enqueue(new TextEncoder().encode(JSON.stringify({stage,detail})+'\n'));send('embed','벡터 생성 중');setTimeout(()=>{
state.documents.push({id:String(n),name,text:'원문 내용',rag:n===2?{status:'failed',error:'임베딩 실패'}:{status:'ready',summary:'문서 '+n+'의 요약',chunk_count:3}});
send(n===2?'error':'done',n===2?'임베딩 실패':'저장 완료');c.close();},n===1?500:1800);}})));
};});
await p.goto('http://127.0.0.1:5185');await p.getByRole('button',{name:'문서 관리로 이동'}).click();
await p.locator('input[type=file]').setInputFiles(['첫번째.docx','두번째.xlsx','세번째.pptx'].map(name=>({name,mimeType:'application/octet-stream',buffer:Buffer.from('mock')})));
await p.getByText('2 / 3 · 두번째.xlsx',{exact:true}).waitFor();assert.equal(await p.locator('.file-progress').count(),1);assert.equal(await p.locator('.queue-row.complete').count(),1);assert.equal(await p.locator('.queue-row.active').count(),1);assert.equal(await p.locator('.queue-row.waiting').count(),1);
await p.screenshot({path:'outputs/single-document-progress.png',fullPage:true});
await p.getByText('3 / 3 · 세번째.pptx',{exact:true}).waitFor();assert.equal(await p.locator('.queue-row.failed').count(),1);assert.equal(await p.locator('.file-progress').count(),1);
await p.getByText('3개 중 2개 문서의 등록과 AI 분석을 완료했습니다.',{exact:false}).waitFor();
assert.equal(await p.locator('.file-progress').count(),0);assert.equal(await p.locator('.doc-row.doc-complete').count(),2);assert.equal(await p.locator('.doc-row.doc-failed').count(),1);assert.equal(await p.locator('.document-analysis').count(),1);
await p.locator('.doc-open').filter({hasText:'세번째.pptx'}).click();await p.getByText('문서 3의 요약',{exact:true}).waitFor();
await p.getByRole('button',{name:'원문 보기'}).click();await p.getByRole('dialog').waitFor();assert.equal(await p.locator('.drawer pre').textContent(),'원문 내용');
console.log('Sequential single-panel progress, success/failure markers, continuation, selected summary and source passed.');
}finally{await b.close();}})().catch(e=>{console.error(e);process.exit(1)});
