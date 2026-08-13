"""
ตรวจการหาไฟล์เสียงของการประชุม โดยไม่ต้องต่อ DB หรือยิง HTTP

    python -m unittest discover -s tests -v

จุดที่พังแล้วเจ็บจริง:
  * path ชี้ออกนอก upload_dir ต้องถูกปฏิเสธ ไม่ใช่ยอมส่งไฟล์ในเครื่องออกไป
  * ไฟล์หายไปแล้วต้องคืน None ให้ API ตอบ 404 ไม่ใช่ 500
"""

import os
import tempfile
import unittest
from pathlib import Path

from app.services.audio_file import audio_media_type, resolve_audio_path


class ResolveAudioPath(unittest.TestCase):
    """ด่านกันอ่านไฟล์นอกโฟลเดอร์อัปโหลด — audio_uri ใน DB แก้ได้ จึงเชื่อไม่ได้"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.upload_dir = self.tmp.name
        self.audio = os.path.join(self.upload_dir, "meeting_1234.mp3")
        Path(self.audio).write_bytes(b"ID3fake")

    def tearDown(self):
        self.tmp.cleanup()

    def test_finds_file_inside_upload_dir(self):
        self.assertEqual(resolve_audio_path(self.audio, self.upload_dir), Path(self.audio).resolve())

    def test_rejects_path_escaping_upload_dir(self):
        outside = Path(self.upload_dir).parent / "secret.mp3"
        outside.write_bytes(b"ID3fake")
        try:
            escape = os.path.join(self.upload_dir, "..", "secret.mp3")
            self.assertIsNone(resolve_audio_path(escape, self.upload_dir))
        finally:
            outside.unlink()

    def test_missing_file_is_none(self):
        self.assertIsNone(resolve_audio_path(os.path.join(self.upload_dir, "gone.mp3"), self.upload_dir))

    def test_directory_is_not_playable(self):
        self.assertIsNone(resolve_audio_path(self.upload_dir, self.upload_dir))

    def test_no_audio_uri_is_none(self):
        # การประชุมที่อัปโหลดเป็น transcript ไม่มีไฟล์เสียง
        self.assertIsNone(resolve_audio_path(None, self.upload_dir))
        self.assertIsNone(resolve_audio_path("", self.upload_dir))


class MediaType(unittest.TestCase):
    def test_guesses_from_extension(self):
        self.assertEqual(audio_media_type(Path("a.mp3")), "audio/mpeg")

    def test_unknown_extension_falls_back_to_bytes(self):
        # ปล่อยให้ browser ตัดสินใจเอง ดีกว่าโกหกชนิดไฟล์
        self.assertEqual(audio_media_type(Path("a.weird")), "application/octet-stream")


if __name__ == "__main__":
    unittest.main()
