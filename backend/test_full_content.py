import unittest
from unittest.mock import AsyncMock,patch
from backend import rag,app

class FullContentTests(unittest.IsolatedAsyncioTestCase):
    async def test_text_is_not_rewritten_or_summarized(self):
        with patch.object(rag,'request',AsyncMock()) as request:
            value=await rag._summarize({'text':'[시트 A / 행 1]\nA1: 1.234','slide_count':0},[])
        request.assert_not_called()
        self.assertEqual(value['slides'],[])

    async def test_each_slide_is_transcribed_without_summary_or_truncation(self):
        text='수치 1.234, 예외 조건, 화살표 A → B\n'*500
        result={'choices':[{'finish_reason':'stop','message':{'content':app.json.dumps({'text':text,'unreadable':['우측 하단 흐림']})}}]}
        images=[{'type':'image_url','image_url':{'url':'data:image/png;base64,test'}}]*2
        with patch.object(rag,'request',AsyncMock(return_value=result)) as request:
            value=await rag._summarize({'slide_count':2},images)
        self.assertEqual(request.await_count,2)
        self.assertEqual(value['slides'][1]['text'],text)
        self.assertEqual(value['slides'][0]['unreadable'],['우측 하단 흐림'])
        for call in request.call_args_list:
            self.assertEqual(len([v for v in call.args[2]['messages'][1]['content'] if v['type']=='image_url']),1)

    async def test_truncated_transcription_is_rejected(self):
        result={'choices':[{'finish_reason':'length','message':{'content':'{}'}}]}
        with patch.object(rag,'request',AsyncMock(return_value=result)):
            with self.assertRaises(app.HTTPException):
                await rag._summarize({'slide_count':1},[{'type':'image_url'}])

    async def test_checklist_does_not_read_or_send_images(self):
        from backend.test_checklist_quality import ChecklistQualityTests
        helper=ChecklistQualityTests();helper.setup_inputs()
        helper.doc['slide_count']=3
        with patch.object(app,'build_content',side_effect=AssertionError('Images must not be read for checklist')):
            _,client=await helper.run_generate([{'items':[helper.item]},{'issues':[]}])
        for call in client.post.call_args_list:
            self.assertNotIn('image_url',app.json.dumps(call.kwargs['json']))
