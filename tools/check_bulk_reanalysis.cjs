const {chromium}=require('C:/Users/dawoon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const users=[{id:'demo-dev',name:'김개발',department:'개발'},{id:'demo-next',name:'이후임',department:'개발'}];let user=users[0];
  const h={id:'test',name:'근태 운영 인수인계',scope:'근태 마감 및 승인',owner:'김개발',successor:'이후임',start_date:'2026-10-21',end_date:'2026-10-30'};
  const state={handover:h,status:'review',revision:1,documents:['a','b','c'].map(id=>({id,name:id+'.docx',text:'본문',rag:{status:'outdated'}})),items:[{id:'a',title:'근태 자료 확인',description:'누락된 근태를 확인합니다.',priority:'높음',category:'근태',reviewed:true,evidence:[],origin:'manual'}],llm_configured:true};
  const f={revision:1,schedule:{},schedule_current:false,progress:{},questions:[],conversations:[],signature:null,calendar:{configured:false,connected:false},calendar_results:[]};
  const rows=[{item_id:'a',start:'2026-10-21',end:'2026-10-21',reason:'근태 자료를 먼저 확인합니다.'}];
  await page.route('**/api/**',async route=>{
   const req=route.request(),path=new URL(req.url()).pathname,method=req.method();let result,stream=false;
   if(path==='/api/demo/users')result={users};
   else if(path==='/api/session')result={user};
   else if(path==='/api/demo/session'){user=users.find(u=>u.id===req.postDataJSON().user_id);result={user};}
   else if(path==='/api/handovers')result={handovers:[{...h,status:state.status,can_access:true,can_manage:user===users[0],document_count:0,item_count:1}]};
   else if(path.endsWith('/workspace'))result={...state,permissions:{can_manage:user===users[0],can_view_content:true}};
   else if(path.endsWith('/features'))result=f;
   else {
    const body=req.postDataJSON();assert.equal(body.revision,f.revision);
    state.revision++;f.revision++;
    if(path.endsWith('/analyze/stream')){ const id=path.split('/').at(-3); if(id==='b'){await route.fulfill({contentType:'application/x-ndjson',body:JSON.stringify({stage:'error',detail:'테스트 오류'})+'\n'});return;} stream=true; } else if(path.endsWith('/schedule/generate/stream')){f.schedule.draft={rows,settings:body.settings};stream=true;}
    else if(path.endsWith('/schedule/confirm')){f.schedule={confirmed:body.rows,settings:f.schedule.draft.settings};f.schedule_current=true;}
    else if(path.endsWith('/signature'))f.signature={name:body.name,signed_at:'2026-10-20'};
    else if(path.endsWith('/progress'))f.progress.a={status:body.status};
    else if(path.endsWith('/qa/stream')){f.conversations=[{id:'c1',title:body.question,messages:[{id:'m1',question:body.question,answer:'인계자에게 승인 기준을 확인하세요.',evidence:[],insufficient:true}]}];stream=true;}
    else if(path.endsWith('/questions'))f.questions.push({id:'q1',question:body.content,author:user.name,answer:null});
    else if(path.endsWith('/questions/q1/answer')){f.questions[0].answer=body.content;f.questions[0].answered_by=user.name;}
    else throw Error('Unexpected '+method+' '+path);
    result={ok:true};
   }
   if(stream)await route.fulfill({contentType:'application/x-ndjson',body:JSON.stringify({stage:'done',detail:'처리 완료'})+'\n'});
   else await route.fulfill({json:result});
  });
  const nav=async name=>page.locator('nav button').filter({hasText:name}).click();
  const open=async()=>page.getByRole('button',{name:h.name+' 열기',exact:true}).click();
  await page.goto('http://127.0.0.1:5185');await open();
  await page.getByRole('button',{name:'전체 문서 다시 분석',exact:true}).click();
  await page.getByText('3개 중 2개 문서의 분석을 완료했습니다. 실패 1개는 개별 재분석할 수 있습니다.',{exact:true}).waitFor();
  assert.equal(state.revision,4);
  const options=await page.locator('#progress-document option').allTextContents();
  assert.ok(options.some(v=>v.includes('a.docx')&&v.includes('완료')));
  assert.ok(options.some(v=>v.includes('b.docx')&&v.includes('실패')));
  assert.ok(options.some(v=>v.includes('c.docx')&&v.includes('완료')));
  assert.deepEqual(errors,[]);
  await page.screenshot({path:'.artifact-build/bulk-reanalysis.png',fullPage:true});
  console.log('PASS sequential reanalysis, fresh revisions, continue after failure, per-document outcomes');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
