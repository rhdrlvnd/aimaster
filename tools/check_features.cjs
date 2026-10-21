const {chromium}=require('C:/Users/dawoon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const users=[{id:'demo-dev',name:'김개발',department:'개발'},{id:'demo-next',name:'이후임',department:'개발'}];let user=users[0];
  const h={id:'test',name:'근태 운영 인수인계',scope:'근태 마감 및 승인',owner:'김개발',successor:'이후임',start_date:'2026-10-21',end_date:'2026-10-30'};
  const state={handover:h,status:'approved',revision:1,documents:[],items:[{id:'a',title:'근태 자료 확인',description:'누락된 근태를 확인합니다.',priority:'높음',category:'근태',reviewed:true,evidence:[],origin:'manual'}],llm_configured:true};
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
    if(path.endsWith('/schedule/generate/stream')){f.schedule.draft={rows,settings:body.settings};stream=true;}
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
  await nav('인수인계 일정');await page.getByRole('button',{name:'AI 일정 초안 작성',exact:true}).click();
  await page.getByRole('button',{name:'일정 확정',exact:true}).click();
  await page.getByText('2026-10-21 ~ 2026-10-21',{exact:true}).waitFor();
  await page.screenshot({path:'.artifact-build/schedule-owner.png',fullPage:true});
  await nav('인수인계 현황');await page.getByLabel('서명 성명').fill('김개발');await page.getByRole('checkbox').check();
  await page.getByRole('button',{name:'서명 저장',exact:true}).click();await page.getByText('서명자 김개발 · 2026-10-20',{exact:true}).waitFor();
  await page.getByRole('button',{name:'인수인계 목록으로'}).click();await page.getByLabel('테스트 사용자',{exact:true}).selectOption('demo-next');await open();
  await nav('인수인계 일정');await page.getByLabel('근태 자료 확인 인수 상태').selectOption('done');
  await page.getByText('처리 결과를 저장했습니다.',{exact:true}).waitFor();assert.equal(f.progress.a.status,'done');
  assert.equal(await page.getByRole('button',{name:'AI 일정 초안 작성',exact:true}).count(),0);
  await nav('업무 질문');await page.getByLabel('업무 질문',{exact:true}).fill('승인 기준을 알려줘');await page.getByRole('button',{name:'AI에게 질문',exact:true}).click();
  await page.getByText('인계자에게 승인 기준을 확인하세요.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'인계자 질문으로 옮기기'}).click();await page.getByRole('button',{name:'질문 등록',exact:true}).click();
  await page.getByText('답변 대기 · 이후임',{exact:true}).waitFor();
  await page.screenshot({path:'.artifact-build/questions-successor.png',fullPage:true});
  await nav('인수인계 현황');await page.getByText('100%',{exact:true}).waitFor();
  await page.screenshot({path:'.artifact-build/dashboard-successor.png',fullPage:true});
  assert.deepEqual(errors,[]);console.log('PASS: owner schedule/confirm/sign, successor progress, AI answer and question board, dashboard, role controls; mocked API only');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
