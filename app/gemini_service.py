"""
Gemini AI Entegrasyon ve Doğrulama Servisi
Google Gemini REST API üzerinden:
1. API anahtarı bağlantı doğrulaması
2. Güncel Flash modelleriyle (gemini-3.5-flash-lite, gemini-3.8-flash, gemini-3.5-flash)
   doğrudan çift yönlü çeviri ve derin dilbilgisi analizi
3. Hızlı açıklama ve artikel kuralı üretimi
sağlar.
"""
import urllib.request
import urllib.error
import urllib.parse
import json
import time
from typing import Tuple, Optional, Dict, Any

from app.security import is_sensitive_clipboard_text, is_dpapi_protected


SUPPORTED_MODELS = [
    ("gemini-3.5-flash-lite", "Gemini 3.5 Flash Lite (Önerilen - Hızlı & Düşük Maliyet)"),
    ("gemini-3.8-flash", "Gemini 3.8 Flash (Kalite Odaklı & Akıllı)"),
    ("gemini-3.5-flash", "Gemini 3.5 Flash (Dengeli Model)"),
    ("gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite (Hafif Model)"),
    ("gemini-2.5-flash", "Gemini 2.5 Flash (Eski / Kısıtlı Model)"),
]

DEFAULT_MODEL = "gemini-3.5-flash-lite"


class GeminiService:
    def __init__(self, api_key: str = "", model: str = DEFAULT_MODEL):
        self.api_key = api_key.strip() if api_key else ""
        self.model = model.strip() if model else DEFAULT_MODEL

    def set_api_key(self, api_key: str):
        self.api_key = api_key.strip() if api_key else ""

    def set_model(self, model: str):
        if model and model.strip():
            self.model = model.strip()

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 10 and not is_dpapi_protected(self.api_key) and not self.api_key.startswith("dpapi:"))

    def _call_gemini_api(self, prompt: str, is_json: bool = False, max_tokens: int = 1000, deadline: Optional[float] = None) -> Optional[str]:
        """
        Gemini REST API'sine x-goog-api-key başlığı ile güvenli istek gönderir.
        Kullanıcının modeli (404 veya 503 gibi) hata verirse bilinen aktif Flash modellerine otomatik yedekleme yapar.
        API anahtarı asla URL'de iletilmez veya loglara yazdırılmaz.
        Uçtan uca zaman bütçesi (deadline) aşımını engeller.
        """
        if not self.is_configured():
            return None

        preferred = self.model if self.model else DEFAULT_MODEL
        candidates = [preferred]
        for m in ("gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"):
            if m not in candidates:
                candidates.append(m)

        payload_dict = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": max_tokens
            }
        }
        if is_json:
            payload_dict["generationConfig"]["responseMimeType"] = "application/json"

        payload = json.dumps(payload_dict).encode("utf-8")

        for model_name in candidates:
            if deadline is not None:
                remaining = deadline - time.monotonic()
                if remaining <= 0.2:
                    break
                per_call_timeout = max(0.2, min(remaining, 3.0))
            else:
                per_call_timeout = 8.0

            # Güvenlik: API anahtarı URL'de taşınmaz, x-goog-api-key HTTP başlığında iletilir
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
            try:
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "ScreenLingo-Assistant/1.0",
                        "x-goog-api-key": self.api_key
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=per_call_timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates_resp = data.get("candidates", [])
                    if candidates_resp:
                        parts = candidates_resp[0].get("content", {}).get("parts", [])
                        if parts:
                            text_out = parts[0].get("text", "").strip()
                            if text_out:
                                if self.model != model_name and model_name in ("gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"):
                                    self.model = model_name
                                return text_out
            except urllib.error.HTTPError as e:
                # 404 (model kaldırılmış) veya 503 (servis yoğun) durumunda bir sonraki aktif modeli dene
                if e.code in (404, 503, 500):
                    continue
                else:
                    # Loglarda veya konsolda API anahtarı ASLA yazdırılmamalıdır
                    print(f"Gemini API HTTP {e.code} hatası ({model_name})")
                    break
            except Exception:
                continue

        return None

    def test_connection(self, key_to_test: Optional[str] = None) -> Tuple[bool, str]:
        """
        Gemini API anahtarının çalışıp çalışmadığını x-goog-api-key başlığı ile test eder.
        Dönüş: (başarılı_mı: bool, durum_mesajı: str)
        """
        api_key = (key_to_test if key_to_test is not None else self.api_key).strip()
        if not api_key:
            return False, "⚠️ Lütfen önce bir Gemini API anahtarı girin."
        if api_key.startswith("dpapi:") or is_dpapi_protected(api_key):
            return False, "❌ Şifreli metin (DPAPI) doğrudan test edilemez."

        # Güvenlik: API anahtarı URL sorgusunda iletilmez
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "ScreenLingo-Assistant/1.0",
                    "Accept": "application/json",
                    "x-goog-api-key": api_key
                }
            )
            with urllib.request.urlopen(req, timeout=7) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = data.get("models", [])
                    return True, f"✅ Gemini API Bağlantısı Başarılı! ({len(models)} model erişilebilir)"
                else:
                    return False, f"⚠️ Beklenmeyen yanıt kodu: {resp.status}"

        except urllib.error.HTTPError as e:
            try:
                err_content = e.read().decode("utf-8")
                err_json = json.loads(err_content)
                err_msg = err_json.get("error", {}).get("message", "")
            except Exception:
                err_msg = ""

            # Güvenlik: Hata mesajında anahtarın sızdırılmasını engelle
            for k in (api_key, self.api_key):
                if k and k in err_msg:
                    err_msg = err_msg.replace(k, "[GİZLENDİ]")

            if e.code in (400, 401):
                return False, "❌ API Anahtarı Geçersiz: Google anahtarı doğrulamadı."
            elif e.code == 403:
                return False, "❌ Erişim Reddedildi: Gemini API etkin değil veya kısıtlanmış."
            elif e.code == 429:
                return False, "⚠️ İstek Limiti (Rate Limit): Lütfen biraz bekleyin."
            else:
                detail = f" ({err_msg})" if err_msg else ""
                return False, f"❌ Google API Hatası (HTTP {e.code}){detail}"

        except urllib.error.URLError:
            return False, "⚠️ Bağlantı Kurulamadı: İnternet bağlantınızı kontrol edin."
        except Exception as e:
            msg = str(e)
            for k in (api_key, self.api_key):
                if k and k in msg:
                    msg = msg.replace(k, "[GİZLENDİ]")
            return False, f"⚠️ Hata: {msg}"

    def translate_and_analyze(self, text: str, deadline: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Metni doğrudan Gemini API'ye sorarak çevirir ve dilbilgisi analizi yapar.
        Mümkün olan en az token tüketen Flash modeli kullanır.
        """
        if not self.is_configured():
            return None

        clean = text.strip()
        if not clean or is_sensitive_clipboard_text(clean):
            return None

        prompt = (
            "Sen uzman bir Almanca-Türkçe sözlük ve çeviri asistanısın.\n"
            "GÖREV: Aşağıdaki Almanca metni veya kelimeyi mutlaka TÜRKÇEYE çevir ve dilbilgisi analizi yap.\n"
            "ÖNEMLİ KURAL: 'turkish' alanı KESİNLİKLE metnin Türkçe çevirisi olmalıdır. Asla Almanca veya boş bırakılamaz!\n"
            "YALNIZCA geçerli ve hatasız tek bir JSON objesi döndür:\n"
            "{\n"
            '  "german": "Almanca orijinal kelime veya cümle (örn: das Buch)",\n'
            '  "turkish": "Metnin TÜRKÇE çevirisi / anlamı (örn: kitap)",\n'
            '  "article": "der veya die veya das ya da boş",\n'
            '  "plural": "Almanca çoğul hali veya boş",\n'
            '  "pos": "isim, fiil, sıfat veya cümle",\n'
            '  "is_sentence": false,\n'
            '  "rule_note": "Varsa 1-2 cümlelik pratik dilbilgisi veya artikel kuralı",\n'
            '  "examples": [{"de": "Ich lese ein Buch.", "tr": "Bir kitap okuyorum."}]\n'
            "}\n"
            f'Almanca Metin: "{clean}"'
        )

        raw_json = self._call_gemini_api(prompt, is_json=True, max_tokens=1000, deadline=deadline)
        if not raw_json:
            return None

        try:
            # Markdown ```json bloklarını temizle
            if raw_json.startswith("```"):
                lines = raw_json.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                raw_json = "\n".join(lines).strip()

            parsed = json.loads(raw_json)
            return self._format_gemini_translation(parsed, clean, self.model)
        except Exception as e:
            print(f"[Gemini Direct JSON Parse Hatası]: {e}")
            return None

    def _format_gemini_translation(self, parsed: dict, original_text: str, model_name: str) -> Optional[Dict[str, Any]]:
        """Gemini JSON çıktısını standart sözlük/çeviri formatına dönüştürür."""
        german = str(parsed.get("german", "")).strip() or original_text
        turkish = str(parsed.get("turkish", "")).strip()

        # Doğrulama: Türkçe anlam boş veya orijinal metinle birebir aynıysa geçersiz say
        if not turkish or turkish.lower() == original_text.lower():
            return None

        article = str(parsed.get("article", "")).strip().lower()
        if article not in ("der", "die", "das"):
            article = ""
        plural = str(parsed.get("plural", "")).strip()
        pos = str(parsed.get("pos", "")).strip()
        is_sentence = bool(parsed.get("is_sentence", False))
        rule_note = str(parsed.get("rule_note", "")).strip()
        raw_examples = parsed.get("examples", [])

        # Artikel eklemesi kontrolü (İsim ise ve başında artikel yoksa)
        if article and not is_sentence and not german.lower().startswith(article):
            german = f"{article} {german}"

        grammar_notes = []
        if rule_note:
            grammar_notes.append({
                "title": "Gemini AI Notu",
                "desc": rule_note,
                "text": rule_note
            })

        dict_entries = []
        if turkish:
            dict_entries.append({
                "pos": pos or ("cümle" if is_sentence else "kelime"),
                "meanings": [turkish]
            })

        formatted_examples = []
        if isinstance(raw_examples, list):
            for ex in raw_examples:
                if isinstance(ex, dict) and "de" in ex and "tr" in ex:
                    formatted_examples.append({
                        "de": str(ex.get("de", "")),
                        "tr": str(ex.get("tr", ""))
                    })

        return {
            "original": original_text,
            "german": german if german else original_text,
            "turkish": turkish,
            "translation": turkish,
            "article": article,
            "plural": plural,
            "pos": pos or ("cümle" if is_sentence else "kelime"),
            "is_sentence": is_sentence,
            "grammar_notes": grammar_notes,
            "dict_entries": dict_entries,
            "examples": formatted_examples,
            "rule_note": rule_note,
            "gemini_explanation": rule_note,
            "direction": "de_to_tr",
            "detected_lang": "de",
            "model_used": model_name,
            "source": "gemini_ai"
        }

    def generate_explanation(self, text: str, source_lang: str = "de", target_lang: str = "tr", deadline: Optional[float] = None) -> Optional[str]:
        """İsteğe bağlı olarak Gemini'den kısa dilbilgisi veya kullanım notu alır."""
        if not self.is_configured():
            return None

        clean = text.strip() if text else ""
        if not clean or is_sensitive_clipboard_text(clean):
            return None

        prompt = (
            f"Almanca ve Türkçe dil asistanısın. Aşağıdaki metni açıkla. "
            f"Kaynak dil: {source_lang}, Hedef dil: {target_lang}.\n"
            f"Metin: '{clean}'\n"
            f"Lütfen en fazla 2-3 cümleyle, varsa artikel kuralı, fiil çekimi veya günlük kullanım ipucu ver."
        )

        return self._call_gemini_api(prompt, is_json=False, max_tokens=500, deadline=deadline)
