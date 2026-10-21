const {chromium}=require('C:/Users/dawoon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 await page.goto('http://127.0.0.1:5185');await page.locator('.item').first().waitFor();
 const state=await (await page.request.get('http://127.0.0.1:8000/api/workspace')).json();
 let count=0;
 for(let i=0;i<state.items.length;i++){
 const item=state.items[i];const article=page.locator('.item').nth(i);
 assert.equal(await article.locator('.item-title').inputValue(),item.title);
 for(let j=0;j<item.evidence.length;j++){
 const e=item.evidence[j],doc=state.documents.find(d=>d.id===e.document_id);
 await article.locator('.evidence-links button').nth(j).click();
 const drawer=page.getByRole('dialog',{name:'원문 근거'});await drawer.waitFor();
 assert.equal((await drawer.locator('.source-name').innerText()).trim(),doc.name);
 assert.equal((await drawer.locator('blockquote').innerText()).trim(),e.quote.trim());
 assert.equal((await drawer.locator('pre').textContent()),doc.text);
 if(e.kind==='visual'){
  assert.equal(await drawer.locator('select').inputValue(),String(e.slide));
  await drawer.locator('img').evaluate(img=>img.complete&&img.naturalWidth>0?true:new Promise((resolve,reject)=>{img.onload=()=>resolve(true);img.onerror=()=>reject(new Error('Image failed'));}));
 }
 await drawer.getByRole('button',{name:'원문 닫기'}).click();count++;
 }
 }
 console.log('Verified',state.items.length,'items and all',count,'evidence links: correct document, quote, full text, and PPT image.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
