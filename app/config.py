"""
Uygulama Yapılandırma ve Ayar Yönetimi Modülü
"""
import json
import os
from pathlib import Path
from typing import Optional, Union
import uuid

from app.security import is_dpapi_protected, protect_key, unprotect_key, mask_api_key

DEFAULT_CONFIG = {
    "clipboard_auto_lookup": False,  # Gizlilik gereği yeni kurulumlarda varsayılan KAPALI
    "always_on_top": True,
    "target_language": "tr",
    "theme": "dark",
    "auto_hide_seconds": 12,
    "gemini_api_key": "",
    "font_size": 11,
    "history_limit": 100,
    "window_pos_x": 100,
    "window_pos_y": 100,
    "hotkey_ocr": "tab+space",
    "hotkey_overlay": "alt+h",
    "hotkey_clipboard": "alt+c",
    "hotkey_hover": "alt+v",
    "hover_enabled": True,
    "hover_delay_ms": 300,
    "hover_trigger_mode": "mouse_side",
    "hover_auto_hide_seconds": 5,
    "use_gemini_direct": False,
    "gemini_model": "gemini-3.5-flash-lite",
    "first_run_completed": False,
    "tesseract_cmd": "",
    "ocr_engine_preference": "auto",
    "disable_security_filter": False,
    "hide_security_warnings": False,
    "hide_translation_warnings": False,
    "show_translation_warnings": True,
    "lemma_lookup_enabled": True,
    "grammar_analysis_enabled": True,
}

from app.paths import get_config_path

CONFIG_FILE = get_config_path()

DEPRECATED_GEMINI_MODELS = {
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash-lite-preview",
    "gemini-2.0-pro",
    "gemini-2.0-pro-exp",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    "gemini-1.5-pro",
    "gemini-pro",
}

VALID_GEMINI_MODELS = {
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
}


def _atomic_write_json(target_file: Path, data: dict) -> None:
    """
    JSON verisini hedef dosyaya atomik olarak yazar.
    1. Hedef dosya ile aynı dizinde benzersiz bir geçici dosya (.tmp) oluşturulur.
    2. JSON verisi yazılır, flush ve fsync edilerek diske yazılması garanti edilir.
    3. Dosya tanıtıcısı kapatıldıktan sonra os.replace ile hedef dosya atomik olarak güncellenir.
    4. Herhangi bir hata durumunda geçici dosya silinir; mevcut hedef dosya bozulmadan kalır.
    """
    target_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file = target_file.with_name(f"{target_file.stem}_{os.getpid()}_{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_file, target_file)
    except Exception as e:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass
        raise e


def load_config(config_path: Optional[Union[str, Path]] = None) -> dict:
    """Mevcut yapılandırmayı yükler, yoksa varsayılanı oluşturur."""
    target_file = Path(config_path) if config_path else CONFIG_FILE
    if not target_file.exists():
        save_config(DEFAULT_CONFIG, config_path=target_file)
        return DEFAULT_CONFIG.copy()
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Eksik alanları varsayılanlarla doldur; mevcut kullanıcı tercihlerini koru
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)

            # Gemini API Anahtarının Güvenli Çözümü:
            # 1. 'gemini_api_key' veya 'gemini_api_key_encrypted' dpapi: ile başlıyorsa çöz.
            # 2. Eski düz metin anahtarlar bellekte olduğu gibi tutulur ve diske otomatik DPAPI olarak yükseltilir.
            # 3. Çözme hatasında kullanıcı anahtarı boş ile ezilmez; hata güvenli biçimde loglanır.
            raw_key = merged.get("gemini_api_key") or ""
            if not raw_key and data.get("gemini_api_key_encrypted"):
                enc_val = data.get("gemini_api_key_encrypted")
                if isinstance(enc_val, str) and enc_val.strip():
                    raw_key = enc_val if is_dpapi_protected(enc_val) else f"dpapi:{enc_val}"

            if raw_key and is_dpapi_protected(raw_key):
                try:
                    decrypted_key = unprotect_key(raw_key)
                    merged["gemini_api_key"] = decrypted_key
                except Exception as e:
                    print(f"[Güvenlik UYARI] Gemini API anahtarı DPAPI ile çözülemedi: {e}. Mevcut şifreli kayıt korunuyor.")
                    # DPAPI çözme başarısızsa çalışma zamanı API anahtarı boş bırakılır (servislere şifreli metin gitmez)
                    merged["gemini_api_key"] = ""
                    # Şifreli ham değer yalnızca config kaydında eski kaydı korumak için dahili alanda saklanır
                    merged["_gemini_api_key_encrypted_raw"] = raw_key
                    merged["_gemini_api_key_error"] = f"DPAPI çözme hatası: {e}"
            else:
                merged["gemini_api_key"] = raw_key

            # Model normalizasyonu:
            # 1. gemini-flash-latest alias'ı Google tarafından Gemini 3.5 Flash'a yönlendirildiğinden
            #    kararlı gemini-3.5-flash kimliğine dönüştürülür.
            # 2. Kapatılmış modeller (gemini-2.0, 1.5 vb.) güncel kararlı gemini-3.5-flash-lite'a taşınır.
            # 3. Resmi belgelerde geçerli olan (3.1-flash-lite, 3.8-flash, 3.5-flash, 2.5-flash) tercihler korunur.
            current_model = merged.get("gemini_model")
            if current_model == "gemini-flash-latest":
                merged["gemini_model"] = "gemini-3.5-flash"
            elif current_model in DEPRECATED_GEMINI_MODELS or current_model not in VALID_GEMINI_MODELS:
                merged["gemini_model"] = "gemini-3.5-flash-lite"
            # Dinleme özelliği kaldırıldığı için eski dosyalardaki sound_enabled anahtarını temizle
            merged.pop("sound_enabled", None)

            # Güvenlik ve Uyumluluk:
            # Diskte düz metin anahtar veya eski 'gemini_api_key_encrypted' alanı kalmışsa
            # ilk yüklemede diski güvenli DPAPI formatına otomatik olarak yükselt
            if target_file.exists() and ((raw_key and not is_dpapi_protected(raw_key)) or "gemini_api_key_encrypted" in data):
                try:
                    save_config(merged, config_path=target_file)
                except Exception:
                    pass

            return merged
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(config: dict, config_path: Optional[Union[str, Path]] = None) -> bool:
    """
    Yapılandırmayı JSON dosyasına atomik ve güvenli biçimde kaydeder.
    Gemini API anahtarı Windows DPAPI ile şifrelenir; diske asla düz metin yazılmaz.
    """
    global CONFIG_FILE
    target_file = Path(config_path) if config_path else CONFIG_FILE
    to_save = config.copy()
    to_save.pop("gemini_api_key_encrypted", None)

    # Dahili metadata alanlarını kontrol et
    raw_unresolved = to_save.get("_gemini_api_key_encrypted_raw", "")
    explicit_cleared = to_save.get("_gemini_api_key_cleared", False)

    # API Anahtarını DPAPI ile koru
    key = to_save.get("gemini_api_key", "")
    if key:
        if is_dpapi_protected(key):
            to_save["gemini_api_key"] = key
        else:
            try:
                to_save["gemini_api_key"] = protect_key(key)
            except Exception as e:
                print(f"[Güvenlik UYARI] Gemini API anahtarı DPAPI ile şifrelenemedi: {e}. Config kaydedilemedi.")
                return False
    elif raw_unresolved and not explicit_cleared:
        # Çözülemeyen mevcut şifreli anahtar var ve kullanıcı açıkça silmedi:
        # Kullanıcı başka ayarları kaydedip anahtara dokunmadıysa mevcut şifreli değer aynen korunur.
        to_save["gemini_api_key"] = raw_unresolved
    else:
        to_save["gemini_api_key"] = ""

    # Dahili alanların ('_' ile başlayan) diske JSON olarak yazılmasını engelle
    clean_save = {k: v for k, v in to_save.items() if not k.startswith("_")}

    try:
        _atomic_write_json(target_file, clean_save)
        return True
    except Exception as e:
        print(f"[Config Kaydetme Hatası] Hedef dizine yazılamadı ({target_file}): {e}")
        from app.paths import CODE_DIR
        if target_file.parent != CODE_DIR:
            fallback_file = CODE_DIR / "config.json"
            try:
                _atomic_write_json(fallback_file, clean_save)
                CONFIG_FILE = fallback_file
                return True
            except Exception as fb_err:
                print(f"[Config Kaydetme Hatası] Fallback dizinine de yazılamadı: {fb_err}")
        return False
