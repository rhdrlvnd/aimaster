const {chromium}=require('C:/Users/dawoon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const states={},calls=[];let serial=0;
  const summary=s=>({...s.handover,revision:s.revision,status:s.status,document_count:s.documents.length,item_count:s.items.length});
  await page.route('**/api/**',async r=>{
   const req=r.request(),path=new URL(req.url()).pathname,method=req.method();calls.push(method+' '+path);
   let result;
   if(path==='/api/handovers'){
    if(method==='GET')result={handovers:Object.values(states).map(summary)};
    else{const id='h'+(++serial);states[id]={handover:{...req.postDataJSON(),id},revision:0,status:'empty',documents:[],items:[],llm_configured:true};result=summary(states[id]);}
   }else{
    const [,id,action]=path.match(/^\/api\/handovers\/([^/]+)(?:\/(.*))?$/)||[];
    assert.ok(id,'Unscoped request: '+path);const s=states[id];
    if(!action){s.handover={...s.handover,...req.postDataJSON()};s.revision++;result=summary(s);}
    else if(action==='workspace')result=s;
    else if(action==='checklist'){s.items=req.postDataJSON().items;s.status='review';s.revision++;result={ok:true};}
    else if(action==='approve'){s.status='approved';s.revision++;result={ok:true};}
    else if(action==='reopen'){s.status='review';s.revision++;s.items.forEach(i=>i.reviewed=false);result={ok:true};}
    else throw Error('Unexpected '+path);
   }
   await r.fulfill({json:result});
  });
  await page.goto('http://127.0.0.1:5185');
  await page.getByRole('heading',{name:'첫 인수인계를 시작해 보세요'}).waitFor();
  async function create(name){
   await page.getByRole('button',{name:'인수인계 시작',exact:true}).first().click();
   const form=page.getByRole('dialog');
   await form.getByLabel('인수인계 제목').fill(name);await form.getByLabel('담당 업무').fill('급여 자료와 근태 마감');
   await form.getByLabel('전임자',{exact:true}).fill('정수민');await form.getByLabel('후임자',{exact:true}).fill('김하늘');
   await form.getByLabel('시작일').fill('2026-10-19');await form.getByLabel('종료일').fill('2026-10-30');
   await form.getByRole('button',{name:'생성하고 문서 등록'}).click();
   await page.getByRole('heading',{level:1,name:'업무 문서',exact:true}).waitFor();
  }
  await create('인사운영 인수인계');
  await page.getByRole('button',{name:'체크리스트',exact:true}).click();
  await page.getByRole('button',{name:'항목 추가',exact:true}).click();
  await page.getByLabel('업무명').fill('근태 마감 확인');await page.getByLabel('업무 설명').fill('승인된 근태 자료 확인');
  const dismiss=d=>d.dismiss();page.once('dialog',dismiss);
  await page.getByRole('button',{name:'인수인계 목록으로'}).click();
  assert.equal(await page.getByLabel('업무명').inputValue(),'근태 마감 확인');
  await page.getByLabel('검토 완료',{exact:true}).check();
  await page.getByRole('button',{name:'변경 저장',exact:true}).click();
  await page.getByRole('button',{name:'검토 확정',exact:true}).click();
  await page.getByRole('button',{name:'검토 다시 열기',exact:true}).click();
  await page.getByRole('button',{name:'인수인계 목록으로'}).click();
  await create('재무업무 인수인계');
  await page.getByRole('button',{name:'체크리스트',exact:true}).click();
  assert.equal(await page.getByText('근태 마감 확인',{exact:true}).count(),0);
  await page.getByRole('button',{name:'인수인계 목록으로'}).click();
  await page.getByRole('button',{name:'인사운영 인수인계 기본 정보 수정'}).click();
  await page.getByLabel('인수인계 제목').fill('인사운영 10월 인수인계');
  await page.getByRole('button',{name:'기본 정보 저장'}).click();
  await page.getByRole('button',{name:'인사운영 10월 인수인계 열기'}).waitFor();
  await page.screenshot({path:'.artifact-build/handover-list.png',fullPage:true});
  await page.reload();await page.getByRole('button',{name:'인사운영 10월 인수인계 열기'}).click();
  for(const title of ['인수인계 현황','업무 문서','체크리스트','인수인계 일정','업무 질문']){
   await page.locator('nav button').filter({hasText:title}).click();
   await page.getByRole('heading',{level:1,name:title,exact:true}).waitFor();
   assert.equal(await page.locator('header strong').textContent(),title);
  }
  await page.getByRole('button',{name:/^체크리스트/}).first().click();
  await page.getByRole('heading',{name:'근태 마감 확인',exact:true}).waitFor();
  assert.equal(states.h1.items.length,1);assert.equal(states.h2.items.length,0);
  assert.deepEqual(errors,[]);
  console.log('PASS create, edit metadata, separate workspaces, dirty guard, save/approve/reopen, reload, 5 menu titles');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
