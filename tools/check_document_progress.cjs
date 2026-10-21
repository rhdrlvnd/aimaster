const {chromium}=require('C:/Users/dawoon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1100}});
 await page.route('**/api/workspace',r=>r.fulfill({json:{revision:1,documents:[],items:[],status:'empty',llm_configured:true}}));
 await page.addInitScript(()=>{
 const original=window.fetch;
 window.fetch=(url,options)=>url!=='/api/documents/stream'?original(url,options):Promise.resolve(new Response(new ReadableStream({start(c){
 const send=(stage,detail)=>c.enqueue(new TextEncoder().encode(JSON.stringify({stage,detail})+'\n'));
 send('receive','파일 수신 완료');send('extract','문서 내용 추출');
 setTimeout(()=>send('render','1,234자 추출 완료 · 슬라이드를 이미지로 변환합니다.'),100);
 setTimeout(()=>{send('save','슬라이드 5장 변환 완료');send('done','1,234자 · 슬라이드 5장 · 저장 완료, 분석 준비가 끝났습니다.');c.close();},3500);
 }})));
 });
 await page.goto('http://127.0.0.1:5173');
 await page.getByRole('button',{name:'문서 관리로 이동'}).click();
 await page.locator('input[type=file]').setInputFiles({name:'배치설계와_운영개선_검토.pptx',mimeType:'application/octet-stream',buffer:Buffer.from('mock')});
 const panel=page.getByRole('region',{name:'AI 분석 진행 상황'});
 await panel.getByText('1,234자 추출 완료 · 슬라이드를 이미지로 변환합니다.',{exact:true}).waitFor();
 assert.equal(await panel.locator('li.complete').count(),2);
 assert.equal(await panel.locator('li.active .spin').count(),1);
 await page.screenshot({path:'outputs/document-progress.png',fullPage:true});
 await panel.getByText('1,234자 · 슬라이드 5장 · 저장 완료, 분석 준비가 끝났습니다.',{exact:true}).waitFor();
 assert.equal(await panel.locator('li.complete').count(),8);
 console.log('Document progress: conversion spinner, completed extraction, final counts passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
