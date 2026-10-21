import unittest
from backend.app import Item, Evidence, validate_output_language, OutputLanguageError


class OutputLanguageTests(unittest.TestCase):
    def item(self, **changes):
        values = dict(title='배치 업무 범위 및 문의 전달 확인', description='API와 SQL 실행 절차를 확인한다.', category='업무 범위', priority='보통', evidence=[Evidence(document_id='source', quote='确认批次业务范围')])
        return Item(**(values | changes))

    def test_reject_mixed_generated_prose(self):
        for field in ('title', 'description', 'category'):
            with self.subTest(field=field), self.assertRaises(OutputLanguageError):
                validate_output_language([self.item(**{field:'确认批次业务范围与 문의 전달'})])

    def test_preserve_verbatim_foreign_evidence_and_english_terms(self):
        item = self.item()
        validate_output_language([item])
        self.assertEqual(item.evidence[0].quote, '确认批次业务范围')
