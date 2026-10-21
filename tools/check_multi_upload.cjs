const {chromium}=require('C:/Users/dawoon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const state={revision:0,project:{},documents:[],items:[],status:'empty',llm_configured:true};
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let attempts=0;
 await page.route('**/api/**',async route=>{
  const url=new URL(route.request().url());
  if(url.pathname==='/api/workspace')return route.fulfill({json:state});
  if(url.pathname==='/api/documents/stream'){
   attempts++;
   if(attempts===2)return route.fulfill({status:422,json:{detail:'손상된 문서입니다.'}});
   state.documents.push({id:`doc-${attempts}`,name:attempts===1?'manual.docx':'design.pptx',text:'업무 자료'});state.status='ready';
   return route.fulfill({contentType:'application/x-ndjson',body:[{stage:'receive',detail:'수신 완료'},{stage:'extract',detail:'내용 추출'},{stage:'save',detail:'저장 중'},{stage:'done',detail:'분석 준비 완료'}].map(e=>JSON.stringify(e)+'\n').join('')});
  }
  return route.abort();
 });
 await page.goto('http://127.0.0.1:5173');
 await page.getByRole('button',{name:'문서 관리로 이동'}).click();
 const input=page.locator('input[type=file]');
 assert.equal(await input.getAttribute('multiple'),'');
 await input.setInputFiles(['manual.docx','broken.xlsx','design.pptx'].map(name=>({name,mimeType:'application/octet-stream',buffer:Buffer.from('mock document')})));
 await page.getByRole('status').filter({hasText:'3개 중 2개 문서를 등록했습니다.'}).waitFor();
 await page.getByRole('alert').filter({hasText:'broken.xlsx: 손상된 문서입니다.'}).waitFor();
 assert.equal(attempts,3);assert.equal(state.documents.length,2);
 const panel=page.getByRole('region',{name:'AI 분석 진행 상황'});
 assert.equal(await panel.locator('.file-progress').count(),3);
 assert.equal(await panel.locator('li.failed').count(),1);
 assert.equal(await panel.locator('li.complete').count(),15);
 await input.setInputFiles(Array.from({length:9},(_,i)=>({name:`${i}.txt`,mimeType:'text/plain',buffer:Buffer.from('text')})));
 await page.getByRole('alert').filter({hasText:'현재 추가 가능한 파일은 8개입니다.'}).waitFor();
 assert.equal(attempts,3);assert.deepEqual(errors,[]);
 console.log('Browser: multiple selection, partial failure, success retention, remaining-capacity guard passed (mock API; user data untouched).');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});

