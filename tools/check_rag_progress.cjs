const {chromium}=require('C:/Users/dawoon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({channel:'msedge',headless:true});try{
const page=await browser.newPage({viewport:{width:1440,height:1000}});
await page.route('**/api/workspace',r=>r.fulfill({json:{revision:1,documents:[{id:'doc',name:'운영.docx',text:'일일 점검'}],items:[],status:'ready',llm_configured:true}}));
await page.addInitScript(()=>{const fetchOriginal=window.fetch;window.fetch=(url,options)=>url!=='/api/documents/doc/analyze/stream'?fetchOriginal(url,options):Promise.resolve(new Response(new ReadableStream({start(c){
const send=(stage,detail)=>c.enqueue(new TextEncoder().encode(JSON.stringify({stage,detail})+'\n'));
send('summarize','AI 문서 요약 중');setTimeout(()=>send('chunk','요약 완료 · 청킹 중'),300);setTimeout(()=>send('embed','3개 청크 · 벡터 생성 중'),600);setTimeout(()=>send('store','3개 벡터 · ChromaDB 저장 중'),1800);setTimeout(()=>{send('done','3개 청크 · ChromaDB 저장 완료');c.close();},2400);
}})));});
await page.goto('http://127.0.0.1:5185');await page.getByRole('button',{name:'문서 관리로 이동'}).click();await page.getByRole('button',{name:'AI 문서 분석',exact:true}).click();
const panel=page.getByRole('region',{name:'AI 분석 진행 상황'});await panel.getByText('3개 청크 · 벡터 생성 중',{exact:true}).waitFor();assert.equal(await panel.locator('li.active').innerText(),'벡터 임베딩\n진행 중');
const left=await page.locator('.document-panel').boundingBox(),right=await page.locator('.document-results').boundingBox();assert.ok(right.x>=left.x+left.width);assert.ok(right.width>left.width);
await page.screenshot({path:'outputs/rag-progress.png',fullPage:true});
await panel.getByText('3개 청크 · ChromaDB 저장 완료',{exact:true}).waitFor();assert.equal(await panel.locator('li.complete').count(),7);
await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
console.log('RAG analysis stages, spinner, completion, existing-document action, mobile layout passed; no workspace changes.');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exit(1)});
