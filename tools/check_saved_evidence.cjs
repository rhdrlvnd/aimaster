const {chromium}=require('C:/Users/dawoon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 await page.goto(process.env.APP_URL||'http://127.0.0.1:5173');
 await page.locator('.item').first().waitFor();
 const items=await page.locator('.item').count();
 assert.equal(await page.locator('.item .no-evidence').count(),0);
 const links=page.locator('.evidence-links button');assert.ok(await links.count()>=items);
 await links.first().click();await page.getByRole('dialog',{name:'원문 근거'}).waitFor();
 assert.ok((await page.locator('blockquote').innerText()).trim());
 assert.ok((await page.locator('.drawer pre').innerText()).trim());
 await page.screenshot({path:'outputs/evidence-restored.png',fullPage:true});
 console.log('Verified actual saved checklist:',items,'items, evidence links and original document drawer.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});

