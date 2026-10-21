import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from backend import app, rag


class ChecklistQualityTests(unittest.IsolatedAsyncioTestCase):
    async def test_overlong_generated_description_is_rewritten_before_review(self):
        self.setup_inputs()
        long_item=dict(self.item,description='가'*501)
        result,client=await self.run_generate([{'items':[long_item]},{'items':[self.item]},{'issues':[]}])
        self.assertEqual(client.post.await_count,3)
        self.assertLessEqual(len(result[0].description),500)
        self.assertIn('500자',client.post.call_args_list[1].kwargs['json']['messages'][-1]['content'])
        review_prompt=client.post.call_args_list[-1].kwargs['json']['messages'][0]['content']
        self.assertIn('모든 예시',review_prompt)

    async def test_truncated_group_splits_without_losing_document_context(self):
        from backend.checklist_generation import generate_bounded_section
        self.setup_inputs()
        other=dict(self.item,title='근태 예외 확인')
        truncated=self.response({});truncated.json.return_value={'choices':[{'finish_reason':'length','message':{'content':'BROKEN_JSON'}}]}
        responses=[truncated,self.response({'items':[self.item]}),self.response({'issues':[]}),self.response({'items':[other]}),self.response({'issues':[]})]
        client=AsyncMock();client.__aenter__.return_value=client
        payloads=[]
        async def post(*args,**kwargs):
            import copy
            payloads.append(copy.deepcopy(kwargs['json']))
            return responses.pop(0)
        client.post.side_effect=post
        names=[self.item['title'],other['title']]
        with patch.dict(app.os.environ,{'LLM_API_KEY':'test','LLM_BASE_URL':'https://example.invalid'}),patch.object(app.httpx,'AsyncClient',return_value=client),patch.object(rag,'retrieve',AsyncMock(return_value=[self.chunk])):
            result=await generate_bounded_section([self.doc],lambda *args:None,names,names)
        self.assertEqual([i.title for i in result],names)
        self.assertEqual(len(payloads),5)
        for payload in payloads:
            text=app.json.dumps(payload,ensure_ascii=False)
            self.assertIn(self.doc['text'],text)
            self.assertNotIn('BROKEN_JSON',text)

    async def test_single_item_truncation_has_bounded_clean_retries(self):
        from backend.checklist_generation import generate_bounded_section
        self.setup_inputs();client=AsyncMock();client.__aenter__.return_value=client
        limits=[];messages=[]
        async def post(*args,**kwargs):
            import copy
            limits.append(kwargs['json']['max_completion_tokens'])
            messages.append(copy.deepcopy(kwargs['json']['messages']))
            response=self.response({});response.json.return_value={'choices':[{'finish_reason':'length','message':{'content':'BROKEN_JSON'}}]}
            return response
        client.post.side_effect=post
        with patch.dict(app.os.environ,{'LLM_API_KEY':'test','LLM_BASE_URL':'https://example.invalid','LLM_CHAT_MODEL':'gpt-6.1-sol'}),patch.object(app.httpx,'AsyncClient',return_value=client),patch.object(rag,'retrieve',AsyncMock(return_value=[self.chunk])):
            with self.assertRaises(app.HTTPException) as caught:
                await generate_bounded_section([self.doc],lambda *args:None,[self.item['title']],[self.item['title']])
        self.assertEqual(caught.exception.status_code,422)
        self.assertEqual(limits,[6000,9000,12000])
        self.assertNotIn('BROKEN_JSON',app.json.dumps(messages))

    def setup_inputs(self):
        self.doc = dict(id='doc', name='인사 업무.docx', text='매월 말 근태를 마감한다.', rag={'summary':'근태 업무'})
        self.chunk = dict(chunk_id='chunk', document_id='doc', kind='text', text=self.doc['text'])
        self.item = dict(title='근태 마감 절차 확인', description='매월 말 근태를 마감하는 절차를 확인한다.', category='근태', priority='보통', evidence=[dict(document_id='doc', chunk_id='chunk', quote=self.doc['text'])])

    def response(self, payload):
        response = MagicMock(status_code=200)
        response.json.return_value = {'choices':[{'finish_reason':'stop', 'message':{'content':app.json.dumps(payload, ensure_ascii=False)}}]}
        return response

    async def run_generate(self, responses):
        client = AsyncMock()
        client.post.side_effect = [self.response(value) for value in responses]
        client.__aenter__.return_value = client
        with patch.dict(app.os.environ, {'LLM_API_KEY':'test-key', 'LLM_BASE_URL':'https://example.invalid'}), patch.object(app.httpx, 'AsyncClient', return_value=client), patch.object(rag, 'retrieve', AsyncMock(return_value=[self.chunk])):
            result = await app.generate_section([self.doc])
        return result, client

    async def test_content_audit_retries_with_actual_feedback(self):
        self.setup_inputs()
        result, client = await self.run_generate([
            {'items':[self.item]}, {'issues':['근태 마감 절차 확인: chunk의 매월 말 조건을 명확히 유지하세요.']},
            {'items':[self.item]}, {'issues':[]},
        ])
        self.assertEqual(len(result), 1)
        self.assertEqual(client.post.await_count, 4)
        correction = client.post.call_args_list[2].kwargs['json']['messages'][-1]['content']
        self.assertIn('매월 말 조건', correction)
        self.assertTrue(any(m['role']=='assistant' for m in client.post.call_args_list[2].kwargs['json']['messages']))

    async def test_false_citation_is_rejected_before_semantic_review(self):
        self.setup_inputs()
        invalid = dict(self.item, evidence=[dict(document_id='doc',chunk_id='chunk',quote='매일 오전 9시')])
        result, client = await self.run_generate([{'items':[invalid]}, {'items':[self.item]}, {'issues':[]}])
        self.assertEqual(client.post.await_count, 3)
        self.assertEqual(result[0].evidence[0].quote, self.doc['text'])

    async def test_repeated_content_problems_fail_closed(self):
        self.setup_inputs()
        with self.assertRaises(app.HTTPException) as caught:
            await self.run_generate([value for _ in range(3) for value in ({'items':[self.item]}, {'issues':['chunk와 설명의 조건이 다릅니다.']})])
        self.assertEqual(caught.exception.status_code,502)

    async def test_full_chunk_collection_has_no_top_k_omission(self):
        rows = [dict(document_id='doc', ordinal=n, kind='text', slide=0) for n in reversed(range(40))]
        collection = MagicMock()
        collection.get.return_value = dict(ids=[f'c{r["ordinal"]}' for r in rows],documents=[f'근태 업무 {r["ordinal"]}' for r in rows],metadatas=rows)
        doc = dict(id='doc', rag=dict(status='ready', embedding_model=rag.model(), version=rag.VERSION, index_id='idx', chunk_count=40))
        with patch.object(rag,'collection',return_value=collection):
            result = await rag.retrieve([doc], '.', lambda *args:None)
        self.assertEqual([row['ordinal'] for row in result], list(range(40)))
        self.assertTrue(all(row['slide'] is None for row in result))
        collection.query.assert_not_called()
