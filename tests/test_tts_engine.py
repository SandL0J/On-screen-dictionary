"""
TTS Motoru Devre Dışı Bırakılma ve Geriye Dönük Uyumluluk Testleri
"""
import unittest
from app.tts_engine import GermanTTSEngine


class TestTTSEngine(unittest.TestCase):
    def setUp(self):
        self.tts = GermanTTSEngine()

    def test_audio_download_disabled(self):
        # Dinleme özelliği kaldırıldığı için indirme None dönmeli ve dosya üretmemeli
        text = "Danke"
        path = self.tts.download_audio(text)
        self.assertIsNone(path)

    def test_play_non_blocking_noop(self):
        # play çağrısı ses çalmadan ve kilitlenmeden anında güvenli bir şekilde dönmeli
        try:
            self.tts.play("Guten Tag")
            success = True
        except Exception:
            success = False
        self.assertTrue(success)


if __name__ == "__main__":
    unittest.main()
