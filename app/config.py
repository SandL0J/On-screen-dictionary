"""
Uygulama Yapılandırma ve Ayar Yönetimi Modülü
"""
import json
import os
from pathlib import Path

DEFAULT_CONFIG = {
    "clipboard_auto_lookup": True,
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
    "gemini_model": "gemini-3.1-flash-lite",
    "first_run_completed": False,
    "tesseract_cmd": "",
    "ocr_engine_preference": "auto",
}

from app.paths import get_config_path

CONFIG_FILE = get_config_path()


def load_config() -> dict:
    """Mevcut yapılandırmayı yükler, yoksa varsayılanı oluşturur."""
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Eksik alanları varsayılanlarla doldur
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            # Google tarafından kaldırılan eski modelleri güncel Flash modeline yükselt
            if merged.get("gemini_model") in ("gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-flash-8b"):
                merged["gemini_model"] = "gemini-3.1-flash-lite"
            # Dinleme özelliği kaldırıldığı için eski dosyalardaki sound_enabled anahtarını temizle
            merged.pop("sound_enabled", None)
            return merged
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> bool:
    """Yapılandırmayı JSON dosyasına kaydeder."""
    global CONFIG_FILE
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Ayar kaydetme hatası: {e}")
        from app.paths import CODE_DIR
        if CONFIG_FILE.parent != CODE_DIR:
            fallback_file = CODE_DIR / "config.json"
            try:
                with open(fallback_file, "w", encoding="utf-8") as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)
                CONFIG_FILE = fallback_file
                return True
            except Exception:
                pass
        return False
