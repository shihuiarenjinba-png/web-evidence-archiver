import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from archiver import WebEvidenceArchiver, sha256_file


class FakePage:
    def __init__(self, fail_at=None):
        self.url = 'https://example.com/record'
        self.fail_at = fail_at
    def goto(self, url, **kwargs):
        if self.fail_at == 'goto':
            raise RuntimeError('navigation failed')
        self.url = url
        return SimpleNamespace(status=200)
    def wait_for_timeout(self, ms):
        pass
    def content(self):
        return '<html><body>Evidence</body></html>'
    def screenshot(self, path, **kwargs):
        Path(path).write_bytes(b'png bytes')
    def pdf(self, path, **kwargs):
        if self.fail_at == 'pdf':
            raise RuntimeError('PDF failed')
        Path(path).write_bytes(b'pdf bytes')
    def title(self):
        return 'Evidence'


class CaptureTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archiver = WebEvidenceArchiver.__new__(WebEvidenceArchiver)
        self.archiver.allow_hosts = ['example.com']
        self.archiver.timeout_ms = 1000
    def test_complete_set_published(self):
        result = self.archiver._capture_one(FakePage(), self.root, 1, 'https://example.com/record')
        folder = self.root / result['folder']
        self.assertTrue((folder/'page.html').exists())
        self.assertTrue((folder/'screenshot.png').exists())
        self.assertTrue((folder/'page.pdf').exists())
        metadata = json.loads((folder/'metadata.json').read_text(encoding='utf-8'))
        self.assertEqual(metadata['files']['pdf']['sha256'], sha256_file(folder/'page.pdf'))
    def test_http_404_is_not_published_as_success(self):
        class NotFoundPage(FakePage):
            def goto(self, url, **kwargs):
                self.url = url
                return SimpleNamespace(status=404)
        with self.assertRaisesRegex(ValueError, "successful HTTP response"):
            self.archiver._capture_one(NotFoundPage(), self.root, 1,
                                       "https://example.com/missing")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_pdf_failure_leaves_no_partial_folder(self):
        with self.assertRaises(RuntimeError):
            self.archiver._capture_one(FakePage(fail_at='pdf'), self.root, 1, 'https://example.com/record')
        self.assertEqual(list(self.root.iterdir()), [])
    def test_navigation_failure_leaves_no_partial_folder(self):
        with self.assertRaises(RuntimeError):
            self.archiver._capture_one(FakePage(fail_at='goto'), self.root, 1, 'https://example.com/record')
        self.assertEqual(list(self.root.iterdir()), [])


if __name__=='__main__':
    unittest.main()
