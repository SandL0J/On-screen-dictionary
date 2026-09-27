"""
Almanca Sesli Telaffuz / Dinleme Motoru (Devre Dışı / Deprecated)

Kullanıcı tercihi doğrultusunda telaffuz dinleme özelliği uygulamadan tamamen çıkarılmıştır.
Bu modül geriye dönük çağrı ve içe aktarma uyumluluğu için güvenli ve sessiz bir no-op
arayüzü sağlamaktadır. Ağ istekleri, ses indirme ve ses çalma işlemleri tamamen devre dışıdır.
"""
from typing import Optional
from pathlib import Path


class GermanTTSEngine:
    """Kullanımdan kaldırılmış telaffuz motoru yer tutucusu (No-op)."""

    def __init__(self, *args, **kwargs):
        pass

    def download_audio(self, text: str) -> Optional[Path]:
        """Dinleme özelliği kaldırılmıştır; ses indirilmez, None döner."""
        return None

    def play(self, text: str) -> None:
        """Dinleme özelliği kaldırılmıştır; ses çalınmaz."""
        pass
