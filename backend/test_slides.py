import base64
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from backend.test_support import ScopedTestClient
from backend import app as module


class SlideTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(module, 'DB', Path(self.temp.name)/'test.sqlite3')
        self.patch.start()
        self.client = ScopedTestClient(module)
        self.id = str(uuid.uuid4())

    def tearDown(self):
        self.client.close(); self.patch.stop(); self.temp.cleanup()

    def seed(self):
        module.read_state()
        module.register_document(self.id,'test.pptx','본문',[], 'hash',1)
        path = module.slide_path(self.id,1); path.parent.mkdir(parents=True)
        path.write_bytes(b'png-data')
        return module.read_state()['documents']

    def test_image_payload_and_slide_endpoint(self):
        docs = self.seed()
        content = module.build_content(docs)
        self.assertIn('슬라이드 1', content[1]['text'])
        self.assertEqual(content[2]['image_url']['url'], 'data:image/png;base64,'+base64.b64encode(b'png-data').decode())
        self.assertEqual(self.client.get(f'/api/documents/{self.id}/slides/1').content,b'png-data')
        self.assertEqual(self.client.get(f'/api/documents/{self.id}/slides/2').status_code,404)

    def test_visual_reference_is_not_text_quote(self):
        docs=self.seed()
        item=module.Item(title='검토',description='흐름 확인',category='운영',priority='보통',evidence=[module.Evidence(document_id=self.id,kind='visual',slide=1,quote='화살표로 표현된 흐름')])
        module.validate_evidence([item],docs,True)
        item.evidence[0].slide=2
        with self.assertRaises(ValueError): module.validate_evidence([item],docs,True)
        item.evidence[0].kind='text'
        with self.assertRaises(ValueError): module.validate_evidence([item],docs,True)

    def test_delete_removes_assets_and_access(self):
        self.seed(); state=module.read_state()
        self.assertEqual(self.client.delete(f'/api/documents/{self.id}?revision={state["revision"]}').status_code,200)
        self.assertFalse(module.slide_path(self.id,1).exists())
        self.assertEqual(self.client.get(f'/api/documents/{self.id}/slides/1').status_code,404)

    def test_missing_images_stop_analysis(self):
        docs=self.seed();module.slide_path(self.id,1).unlink()
        with self.assertRaises(module.HTTPException): module.build_content(docs)
