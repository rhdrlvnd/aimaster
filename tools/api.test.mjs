import test from 'node:test';
import assert from 'node:assert/strict';
import {streamRequest} from '../src/services/api.js';
function mockStream(parts){return async()=>new Response(new ReadableStream({start(c){for(const part of parts)c.enqueue(new TextEncoder().encode(part));c.close();}}));}
test('stream reader preserves split events and final line without newline',async()=>{const original=global.fetch;try{global.fetch=mockStream(['{"stage":"heart','beat"}\n{"stage":"chunk","detail":"완료"}\n','{"stage":"done"}']);const events=[];await streamRequest({},e=>events.push(e),'/api/generate/stream');assert.deepEqual(events.map(e=>e.stage),['chunk','done']);}finally{global.fetch=original;}});
test('incomplete stream and server failure do not report success',async()=>{const original=global.fetch;try{global.fetch=mockStream(['{"stage":"chunk"}\n']);await assert.rejects(streamRequest({},()=>{}),/연결이 끊어/);global.fetch=mockStream(['{"stage":"error","detail":"저장 실패"}\n']);await assert.rejects(streamRequest({},()=>{}),/저장 실패/);}finally{global.fetch=original;}});
