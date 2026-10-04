"""
Birim testleri: Hassas Pano Filtresi (Sensitive Clipboard Filter)
Parola, API anahtarı, erişim belirteci, IBAN, kredi kartı ve 40+ karakterlik
boşluksuz verilerin panodan otomatik çeviriye sızmasını engeller.
"""
import unittest
from unittest.mock import MagicMock, patch

from app.security import (
    check_sensitive_clipboard,
    is_sensitive_clipboard_text,
    luhn_checksum,
)
from app.clipboard_watcher import ClipboardWatcher


class TestSensitiveClipboardFilter(unittest.TestCase):
    def test_manager_reported_misses_are_now_detected(self):
        """Kod incelemesinde bildirilen 3 kritik örnek artık güvenle tespit edilmelidir."""
        misses = [
            ("Meine IBAN: TR330006100519789012345678", "IBAN Numarası"),
            ("Kartennummer 378282246310005", "Kredi Kartı"),
            ("Passwort: P@ssw0rd123!", "Parola"),
        ]
        for text, keyword in misses:
            is_sens, reason = check_sensitive_clipboard(text)
            self.assertTrue(is_sens, f"Bildirilen örnek tespit edilemedi: '{text}'")
            self.assertIn(keyword.lower(), reason.lower())
            self.assertTrue(is_sensitive_clipboard_text(text))

    def test_case_insensitive_and_grouped_iban_detection(self):
        """Küçük harfli (de/tr/gb), boşluklu ve tireli gruplanmış IBAN'lar güvenle yakalanmalıdır."""
        iban_samples = [
            ("Meine IBAN: de89370400440532013000", "Küçük harfli DE IBAN"),
            ("Meine IBAN: tr330006100519789012345678", "Küçük harfli TR IBAN"),
            ("Konto: gb82 west 1234 5698 7654 32", "Küçük harfli ve banka kodlu GB IBAN"),
            ("Konto: gb82-west-1234-5698-7654-32", "Tireli gruplanmış küçük harfli GB IBAN"),
            ("Hier ist de89 3704 0044 0532 0130 00 für die Überweisung", "Cümle içinde boşluklu küçük harfli DE"),
            ("Lütfen tr33 0006 1005 1978 9012 3456 78 hesabına yatırın", "Cümle içinde boşluklu küçük harfli TR"),
            ("DE89-3704-0044-0532-0130-00", "Büyük harfli tireli DE IBAN"),
            ("FR14-2004-1010-0505-0001-3M02-606", "Fransa IBAN kalıbı"),
        ]
        for text, desc in iban_samples:
            is_sens, reason = check_sensitive_clipboard(text)
            self.assertTrue(is_sens, f"{desc} tespit edilemedi: '{text}'")
            self.assertIn("iban", reason.lower())
            self.assertTrue(is_sensitive_clipboard_text(text))

    def test_labeled_and_multiline_secrets(self):
        """Etiketli (Passwort, Kennwort, Parola vb.) ve çok satırlı panolar algılanmalıdır."""
        samples = [
            ("Password = secret_token_123", "Etiketli Parola"),
            ("Kennwort: MeinGeheimes123!", "Etiketli Parola"),
            ("Parola: 123456Abc!", "Etiketli Parola"),
            ("Passcode - 987654Secret", "Etiketli Parola"),
            ("api_key: sk-1234567890abcdef123456", "API Gizli"),
            ("Benutzer: admin\nPasswort:\nP@ssw0rd123!", "Etiketli Parola"),
            ("Konto:\nIBAN: DE89 3704 0044 0532 0130 00", "IBAN"),
        ]
        for text, kw in samples:
            is_sens, reason = check_sensitive_clipboard(text)
            self.assertTrue(is_sens, f"Etiketli/çok satırlı pano yakalanamadı: '{text}'")
            self.assertTrue(is_sensitive_clipboard_text(text))

    def test_luhn_checksum_and_credit_cards(self):
        """Luhn algoritması ve kredi kartı tespiti (13-19 hane) doğrulanmalıdır."""
        # 15 haneli Amex (Luhn geçerli)
        amex = "378282246310005"
        self.assertTrue(luhn_checksum(amex))
        self.assertTrue(is_sensitive_clipboard_text(f"Kartennummer {amex}"))
        self.assertTrue(is_sensitive_clipboard_text(f"Card {amex}"))

        # Luhn geçersiz ancak etiketli kart
        self.assertTrue(is_sensitive_clipboard_text("Kartennummer 123456789012345"))

        # Standart 4x4 bloklu kart kalıbı
        self.assertTrue(is_sensitive_clipboard_text("4532-1234-5678-9010"))
        self.assertTrue(is_sensitive_clipboard_text("4532 1234 5678 9010"))

        # Normal kısa sayılar Luhn kontrolünden geçmemeli
        self.assertFalse(luhn_checksum("12345"))
        self.assertFalse(luhn_checksum("2026"))

    def test_sentence_embedded_password_token(self):
        """Cümle içine gömülü karmaşık parola belirteçleri algılanmalıdır."""
        sentence = "Mein neues Passwort ist P@ssw0rd123! bitte merken"
        is_sens, reason = check_sensitive_clipboard(sentence)
        self.assertTrue(is_sens)
        self.assertIn("Parola", reason)

    def test_long_token_without_whitespace_rejected(self):
        """40 karakterden uzun ve içinde boşluk olmayan dizgeler hassas kabul edilmelidir."""
        long_str = "a" * 45
        is_sens, reason = check_sensitive_clipboard(long_str)
        self.assertTrue(is_sens)
        self.assertIn("40 karakter", reason)
        self.assertTrue(is_sensitive_clipboard_text(long_str))

        # 40 karakterden kısa normal boşluksuz kelime reddedilmemeli
        short_str = "Donaudampfschiff"  # 16 karakter
        self.assertFalse(is_sensitive_clipboard_text(short_str))

    def test_api_keys_and_secret_tokens_rejected(self):
        """Google API, API gizli anahtarları, GitHub token, AWS key, JWT, DPAPI ve Private Key algılanmalıdır."""
        sensitive_samples = [
            ("AIzaSyD-1234567890abcdefghijklmnopqrstuv", "Google API Anahtarı"),
            ("sk-proj-1234567890abcdef1234567890", "API Gizli Anahtarı"),
            ("ghp_1234567890abcdefghijklmnopqrstuvwxyzAB", "GitHub Erişim Belirteci"),
            ("AKIAIOSFODNN7EXAMPLE", "AWS Erişim Anahtarı"),
            ("xoxb-dummy-test-token-slack-12345", "Slack Belirteci"),
            (
                "eyJhGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.sflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV",
                "JSON Web Token (JWT)"
            ),
            (
                "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC...\n-----END PRIVATE KEY-----",
                "Özel Anahtar (Private Key)"
            ),
            ("dpapi:AQAAANCMnd8BFdERjHoAwE123456789", "DPAPI Şifreli Metin"),
        ]

        for token, expected_keyword in sensitive_samples:
            is_sens, reason = check_sensitive_clipboard(token)
            self.assertTrue(is_sens, f"Algılanamadı: {token[:20]}")
            self.assertTrue(is_sensitive_clipboard_text(token))

    def test_passwords_and_manager_patterns_rejected(self):
        """Karmaşık parolalar, yüksek entropili belirteçler ve hash'ler reddedilmelidir."""
        passwords = [
            "P@ssw0rd123!",
            "K9#m$L2!pQ8*vR5^",
            "Admin.2026!#",
            "c3ab8ff1-3b11-49e3-b38b-4d1170c5e702",  # UUID
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # SHA256 (64 hex)
            "d41d8cd98f00b204e9800998ecf8427e",  # MD5 (32 hex)
        ]

        for pwd in passwords:
            self.assertTrue(
                is_sensitive_clipboard_text(pwd),
                f"Parola/belirteç algılanamadı: {pwd}"
            )

    def test_financial_and_pii_rejected(self):
        """IBAN ve kredi kartı numaraları reddedilmelidir."""
        financials = [
            "TR33 0006 1005 1978 9012 3456 78",
            "TR330006100519789012345678",
            "DE89370400440532013000",
            "4532-1234-5678-9010",
            "4532 1234 5678 9010",
        ]

        for fin in financials:
            is_sens, reason = check_sensitive_clipboard(fin)
            self.assertTrue(is_sens, f"Finansal veri algılanamadı: {fin}")
            self.assertTrue(is_sensitive_clipboard_text(fin))

    def test_legitimate_german_text_accepted(self):
        """Meşru Almanca kelimeler, cümleler ve tireli birleşik isimler güvenle kabul edilmelidir."""
        legit_samples = [
            "Hallo, wie geht es dir?",
            "Geschwindigkeitsbegrenzung",
            "Bundesverfassungsgericht",
            "Ich lerne Deutsch seit 2 Jahren.",
            "Das ist ein schöner Tag!",
            "100 Euro kostet das Buch.",
            "Kommen Sie bitte um 14:30 Uhr.",
            "Mund-zu-Mund-Beatmung",
            "Baden-Württemberg",
            "Nordrhein-Westfalen",
            "Österreich-Ungarn",
            "Entscheidung",
            "Überraschung",
            "Veränderung",
            "Im Jahr 2026 habe ich meinen Abschluss gemacht.",
            "Das Treffen findet am 15.10.2026 um 10:00 Uhr statt.",
            "Telefon: 0176 12345678",
            "ab20 euro gibt es hier",
            "Ab 20 Euro ist der Versand kostenlos.",
            "am 20. mai gibt es kuchen",
            "Sie erreichen uns unter der Rufnummer 0800 123456.",
            "Die Vorlesung beginnt um 08:15 Uhr im Raum 204.",
        ]

        for text in legit_samples:
            is_sens, reason = check_sensitive_clipboard(text)
            self.assertFalse(
                is_sens,
                f"Meşru Almanca metin yanlışlıkla hassas işaretlendi: '{text}' ({reason})"
            )
            self.assertFalse(is_sensitive_clipboard_text(text))

    def test_clipboard_watcher_rejects_sensitive_candidate(self):
        """ClipboardWatcher._is_valid_candidate hassas metinleri sessizce reddetmelidir."""
        detected = []
        watcher = ClipboardWatcher(on_text_detected=lambda t: detected.append(t))

        # Hassas metinler reddedilmeli
        self.assertFalse(watcher._is_valid_candidate("P@ssw0rd123!"))
        self.assertFalse(watcher._is_valid_candidate("TR330006100519789012345678"))
        self.assertFalse(watcher._is_valid_candidate("Meine IBAN: TR330006100519789012345678"))
        self.assertFalse(watcher._is_valid_candidate("Kartennummer 378282246310005"))
        self.assertFalse(watcher._is_valid_candidate("Passwort: P@ssw0rd123!"))
        self.assertFalse(watcher._is_valid_candidate("AIzaSyD-1234567890abcdefghijklmnopqrstuv"))
        self.assertFalse(watcher._is_valid_candidate("a" * 50))

        # Meşru metinler kabul edilmeli
        self.assertTrue(watcher._is_valid_candidate("Guten Morgen!"))
        self.assertTrue(watcher._is_valid_candidate("Wissenschaftler"))
        self.assertTrue(watcher._is_valid_candidate("Baden-Württemberg"))
        self.assertTrue(watcher._is_valid_candidate("Im Jahr 2026 habe ich gelernt."))

    def test_main_overlay_lookup_from_clipboard_blocks_sensitive_text(self):
        """MainOverlay._lookup_from_clipboard hassas metin kopyalandığında lookup_text çağırmamalı ve uyarı göstermelidir."""
        import tkinter as tk
        from app.gui.main_overlay import MainOverlay

        root = tk.Tk()
        root.withdraw()
        try:
            translator_mock = MagicMock()
            overlay = MainOverlay(
                root=root,
                translator=translator_mock,
                config={"clipboard_auto_lookup": False, "first_run_completed": True}
            )
            overlay.lookup_text = MagicMock()
            overlay._show_hud = MagicMock()

            # Hassas parola kopyalandığında simüle et
            with patch("app.gui.main_overlay.copy_selected_text_windows", return_value="Meine IBAN: TR330006100519789012345678"):
                with patch("app.gui.main_overlay.get_clipboard_text", return_value="Meine IBAN: TR330006100519789012345678"):
                    thread = overlay._lookup_from_clipboard()
                    if thread:
                        thread.join(timeout=1.0)
                    root.update()

            # lookup_text asla çağrılmamalıdır
            overlay.lookup_text.assert_not_called()
            # HUD uyarı kartı çağrılmış olmalıdır
            overlay._show_hud.assert_called_once()
            call_arg = overlay._show_hud.call_args[0][0]
            self.assertIn("Güvenlik Koruması", call_arg.get("error", ""))
        finally:
            if 'overlay' in locals():
                try:
                    overlay.stop()
                except Exception:
                    pass
            try:
                root.destroy()
            except Exception:
                pass

    def test_main_overlay_lookup_text_blocks_sensitive_text(self):
        """MainOverlay.lookup_text (OCR snip veya doğrudan çağrılar) hassas veride çeviriye gitmemeli ve güvenlik HUD'ı göstermelidir."""
        import tkinter as tk
        from app.gui.main_overlay import MainOverlay

        root = tk.Tk()
        root.withdraw()
        try:
            translator_mock = MagicMock()
            overlay = MainOverlay(
                root=root,
                translator=translator_mock,
                config={"clipboard_auto_lookup": False, "first_run_completed": True}
            )
            overlay._show_hud = MagicMock()

            # Hassas API anahtarı aratıldığında
            ret = overlay.lookup_text("AIzaSyD-1234567890abcdefghijklmnopqrstuv")
            self.assertIsNone(ret)
            root.update()

            # Çevirici çağrılmamalıdır
            translator_mock.translate_and_analyze.assert_not_called()
            # Güvenlik HUD'ı gösterilmelidir
            overlay._show_hud.assert_called_once()
            err_text = overlay._show_hud.call_args[0][0].get("error", "")
            self.assertIn("Güvenlik Koruması", err_text)
            self.assertIn("Google API Anahtarı", err_text)
        finally:
            if 'overlay' in locals():
                try:
                    overlay.stop()
                except Exception:
                    pass
            try:
                root.destroy()
            except Exception:
                pass

    def test_hover_tracker_blocks_sensitive_word(self):
        """HoverTracker farenin altında hassas kelime/parola tespit ettiğinde çeviri motoruna göndermemelidir."""
        from app.hover_tracker import HoverTracker
        from PIL import Image

        mock_ocr = MagicMock()
        mock_ocr.recognize_words_with_boxes.return_value = [
            {"x": 210, "y": 55, "w": 60, "h": 20, "text": "P@ssw0rd123!"}
        ]
        mock_translator = MagicMock()
        on_hover = MagicMock()
        on_leave = MagicMock()
        on_not_found = MagicMock()

        tracker = HoverTracker(
            ocr_engine=mock_ocr,
            translator=mock_translator,
            on_word_hover=on_hover,
            on_hover_leave=on_leave,
            on_not_found=on_not_found,
            trigger_mode="mouse_side",
            enabled=True
        )

        with patch("app.hover_tracker.capture_screen_rect_gdi", return_value=Image.new("RGB", (440, 120))):
            tracker._inspect_hover_area(cursor_x=200, cursor_y=200, is_passive_hover=False)

        # Çeviri motoru ve hover callback asla çağrılmamalıdır
        mock_translator.translate_and_analyze.assert_not_called()
        on_hover.assert_not_called()
        on_not_found.assert_called_once()

        tracker.stop()

    def test_hover_tracker_does_not_leak_sensitive_word_in_stdout_stderr_or_logs(self):
        """Sahte hassas değer hover/OCR akışına verildiğinde değer stdout, stderr veya loglarda görünmemelidir."""
        import io
        import sys
        from app.hover_tracker import HoverTracker
        from PIL import Image

        fake_secret = "AIzaSySecretApiKey1234567890TestKey"
        mock_ocr = MagicMock()
        mock_ocr.recognize_words_with_boxes.return_value = [
            {"x": 210, "y": 55, "w": 60, "h": 20, "text": fake_secret}
        ]
        mock_translator = MagicMock()
        on_hover = MagicMock()
        on_leave = MagicMock()
        on_not_found = MagicMock()

        tracker = HoverTracker(
            ocr_engine=mock_ocr,
            translator=mock_translator,
            on_word_hover=on_hover,
            on_hover_leave=on_leave,
            on_not_found=on_not_found,
            trigger_mode="mouse_side",
            enabled=True
        )

        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()

        with patch("sys.stdout", captured_stdout), patch("sys.stderr", captured_stderr):
            with patch("app.hover_tracker.capture_screen_rect_gdi", return_value=Image.new("RGB", (440, 120))):
                tracker._inspect_hover_area(cursor_x=200, cursor_y=200, is_passive_hover=False)

        tracker.stop()

        stdout_val = captured_stdout.getvalue()
        stderr_val = captured_stderr.getvalue()

        # 1. Değer kesinlikle stdout veya stderr'de görünmemelidir
        self.assertNotIn(fake_secret, stdout_val)
        self.assertNotIn(fake_secret, stderr_val)

        # 2. Çeviri motoru kesinlikle çağrılmamalıdır
        mock_translator.translate_and_analyze.assert_not_called()
        on_hover.assert_not_called()
        on_not_found.assert_called_once()

    def test_hover_tracker_unmatched_boxes_do_not_leak_raw_texts(self):
        """İmleç altında kelime bulunamadığında civardaki kutuların ham metinleri stdout'a yazılmamalıdır."""
        import io
        import sys
        from app.hover_tracker import HoverTracker
        from PIL import Image

        raw_secret_box = "SecretTokenBoxValue123"
        mock_ocr = MagicMock()
        # Kutuyu imleçten çok uzağa koy (x=0, y=0) ki hedef kelime bulunamasın
        mock_ocr.recognize_words_with_boxes.return_value = [
            {"x": 0, "y": 0, "w": 30, "h": 10, "text": raw_secret_box}
        ]
        mock_translator = MagicMock()
        on_hover = MagicMock()
        on_leave = MagicMock()
        on_not_found = MagicMock()

        tracker = HoverTracker(
            ocr_engine=mock_ocr,
            translator=mock_translator,
            on_word_hover=on_hover,
            on_hover_leave=on_leave,
            on_not_found=on_not_found,
            trigger_mode="mouse_side",
            enabled=True
        )

        captured_stdout = io.StringIO()
        with patch("sys.stdout", captured_stdout):
            with patch("app.hover_tracker.capture_screen_rect_gdi", return_value=Image.new("RGB", (440, 120))):
                tracker._inspect_hover_area(cursor_x=200, cursor_y=200, is_passive_hover=False)

        tracker.stop()
        stdout_val = captured_stdout.getvalue()
        self.assertNotIn(raw_secret_box, stdout_val)


class TestClosedDatabaseAndTranslatorLeakPrevention(unittest.TestCase):
    """
    Kapalı veritabanı veya hata durumlarında kullanıcı metinlerinin (sentinel)
    stdout, stderr veya log dosyalarına sızmadığını ve DB yazma başarısızlığının
    açıkça bildirildiğini doğrulayan güvenlik testleri.
    """
    SENTINEL = "FAKE_SECRET_SENTINEL_123"

    def setUp(self):
        import tempfile
        from pathlib import Path
        from app.database import Database
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp_dir.name) / "test_leak.db"
        self.db = Database(self.db_path)
        # Veritabanını güvenle kapat
        self.db.close()
        self.assertTrue(self.db.is_closed)

    def tearDown(self):
        self.db = None
        import gc
        gc.collect()
        try:
            self.tmp_dir.cleanup()
        except Exception:
            pass

    def test_closed_db_direct_writes_report_failure_and_do_not_leak_sentinel(self):
        """DB kapalıyken set_cache, add_history ve add_word başarısız olmalı ve sentinel'i konsola/loga yazmamalıdır."""
        import io
        import sys
        from app.paths import get_log_path

        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()

        with patch("sys.stdout", captured_stdout), patch("sys.stderr", captured_stderr):
            cache_res = self.db.set_cache(self.SENTINEL, {"turkish": "gizli_anlam"})
            hist_res = self.db.add_history(self.SENTINEL, {"turkish": "gizli_anlam"})
            word_res = self.db.add_word(german=self.SENTINEL, turkish="gizli_anlam")

        # 1. Başarısızlık açıkça bildirilmelidir
        self.assertFalse(cache_res, "Kapalı DB'ye set_cache False dönmelidir")
        self.assertFalse(hist_res, "Kapalı DB'ye add_history False dönmelidir")
        self.assertEqual(word_res, -1, "Kapalı DB'ye add_word -1 dönmelidir")

        # 2. Sentinel stdout ve stderr içinde kesinlikle bulunmamalıdır
        stdout_val = captured_stdout.getvalue()
        stderr_val = captured_stderr.getvalue()
        self.assertNotIn(self.SENTINEL, stdout_val, "Sentinel değeri stdout çıktısında sızmamalıdır")
        self.assertNotIn(self.SENTINEL, stderr_val, "Sentinel değeri stderr çıktısında sızmamalıdır")

        # 3. Log dosyasında da bulunmamalıdır
        log_file = get_log_path()
        if log_file.exists():
            log_content = log_file.read_text(encoding="utf-8")
            self.assertNotIn(self.SENTINEL, log_content, "Sentinel değeri log dosyasında sızmamalıdır")

    def test_translator_cache_hit_with_closed_db_does_not_leak_sentinel_and_flags_save_failure(self):
        """Önbellek dönüşünde (cache hit) kapalı DB'ye geçmiş kaydı yapılamazsa sentinel sızmamalı ve db_saved=False olmalıdır."""
        import io
        import sys
        from app.translator import TranslationEngine

        translator = TranslationEngine(db=self.db)
        # get_cache'in bir kayıt döndüğünü simüle et
        cached_data = {"german": self.SENTINEL, "turkish": "önbellek_çeviri", "original": self.SENTINEL}

        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()

        with patch.object(self.db, "get_cache", return_value=cached_data):
            with patch("sys.stdout", captured_stdout), patch("sys.stderr", captured_stderr):
                res = translator.translate_and_analyze(self.SENTINEL)

        self.assertFalse(res.get("db_saved", True), "Kapalı DB'ye geçmiş yazılamadığında db_saved False olmalıdır")
        self.assertNotIn(self.SENTINEL, captured_stdout.getvalue())
        self.assertNotIn(self.SENTINEL, captured_stderr.getvalue())

    def test_translator_offline_dict_with_closed_db_does_not_leak_sentinel_and_flags_save_failure(self):
        """Çevrimdışı sözlük yolunda kapalı DB'ye kayıt yapılamazsa sentinel sızmamalı ve db_saved=False olmalıdır."""
        import io
        import sys
        from app.translator import TranslationEngine

        translator = TranslationEngine(db=self.db)
        fake_offline = {"german": self.SENTINEL, "turkish": "çevrimdışı_anlam"}

        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()

        with patch("app.translator.get_offline_analysis", return_value=fake_offline):
            with patch("sys.stdout", captured_stdout), patch("sys.stderr", captured_stderr):
                res = translator.translate_and_analyze(self.SENTINEL)

        self.assertFalse(res.get("db_saved", True), "Çevrimdışı yolda DB yazılamadığında db_saved False olmalıdır")
        self.assertNotIn(self.SENTINEL, captured_stdout.getvalue())
        self.assertNotIn(self.SENTINEL, captured_stderr.getvalue())

    def test_translator_gemini_direct_with_closed_db_does_not_leak_sentinel_and_flags_save_failure(self):
        """Doğrudan Gemini modunda kapalı DB'ye kayıt yapılamazsa sentinel sızmamalı ve db_saved=False olmalıdır."""
        import io
        import sys
        from app.translator import TranslationEngine

        mock_gemini = MagicMock()
        mock_gemini.is_configured.return_value = True
        mock_gemini.translate_and_analyze.return_value = {"german": self.SENTINEL, "turkish": "gemini_anlam"}

        translator = TranslationEngine(db=self.db, use_gemini_direct=True)
        translator.gemini_service = mock_gemini

        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()

        with patch("sys.stdout", captured_stdout), patch("sys.stderr", captured_stderr):
            res = translator.translate_and_analyze(self.SENTINEL)

        self.assertFalse(res.get("db_saved", True), "Gemini direct yolunda DB yazılamadığında db_saved False olmalıdır")
        self.assertNotIn(self.SENTINEL, captured_stdout.getvalue())
        self.assertNotIn(self.SENTINEL, captured_stderr.getvalue())

    def test_translator_online_lookup_with_closed_db_does_not_leak_sentinel_and_flags_save_failure(self):
        """Çevrimiçi arama yolunda kapalı DB'ye kayıt yapılamazsa sentinel sızmamalı ve db_saved=False olmalıdır."""
        import io
        import sys
        from app.translator import TranslationEngine

        translator = TranslationEngine(db=self.db)
        fake_online = {"german": self.SENTINEL, "turkish": "online_anlam", "original": self.SENTINEL, "dict_entries": []}

        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()

        with patch.object(translator, "_lookup_word", return_value=fake_online):
            with patch("sys.stdout", captured_stdout), patch("sys.stderr", captured_stderr):
                res = translator.translate_and_analyze(self.SENTINEL)

        self.assertFalse(res.get("db_saved", True), "Çevrimiçi yolda DB yazılamadığında db_saved False olmalıdır")
        self.assertNotIn(self.SENTINEL, captured_stdout.getvalue())
        self.assertNotIn(self.SENTINEL, captured_stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
