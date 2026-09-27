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
    "use_gemini_direct": False,
    "gemini_model": "gemini-1.5-flash",
}

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"


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
            # Dinleme özelliği kaldırıldığı için eski dosyalardaki sound_enabled anahtarını temizle
            merged.pop("sound_enabled", None)
            return merged
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> bool:
    """Yapılandırmayı JSON dosyasına kaydeder."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Ayar kaydetme hatası: {e}")
        return False
