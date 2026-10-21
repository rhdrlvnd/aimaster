const {chromium}=require('C:/Users/dawoon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/workspace',route=>route.fulfill({json:{revision:1,documents:[{id:'a',name:'운영 매뉴얼.docx',rag:{status:'ready'},text:'매일 주문 확인'}],items:[],status:'ready',llm_configured:true}}));
 await page.addInitScript(()=>{
  const original=window.fetch;window.fetch=(url,options)=>{
   if(url!=='/api/generate/stream')return original(url,options);
   return Promise.resolve(new Response(new ReadableStream({start(controller){
    const send=(stage,detail)=>controller.enqueue(new TextEncoder().encode(JSON.stringify({stage,detail})+'\n'));
    send('prepare','등록 문서를 준비합니다.');
    setTimeout(()=>send('analyze','AI 응답 대기 중 · 1차 시도'),100);
    setTimeout(()=>{send('validate','원문 근거 확인');send('save','저장 중');send('done','초안 저장 완료');controller.close();},3500);
   }})));
  };
 });
 await page.goto('http://127.0.0.1:5173');
 await page.getByRole('button',{name:'AI 초안 생성',exact:true}).click();
 await page.getByText('AI 응답 대기 중 · 1차 시도',{exact:true}).waitFor();
 const panel=page.getByRole('region',{name:'체크리스트 생성 진행 상태'});
 assert.equal(await panel.getAttribute('aria-busy'),'true');
 await page.getByText('0분 2초 경과',{exact:true}).waitFor();
 assert.equal(await panel.locator('li.active .spin').count(),1);
 await page.screenshot({path:'outputs/loading-progress.png',fullPage:true});
 await page.getByText('초안 생성 완료',{exact:true}).waitFor();
 assert.equal(await panel.locator('li.complete').count(),5);
 assert.deepEqual(errors,[]);
 await browser.close();console.log('Progress stages, spinner, elapsed time, completion verified; no user data changed.');
})().catch(e=>{console.error(e);process.exit(1)});
