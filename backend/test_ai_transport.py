import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.ai_transport import post

class TransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_gateway_error_retries_same_payload_and_reports(self):
        client=AsyncMock();client.post.side_effect=[MagicMock(status_code=502),MagicMock(status_code=200)]
        report=MagicMock()
        with patch('backend.ai_transport.asyncio.sleep',new_callable=AsyncMock):
            response=await post(client,'https://example.invalid',label='초안',report=report,json={'model':'test'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(client.post.await_count,2)
        self.assertEqual(client.post.call_args_list[0],client.post.call_args_list[1])
        self.assertIn('재시도',report.call_args_list[0].args[1])

    async def test_retry_is_bounded(self):
        client=AsyncMock();client.post.return_value=MagicMock(status_code=503)
        with patch('backend.ai_transport.asyncio.sleep',new_callable=AsyncMock):
            response=await post(client,'https://example.invalid',label='검토')
        self.assertEqual(response.status_code,503)
        self.assertEqual(client.post.await_count,2)

    async def test_invalid_credentials_are_not_retried(self):
        client=AsyncMock();client.post.return_value=MagicMock(status_code=401)
        await post(client,'https://example.invalid',label='초안')
        self.assertEqual(client.post.await_count,1)
