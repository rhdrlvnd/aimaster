const {chromium}=require('C:/Users/dawoon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 await page.goto('http://127.0.0.1:5185/');
 await page.getByLabel('테스트 사용자',{exact:true}).selectOption('demo-dev');
 await page.getByRole('button',{name:'주문 서비스 운영 인수인계 열기',exact:true}).waitFor();
 if(!await page.getByRole('button',{name:'입퇴사·근태 업무 인수인계 열기',exact:true}).isDisabled())throw Error('HR not locked');
 await page.getByLabel('테스트 사용자',{exact:true}).selectOption('demo-hr');
 await page.waitForFunction(()=>[...document.querySelectorAll('button')].some(b=>b.getAttribute('aria-label')==='입퇴사·근태 업무 인수인계 열기'&&!b.disabled));
 if(!await page.getByRole('button',{name:'주문 서비스 운영 인수인계 열기',exact:true}).isDisabled())throw Error('Dev not locked');
 await page.screenshot({path:'.artifact-build/handover-access.png',fullPage:true});
 await page.getByRole('button',{name:'입퇴사·근태 업무 인수인계 열기',exact:true}).click();
 await page.getByText('업무 문서',{exact:true}).first().waitFor();
 console.log('PASS: demo user switching, locked cards, authorized workspace');
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
