"""
Birim testleri: Sprint 2A - Güvenli ve Dayanıklı Yapılandırma Saklama
- Gemini API anahtarının Windows DPAPI ile korunması
- Düz metin eski config dosyalarının şifreli formata kayıpsız taşınması
- Servislerin kullanması için bellekte düz metin çözülmesi
- Şifreleme/çözme hatalarında var olan ayarın silinmemesi/boş değerle ezilmemesi
- save_config atomik yazma (geçici dosya + flush + fsync + os.replace) ve hata temizliği
"""
import base64
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app.config import DEFAULT_CONFIG, load_config, save_config, _atomic_write_json
from app.security import (
    DPAPI_PREFIX,
    is_dpapi_protected,
    protect_key,
    unprotect_key,
    mask_api_key,
    protect_data,
    unprotect_data,
    IS_WINDOWS,
)


class TestSecurityDPAPIModule(unittest.TestCase):
    """app/security.py modülü birim testleri."""

    def test_mask_api_key(self):
        """API anahtarı maskeleme fonksiyonu hassas bilgileri gizlemelidir."""
        self.assertEqual(mask_api_key(""), "[BOŞ]")
        self.assertEqual(mask_api_key(None), "[BOŞ]")
        self.assertEqual(mask_api_key("dpapi:AQAAANCMnd8BFd..."), "[DPAPI İLE KORUNUYOR]")
        self.assertEqual(mask_api_key("12345"), "[GİZLENDİ]")
        self.assertEqual(mask_api_key("AIzaSyLongSecretKey12345"), "AIza...2345")

    def test_is_dpapi_protected(self):
        """is_dpapi_protected yalnızca 'dpapi:' ile başlayan dizgeleri doğrulamalıdır."""
        self.assertTrue(is_dpapi_protected("dpapi:AQAAANCM..."))
        self.assertFalse(is_dpapi_protected("AIzaSyPlainKey"))
        self.assertFalse(is_dpapi_protected(""))
        self.assertFalse(is_dpapi_protected(None))

    def test_protect_and_unprotect_empty_values(self):
        """Boş değerler boş olarak dönmeli, hata üretmemelidir."""
        self.assertEqual(protect_key(""), "")
        self.assertEqual(unprotect_key(""), "")
        self.assertEqual(protect_key(None), "")
        self.assertEqual(unprotect_key(None), "")

    def test_protect_key_idempotent_for_already_protected(self):
        """Zaten dpapi: ile başlayan anahtar tekrar şifrelenmemelidir."""
        already_enc = "dpapi:AQAAANCMnd8..."
        self.assertEqual(protect_key(already_enc), already_enc)

    def test_unprotect_key_passthrough_for_plain_text(self):
        """Şifreli olmayan düz metin anahtar çözülmeye çalışılmadan aynen dönmelidir."""
        plain = "AIzaSyLegacyKey_12345"
        self.assertEqual(unprotect_key(plain), plain)

    @unittest.skipUnless(IS_WINDOWS, "Canlı DPAPI testi yalnızca Windows üzerinde çalışır")
    def test_live_windows_dpapi_round_trip(self):
        """Canlı Windows DPAPI CryptProtectData ve CryptUnprotectData sentetik anahtarla test edilir."""
        dummy_secret = "AIzaSySyntheticTestSecret_1234567890"
        protected = protect_key(dummy_secret)
        self.assertTrue(protected.startswith(DPAPI_PREFIX))
        self.assertNotIn(dummy_secret, protected)

        unprotected = unprotect_key(protected)
        self.assertEqual(unprotected, dummy_secret)

    def test_unprotect_corrupt_base64_raises_value_error(self):
        """Bozuk base64 içeren dpapi değeri unprotect_key içinde kontrollü hata fırlatmalıdır."""
        with self.assertRaises(ValueError):
            unprotect_key("dpapi:!!!NOT_BASE64!!!")

    @patch("app.security.unprotect_data", side_effect=OSError("Windows DPAPI decryption failed"))
    def test_unprotect_dpapi_failure_raises_os_error(self, mock_unprotect):
        """DPAPI çözme hatası alındığında OSError yükseltilmelidir."""
        valid_b64 = base64.b64encode(b"dummy_cipher").decode("ascii")
        with self.assertRaises(OSError):
            unprotect_key(f"dpapi:{valid_b64}")


class TestConfigAtomicSaveAndResilience(unittest.TestCase):
    """save_config atomik yazma ve hata anında dosya bütünlüğü testleri."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_atomic_write_creates_valid_json_file(self):
        """_atomic_write_json hedef dosyayı atomik olarak oluşturmalı ve geride .tmp bırakmamalıdır."""
        data = {"app": "EkranSozlugu", "version": "0.9.0"}
        _atomic_write_json(self.config_path, data)

        self.assertTrue(self.config_path.exists())
        loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(loaded, data)

        # Hedef dizinde hiçbir geçici .tmp dosyası kalmamalı
        tmp_files = list(self.config_path.parent.glob("*.tmp"))
        self.assertEqual(tmp_files, [])

    def test_atomic_write_failure_preserves_previous_file(self):
        """Yazma sırasında hata oluşursa önceki config bozulmamalı ve geçici dosya silinmelidir."""
        initial_data = {"version": "1.0", "status": "stable"}
        _atomic_write_json(self.config_path, initial_data)
        self.assertTrue(self.config_path.exists())

        # İkinci yazmada flush/fsync veya json yazımında hata simüle et
        corrupted_data = {"version": "2.0", "status": "corrupt"}
        with patch("os.replace", side_effect=PermissionError("Simüle edilmiş dosya kilit hatası")):
            with self.assertRaises(PermissionError):
                _atomic_write_json(self.config_path, corrupted_data)

        # Asıl dosya bozulmamış olmalı (ilk veriyi korumalı)
        loaded = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(loaded, initial_data)

        # Geçici .tmp dosyası temizlenmiş olmalı
        tmp_files = list(self.config_path.parent.glob("*.tmp"))
        self.assertEqual(tmp_files, [])

    def test_save_config_does_not_mutate_caller_dict(self):
        """save_config çağıranın bellek içi dict nesnesindeki plain-text anahtarı ezmemelidir."""
        cfg = {"gemini_api_key": "AIzaSyCallerPlainKey_12345", "theme": "dark"}
        saved = save_config(cfg, config_path=self.config_path)
        self.assertTrue(saved)

        # Çağıranın belleğindeki sözlük düz metin kalmalı (servislerin kullanabilmesi için)
        self.assertEqual(cfg["gemini_api_key"], "AIzaSyCallerPlainKey_12345")

        # Diskteki dosya ise DPAPI korumalı olmalı ve düz metin anahtar içermemelidir
        disk_raw = self.config_path.read_text(encoding="utf-8")
        self.assertNotIn("AIzaSyCallerPlainKey_12345", disk_raw)
        disk_json = json.loads(disk_raw)
        self.assertTrue(disk_json["gemini_api_key"].startswith(DPAPI_PREFIX))


class TestConfigDPAPIMigrationAndSafety(unittest.TestCase):
    """Legacy plain-text config migrasyonu ve DPAPI hata toleransı testleri."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_legacy_plain_text_config_loads_and_migrates_on_save(self):
        """Eski düz metin config yüklenebilmeli ve save_config ile DPAPI korumalı biçime taşınmalıdır."""
        legacy_key = "AIzaSyLegacyKey_9876543210"
        legacy_data = {
            "gemini_api_key": legacy_key,
            "theme": "dark",
            "gemini_model": "gemini-3.5-flash-lite"
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(legacy_data, f)

        # 1. Yükleme: Düz metin anahtar bellekte normal biçimde çözülmüş olarak gelmeli
        loaded = load_config(self.config_path)
        self.assertEqual(loaded["gemini_api_key"], legacy_key)

        # 2. Kaydetme: Başarılı bir save_config çağrısıyla dosya DPAPI formatına taşınmalı
        ok = save_config(loaded, config_path=self.config_path)
        self.assertTrue(ok)

        # 3. Diskteki dosyayı ham metin olarak kontrol et: Düz metin anahtar ASLA yer almamalıdır
        raw_disk_content = self.config_path.read_text(encoding="utf-8")
        self.assertNotIn(legacy_key, raw_disk_content)

        disk_json = json.loads(raw_disk_content)
        self.assertTrue(disk_json["gemini_api_key"].startswith(DPAPI_PREFIX))

        # 4. Yeniden yükleme: Şifreli dosya belleğe tekrar düz metin olarak çözülmeli
        reloaded = load_config(self.config_path)
        self.assertEqual(reloaded["gemini_api_key"], legacy_key)

    def test_dpapi_decryption_failure_leaves_runtime_key_empty_and_error_visible(self):
        """DPAPI çözme hatasında runtime API anahtarı boş kalmalı ve dahili hata alanı doldurulmalıdır."""
        bad_protected_value = "dpapi:INVALID_OR_ANOTHER_MACHINE_KEY_BLOB"
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({"gemini_api_key": bad_protected_value}, f)

        with patch("app.config.unprotect_key", side_effect=Exception("Anahtar bu cihaza ait değil")):
            loaded = load_config(self.config_path)

            # 1. Çalışma zamanı API anahtarı BOŞ olmalıdır (servislere şifreli metin gitmez)
            self.assertEqual(loaded["gemini_api_key"], "")

            # 2. Şifreli ham değer yalnızca dahili alanda korunmalıdır
            self.assertEqual(loaded.get("_gemini_api_key_encrypted_raw"), bad_protected_value)
            self.assertIn("DPAPI çözme hatası", loaded.get("_gemini_api_key_error", ""))

    def test_save_other_settings_preserves_unresolved_key_without_leaking_internal_fields(self):
        """Kullanıcı başka ayarları kaydedince şifreli orijinal değer korunmalı, dahili metadata JSON'a sızmamalıdır."""
        bad_protected_value = "dpapi:PRESERVE_THIS_CIPHERTEXT"
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({"gemini_api_key": bad_protected_value, "theme": "dark"}, f)

        with patch("app.config.unprotect_key", side_effect=Exception("Çözülemedi")):
            loaded = load_config(self.config_path)

        # Kullanıcı yalnızca temayı ve süreyi değiştiriyor, API anahtarına dokunmuyor
        loaded["theme"] = "light"
        loaded["auto_hide_seconds"] = 25
        saved = save_config(loaded, config_path=self.config_path)
        self.assertTrue(saved)

        # Diskteki JSON içeriğini kontrol et
        disk_raw = self.config_path.read_text(encoding="utf-8")
        disk_json = json.loads(disk_raw)

        # 1. Orijinal şifreli değer diskte eksiksiz korunmalıdır
        self.assertEqual(disk_json["gemini_api_key"], bad_protected_value)
        self.assertEqual(disk_json["theme"], "light")
        self.assertEqual(disk_json["auto_hide_seconds"], 25)

        # 2. Hiçbir dahili alan ('_' ile başlayan) diske yazılmamalıdır
        for key in disk_json.keys():
            self.assertFalse(key.startswith("_"), f"Dahili alan JSON'a sızdı: {key}")

    def test_entering_new_key_overwrites_unresolved_key_and_resolves_on_reload(self):
        """Kullanıcı yeni anahtar girdiğinde eski şifreli değerin üzerine yazılmalı ve reload ile çözülmelidir."""
        old_bad_value = "dpapi:OLD_BROKEN_BLOB"
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({"gemini_api_key": old_bad_value}, f)

        with patch("app.config.unprotect_key", side_effect=Exception("Eski anahtar çözülemedi")):
            loaded = load_config(self.config_path)

        self.assertEqual(loaded["gemini_api_key"], "")

        # Kullanıcı yeni geçerli bir anahtar giriyor
        new_plain_key = "AIzaSyNewValidKey_9876543210"
        loaded["gemini_api_key"] = new_plain_key
        save_config(loaded, config_path=self.config_path)

        # Diskteki veri artık eski bozuk değer değil, yeni DPAPI ile şifrelenmiş değer olmalı
        disk_json = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertNotEqual(disk_json["gemini_api_key"], old_bad_value)
        self.assertTrue(disk_json["gemini_api_key"].startswith(DPAPI_PREFIX))
        self.assertNotIn(new_plain_key, self.config_path.read_text(encoding="utf-8"))

        # Yeniden yüklendiğinde yeni anahtar çözülmelidir
        reloaded = load_config(self.config_path)
        self.assertEqual(reloaded["gemini_api_key"], new_plain_key)
        self.assertNotIn("_gemini_api_key_encrypted_raw", reloaded)

    def test_explicitly_clearing_key_does_not_restore_old_encrypted_key(self):
        """Anahtar açıkça ve kasıtlı olarak silindiğinde eski şifreli değer diske geri yazılmamalıdır."""
        old_protected = "dpapi:DO_NOT_RESTORE_ON_EXPLICIT_CLEAR"
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({"gemini_api_key": old_protected}, f)

        with patch("app.config.unprotect_key", side_effect=Exception("Çözülemedi")):
            loaded = load_config(self.config_path)

        # Kullanıcı anahtarı açıkça siliyor
        loaded["gemini_api_key"] = ""
        loaded["_gemini_api_key_cleared"] = True
        loaded.pop("_gemini_api_key_encrypted_raw", None)
        save_config(loaded, config_path=self.config_path)

        disk_json = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(disk_json["gemini_api_key"], "")

        reloaded = load_config(self.config_path)
        self.assertEqual(reloaded["gemini_api_key"], "")
        self.assertNotIn("_gemini_api_key_encrypted_raw", reloaded)

    def test_decryption_failure_does_not_pass_dpapi_ciphertext_to_service(self):
        """Çözme hatasında TranslationEngine veya GeminiService asla DPAPI metnini anahtar olarak almamalıdır."""
        bad_protected_value = "dpapi:CORRUPT_CIPHERTEXT"
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({"gemini_api_key": bad_protected_value}, f)

        with patch("app.config.unprotect_key", side_effect=Exception("Bozuk veri")):
            cfg = load_config(self.config_path)

        from app.translator import TranslationEngine
        from app.gemini_service import GeminiService

        # 1. TranslationEngine başlatma testi
        mock_db = MagicMock()
        engine = TranslationEngine(gemini_api_key=cfg.get("gemini_api_key", ""), db=mock_db)
        self.assertEqual(engine.gemini_service.api_key, "")
        self.assertNotEqual(engine.gemini_service.api_key, bad_protected_value)

        # 2. GeminiService doğrudan başlatma testi
        gs = GeminiService(api_key=cfg.get("gemini_api_key", ""))
        self.assertEqual(gs.api_key, "")
        self.assertNotEqual(gs.api_key, bad_protected_value)

    def test_settings_window_handles_decryption_error_properly(self):
        """Ayarlar ekranı DPAPI çözme hatasını açıkça bildirmeli ve şifreli metni test/kayıt etmemelidir."""
        import tkinter as tk
        from app.gui.settings_window import SettingsWindow

        root = tk.Tk()
        root.withdraw()
        try:
            bad_raw = "dpapi:FOREIGN_MACHINE_BLOB"
            cfg = {
                "gemini_api_key": "",
                "_gemini_api_key_encrypted_raw": bad_raw,
                "_gemini_api_key_error": "DPAPI hatası",
                "gemini_model": "gemini-3.5-flash-lite",
            }
            sw = SettingsWindow(parent=root, config=cfg, on_settings_changed=MagicMock())

            # 1. Giriş kutusu şifreli metinle DOLMAMALI, boş kalmalıdır
            self.assertEqual(sw.entry_api.get(), "")

            # 2. Durum etiketi 'Kayıtlı anahtar mevcut' YAZMAMALI, hata uyarısı göstermelidir
            status_text = sw.lbl_api_status.cget("text")
            self.assertNotIn("Kayıtlı anahtar mevcut", status_text)
            self.assertIn("çözülemedi", status_text)
            self.assertEqual(sw.lbl_api_status.cget("fg"), "#ef4444")

            # 3. Test Et tıklandığında dış servise istek atmadan önce uyarı vermelidir
            sw._test_gemini_api()
            self.assertIn("çözülemedi", sw.lbl_api_status.cget("text"))

            # 4. Şifreli metin kutucuğa yapıştırılsa bile _test_gemini_api engellemelidir
            sw.entry_api.insert(0, "dpapi:SOME_PASTED_CIPHER")
            sw._test_gemini_api()
            self.assertIn("Şifreli metin doğrudan test edilemez", sw.lbl_api_status.cget("text"))

            # 5. Sil butonuna basıldığında açık silme işaretlenmelidir
            sw._clear_api_key()
            self.assertTrue(sw._explicit_key_cleared)
            self.assertEqual(sw.config.get("gemini_api_key"), "")
            self.assertNotIn("_gemini_api_key_encrypted_raw", sw.config)

            sw.close()
        finally:
            root.destroy()

    def test_save_config_failure_on_dpapi_protect_preserves_old_file(self):
        """DPAPI şifreleme başarısız olursa config boş değerle veya düz metinle ezilmemeli, işlem durdurulmalıdır."""
        original_data = {"gemini_api_key": "dpapi:ORIGINAL_VALID_BLOB", "theme": "dark"}
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(original_data, f)

        # Yeni bir anahtar kaydedilmeye çalışılıyor ancak protect_key hata veriyor
        new_cfg = {"gemini_api_key": "AIzaSyNewUnprotectableKey", "theme": "light"}
        with patch("app.config.protect_key", side_effect=OSError("DPAPI servisi yanıt vermiyor")):
            success = save_config(new_cfg, config_path=self.config_path)
            self.assertFalse(success)

        # Eski dosya bozulmadan ve orijinal verisiyle kalmalıdır
        disk_json = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.assertEqual(disk_json["gemini_api_key"], "dpapi:ORIGINAL_VALID_BLOB")
        self.assertEqual(disk_json["theme"], "dark")

    def test_mocked_dpapi_protect_and_unprotect_flow(self):
        """Farklı platformlar ve izole ortamlar için mocklanmış DPAPI akışı doğrulaması."""
        fake_secret = "AIzaSyMockedSecret_12345"
        fake_cipher = "dpapi:FAKE_MOCKED_BASE64_CIPHER"

        with patch("app.config.protect_key", return_value=fake_cipher) as mock_prot, \
             patch("app.config.unprotect_key", return_value=fake_secret) as mock_unprot:

            cfg = {"gemini_api_key": fake_secret}
            save_config(cfg, config_path=self.config_path)
            mock_prot.assert_called_once_with(fake_secret)

            disk_data = json.loads(self.config_path.read_text(encoding="utf-8"))
            self.assertEqual(disk_data["gemini_api_key"], fake_cipher)

            loaded = load_config(self.config_path)
            mock_unprot.assert_called_once_with(fake_cipher)
            self.assertEqual(loaded["gemini_api_key"], fake_secret)


if __name__ == "__main__":
    unittest.main()
