import unittest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from backend import dependencies


class DependencyTests(unittest.IsolatedAsyncioTestCase):
    def items(self):
        return [
            {'id':'a','title':'권한 준비','description':'계정 접근 확인','evidence':[{'quote':'접근 권한 확보 후 테스트를 진행한다.'}]},
            {'id':'b','title':'테스트 확인','description':'환경 테스트','evidence':[]},
        ]

    async def test_suggestion_links_stable_ids_and_evidence(self):
        edge={'item_id':'b','prerequisite_id':'a','reason':'테스트에 접근 권한이 필요하다.','quote':'접근 권한 확보 후 테스트를 진행한다.'}
        with patch.object(dependencies,'json_call',AsyncMock(return_value={'relations':[edge]})):
            result=await dependencies.suggest(self.items())
        self.assertEqual(result[1]['dependencies'],['a'])
        self.assertEqual(result[1]['dependency_notes']['a']['quote'],edge['quote'])
        self.assertNotIn('dependencies',self.items()[0])

    async def test_invalid_quote_not_saved(self):
        edge={'item_id':'b','prerequisite_id':'a','reason':'먼저 수행','quote':'존재하지 않는 원문'}
        with patch.object(dependencies,'json_call',AsyncMock(return_value={'relations':[edge]})) as call:
            with self.assertRaises(HTTPException):
                await dependencies.suggest(self.items())
        self.assertEqual(call.await_count,3)

    async def test_cycle_rejected(self):
        items=self.items()
        items[0]['dependencies']=['b'];items[1]['dependencies']=['a']
        with self.assertRaises(HTTPException) as error:
            dependencies.validate(items)
        self.assertIn('권한 준비',error.exception.detail)
        self.assertIn('테스트 확인',error.exception.detail)

    async def test_no_relation_is_valid(self):
        with patch.object(dependencies,'json_call',AsyncMock(return_value={'relations':[]})):
            result=await dependencies.suggest(self.items())
        self.assertTrue(all(not i['dependencies'] for i in result))
