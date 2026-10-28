import unittest,json
from unittest.mock import AsyncMock,patch
from backend import app,rag
from backend.checklist_generation import generate_full_context
from backend.checklist_generation import repair
from backend.checklist_generation import assign_targets, generate_bounded_section, TargetAssignmentError

class TargetAssignmentTests(unittest.TestCase):
    def test_ids_preserve_intended_titles_order_and_content(self):
        data={'items':[{'target_id':'target-2','title':'표현을 바꾼 제목','description':'두 번째 업무'}, {'target_id':'target-1','title':'다른 표현','description':'첫 번째 업무'}]}
        result=assign_targets(data,['권한 회수 확인','공유자료 이전과 보존 검토'])
        self.assertEqual([i['title'] for i in result['items']],['권한 회수 확인','공유자료 이전과 보존 검토'])
        self.assertEqual(result['items'][0]['description'],'첫 번째 업무')
        self.assertNotIn('target_id',result['items'][0])
        self.assertEqual(data['items'][0]['title'],'표현을 바꾼 제목')

    def test_missing_extra_duplicate_and_unknown_ids_are_rejected(self):
        for rows in ([],[{'target_id':'target-1'}], [{'target_id':'target-1'}]*2, [{'target_id':'target-1'},{'target_id':'target-3'}]):
            with self.subTest(rows=rows),self.assertRaises(TargetAssignmentError):
                assign_targets({'items':rows},['업무 A','업무 B'])

    def test_legacy_titles_allow_only_whitespace_changes(self):
        self.assertEqual(assign_targets({'items':[{'title':'권한  회수'}]},['권한 회수'])['items'][0]['title'],'권한 회수')
        with self.assertRaises(TargetAssignmentError):
            assign_targets({'items':[{'title':'공유자료 이전'}]},['권한 회수'])

class GenerationTests(unittest.IsolatedAsyncioTestCase):
    async def test_truncated_outline_retries_with_more_output_budget(self):
        replies=[{'choices':[{'finish_reason':'length','message':{'content':'{"tasks":['}}]}, {'choices':[{'finish_reason':'stop','message':{'content':'{"tasks":["업무"]}'}}]}]
        item=app.Item(title='업무',description='확인',category='업무',priority='보통')
        with patch.object(rag,'retrieve',AsyncMock(return_value=[])),patch.object(rag,'request',AsyncMock(side_effect=replies)) as request,patch.object(rag,'chat_model',return_value='gpt-6.1-sol'),patch.object(app,'generate_section',AsyncMock(return_value=[item])),patch.object(app,'audit_checklist',AsyncMock(return_value=app.ChecklistAudit(issues=[]))),patch.dict('os.environ',{'LLM_BASE_URL':'https://example.invalid'}):
            result=await generate_full_context([],lambda *args:None)
        self.assertEqual(result,[item])
        self.assertEqual(request.call_args_list[0].args[2]['max_completion_tokens'],3000)
        self.assertEqual(request.call_args_list[1].args[2]['max_completion_tokens'],6000)

    async def test_target_failure_splits_only_affected_group_with_full_context(self):
        docs=[{'id':'a'},{'id':'b'}];outline=['A','B','C']
        async def write(documents,report,targets,all_tasks,feedback):
            self.assertEqual(documents,docs);self.assertEqual(all_tasks,outline)
            if len(targets)>1: raise TargetAssignmentError('업무 누락')
            return [app.Item(title=targets[0],description='확인',category='업무',priority='보통')]
        with patch.object(app,'generate_section',AsyncMock(side_effect=write)) as call:
            result=await generate_bounded_section(docs,lambda *args:None,['A','B'],outline)
        self.assertEqual([i.title for i in result],['A','B'])
        self.assertEqual(call.await_count,3)

    async def test_single_target_failure_never_returns_partial_result(self):
        with patch.object(app,'generate_section',AsyncMock(side_effect=TargetAssignmentError('업무 누락'))):
            with self.assertRaises(app.HTTPException):
                await generate_bounded_section([],lambda *args:None,['A'],['A'])

    async def test_repair_can_split_a_broad_item_into_independent_tasks(self):
        docs=[{'id':'d','text':'권한을 신청한다. 환경을 구성한다.'}]
        source={'chunks':[{'chunk_id':'c','document_id':'d','kind':'text','text':docs[0]['text']}]}
        broad=app.Item(title='권한과 환경 준비',description=docs[0]['text'],category='준비',priority='보통',evidence=[app.Evidence(document_id='d',chunk_id='c',quote=docs[0]['text'])])
        first=broad.model_copy(update={'title':'권한 확인','description':'권한을 신청한다.'})
        second=broad.model_copy(update={'title':'환경 구성','description':'환경을 구성한다.'})
        with patch('backend.agents.json_call',AsyncMock(return_value={'replacements':[{'index':0,'item':first.model_dump()}],'additions':[second.model_dump()]})) as call:
            result=await repair([broad],['독립 완료 업무로 분리'],source,docs,lambda *args:None)
        self.assertEqual([i.title for i in result],['권한 확인','환경 구성'])
        self.assertIn('분리한 독립 업무',call.call_args.args[1])

    async def test_text_zero_slide_repair_and_addition_pass_without_retry(self):
        docs=[{'id':'d','text':'승인 후 전달한다.'}]
        source={'chunks':[{'chunk_id':'c','document_id':'d','kind':'text','slide':None,'text':docs[0]['text']}]}
        raw={'title':'승인','description':'승인 후 전달한다.','category':'업무','priority':'보통','evidence':[{'document_id':'d','chunk_id':'c','quote':docs[0]['text'],'kind':'text','slide':0}]}
        first=app.Item(**raw)
        with patch('backend.agents.json_call',AsyncMock(return_value={'replacements':[{'index':0,'item':raw}],'additions':[{**raw,'title':'전달'}]})) as call:
            result=await repair([first],['조건'],source,docs,lambda *args:None)
        self.assertEqual(call.await_count,1)
        self.assertEqual(len(result),2)
        self.assertTrue(all(i.evidence[0].slide is None for i in result))
        self.assertEqual(raw['evidence'][0]['slide'],0)

    def test_invalid_visual_slide_still_rejected(self):
        from pydantic import ValidationError
        for number in (0,-1):
            with self.assertRaises(ValidationError):
                app.Evidence(document_id='d',quote='장표 근거',kind='visual',slide=number)
        evidence=app.Evidence(document_id='d',quote='장표 근거',kind='visual',slide=2)
        self.assertEqual(evidence.slide,2)

    async def test_repair_retries_invalid_quote_without_mutating_original(self):
        docs=[{'id':'d','text':'승인 후 전달한다.'}]
        source={'chunks':[{'chunk_id':'c','document_id':'d','kind':'text','text':docs[0]['text']}]}
        item=app.Item(title='승인',description='승인 확인',category='업무',priority='보통',evidence=[app.Evidence(document_id='d',chunk_id='c',quote=docs[0]['text'])])
        invalid=item.model_dump();invalid['evidence'][0]['quote']='원문에 없는 인용'
        valid=item.model_dump();valid['description']='승인 후 전달한다.'
        responses=[{'replacements':[{'index':0,'item':invalid}]},{'replacements':[{'index':0,'item':valid}]}]
        with patch('backend.agents.json_call',AsyncMock(side_effect=responses)) as call:
            result=await repair([item],['승인 조건'],source,docs,lambda *args:None)
        self.assertEqual(call.await_count,2)
        self.assertIn('인용',call.call_args.args[2]['validation_feedback'])
        self.assertEqual(item.description,'승인 확인')
        self.assertEqual(result[0].description,'승인 후 전달한다.')

    async def test_repair_exhaustion_reports_schema_error_without_input_values(self):
        with patch('backend.agents.json_call',AsyncMock(return_value={'replacements':[{'index':0,'item':{'title':'PRIVATE'}}]})) as call:
            with self.assertRaises(app.HTTPException) as error:
                await repair([],['조건'],{'chunks':[]},[],lambda *args:None)
        self.assertEqual(call.await_count,3)
        self.assertEqual(error.exception.status_code,422)
        self.assertNotIn('PRIVATE',error.exception.detail)
        self.assertIn('replacements.0.item',error.exception.detail)

    async def test_targeted_repair_preserves_unrelated_items_and_checks_sources(self):
        docs=[{'id':'d','text':'승인 후 전달한다.'}]
        source={'chunks':[{'chunk_id':'c','document_id':'d','kind':'text','text':docs[0]['text']}]}
        first=app.Item(title='승인',description='승인을 확인한다.',category='업무',priority='보통',evidence=[app.Evidence(document_id='d',chunk_id='c',quote=docs[0]['text'])])
        second=first.model_copy(update={'title':'전달'})
        updated=first.model_copy(update={'description':'승인 후에만 전달한다.'})
        with patch('backend.agents.json_call',AsyncMock(return_value={'replacements':[{'index':0,'item':updated.model_dump()}],'additions':[]})):
            result=await repair([first,second],['승인 조건 보완'],source,docs,lambda *args:None)
        self.assertEqual(result[0].description,updated.description)
        self.assertEqual(result[1],second)

    def test_cross_document_item_preserves_more_than_ten_valid_sources(self):
        docs=[{'id':str(i),'text':f'조건 {i} 확인'} for i in range(11)]
        item=app.Item(title='교차 조건 확인',description='각 문서의 조건을 확인한다.',category='업무',priority='보통',evidence=[app.Evidence(document_id=d['id'],quote=d['text']) for d in docs])
        app.validate_evidence([item],docs,True)
        self.assertEqual({e.document_id for e in item.evidence},{d['id'] for d in docs})

    async def test_every_section_sees_all_sources_and_global_plan(self):
        docs=[{'id':'a','name':'a'},{'id':'b','name':'b'}]
        names=[f'업무 {i}' for i in range(9)]
        response={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'tasks':names})}}]}
        async def section(documents,report,targets,outline,feedback):
            self.assertEqual(documents,docs);self.assertEqual(outline,names)
            return [app.Item(title=t,description='확인',category='업무',priority='보통') for t in targets]
        with patch.object(rag,'retrieve',AsyncMock(return_value=[])),patch.object(rag,'request',AsyncMock(return_value=response)),patch.object(app,'generate_section',AsyncMock(side_effect=section)) as writer,patch.object(app,'audit_checklist',AsyncMock(return_value=app.ChecklistAudit(issues=[]))) as auditor,patch.dict('os.environ',{'LLM_BASE_URL':'https://example.invalid'}):
            items=await generate_full_context(docs,lambda *args:None)
        self.assertEqual([i.title for i in items],names)
        self.assertEqual(writer.await_count,5)
        self.assertEqual(len(auditor.call_args.args[5].items),9)

    async def test_duplicate_outline_fails_before_writing(self):
        response={'choices':[{'finish_reason':'stop','message':{'content':'{"tasks":["업무","업무"]}'}}]}
        with patch.object(rag,'retrieve',AsyncMock(return_value=[])),patch.object(rag,'request',AsyncMock(return_value=response)),patch.object(app,'generate_section',AsyncMock()) as writer:
            with self.assertRaises(app.HTTPException):await generate_full_context([],lambda *args:None)
        writer.assert_not_called()

    async def test_global_feedback_is_passed_back_before_success(self):
        response={'choices':[{'finish_reason':'stop','message':{'content':'{"tasks":["업무"]}'}}]}
        item=app.Item(title='업무',description='확인',category='업무',priority='보통')
        with patch.object(rag,'retrieve',AsyncMock(return_value=[])),patch.object(rag,'request',AsyncMock(return_value=response)),patch.object(app,'generate_section',AsyncMock(return_value=[item])) as writer,patch('backend.checklist_generation.repair',AsyncMock(return_value=[item])) as repair,patch.object(app,'audit_checklist',AsyncMock(side_effect=[app.ChecklistAudit(issues=['예외 조건 확인']),app.ChecklistAudit(issues=[])])),patch.dict('os.environ',{'LLM_BASE_URL':'https://example.invalid'}):
            result=await generate_full_context([],lambda *args:None)
        self.assertEqual(result,[item])
        self.assertEqual(writer.await_count,1)
        self.assertEqual(repair.call_args.args[1],['예외 조건 확인'])

    async def test_unresolved_global_issues_never_return_partial_result(self):
        response={'choices':[{'finish_reason':'stop','message':{'content':'{"tasks":["업무"]}'}}]}
        item=app.Item(title='업무',description='확인',category='업무',priority='보통')
        with patch.object(rag,'retrieve',AsyncMock(return_value=[])),patch.object(rag,'request',AsyncMock(return_value=response)),patch.object(app,'generate_section',AsyncMock(return_value=[item])),patch('backend.checklist_generation.repair',AsyncMock(return_value=[item])) as fix,patch.object(app,'audit_checklist',AsyncMock(return_value=app.ChecklistAudit(issues=['필수 조건 누락']))) as audit,patch.dict('os.environ',{'LLM_BASE_URL':'https://example.invalid'}):
            with self.assertRaises(app.HTTPException):
                await generate_full_context([],lambda *args:None)
        self.assertEqual(fix.await_count,4)
        self.assertEqual(audit.await_count,5)

    async def test_malformed_final_audit_has_explicit_failure(self):
        response={'choices':[{'finish_reason':'stop','message':{'content':'{"tasks":["업무"]}'}}]}
        item=app.Item(title='업무',description='확인',category='업무',priority='보통')
        with patch.object(rag,'retrieve',AsyncMock(return_value=[])),patch.object(rag,'request',AsyncMock(return_value=response)),patch.object(app,'generate_section',AsyncMock(return_value=[item])),patch.object(app,'audit_checklist',AsyncMock(side_effect=ValueError('내용 검토 응답이 완성되지 않았습니다.'))),patch.dict('os.environ',{'LLM_BASE_URL':'https://example.invalid'}):
            with self.assertRaises(app.HTTPException) as error:
                await generate_full_context([],lambda *args:None)
        self.assertEqual(error.exception.status_code,422)
        self.assertIn('최종 검토 응답',error.exception.detail)
