const {chromium}=require('C:/Users/dawoon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{const b=await chromium.launch({channel:'msedge',headless:true});try{
const p=await b.newPage();let calls=0;const state={revision:2,documents:[{id:'d',name:'manual.docx',text:'본문'}],items:[],status:'ready',llm_configured:true};
await p.route('**/api/**',r=>{const u=new URL(r.request().url());if(u.pathname==='/api/workspace')return r.fulfill({json:state});if(u.pathname==='/api/documents'&&r.request().method()==='DELETE'){calls++;assert.equal(u.searchParams.get('revision'),'2');state.documents=[];state.status='empty';return r.fulfill({json:{ok:true}});}return r.abort();});
await p.goto('http://127.0.0.1:5185');await p.getByRole('button',{name:'문서 관리로 이동'}).click();
p.once('dialog',d=>d.dismiss());await p.getByRole('button',{name:'문서 전체 삭제',exact:true}).click();assert.equal(calls,0);
p.once('dialog',d=>{assert.ok(d.message().includes('기존 체크리스트는 남지만'));return d.accept();});await p.getByRole('button',{name:'문서 전체 삭제',exact:true}).click();await p.getByText('모든 업무 문서를 삭제했습니다. 새 문서를 등록해 주세요.',{exact:false}).waitFor();assert.equal(calls,1);assert.equal(await p.locator('.doc-row').count(),0);assert.ok(await p.getByRole('button',{name:'문서 전체 삭제',exact:true}).isDisabled());console.log('Bulk delete confirmation cancel/accept and empty state passed; actual documents unchanged.');
}finally{await b.close();}})().catch(e=>{console.error(e);process.exit(1)});
