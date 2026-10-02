"""
Gemini AI Entegrasyon ve Doğrulama Servisi
Google Gemini REST API üzerinden:
1. API anahtarı bağlantı doğrulaması
2. Düşük maliyetli Flash modelleriyle (gemini-1.5-flash, gemini-2.0-flash, gemini-1.5-flash-8b)
   doğrudan çift yönlü çeviri ve derin dilbilgisi analizi
3. Hızlı açıklama ve artikel kuralı üretimi
sağlar.
"""
import urllib.request
import urllib.error
import urllib.parse
import json
from typing import Tuple, Optional, Dict, Any


SUPPORTED_MODELS = [
    ("gemini-3.1-flash-lite", "Gemini 3.1 Flash-Lite (Önerilen - Hızlı & Kararlı)"),
    ("gemini-3.8-flash", "Gemini 3.8 Flash (Yeni Nesil Model)"),
    ("gemini-flash-latest", "Gemini Flash Latest (En Güncel Flash)"),
    ("gemini-1.5-flash", "Gemini 1.5 Flash (Eski Model)"),
]


class GeminiService:
    def __init__(self, api_key: str = "", model: str = "gemini-3.1-flash-lite"):
        self.api_key = api_key.strip() if api_key else ""
        self.model = model.strip() if model else "gemini-3.1-flash-lite"

    def set_api_key(self, api_key: str):
        self.api_key = api_key.strip() if api_key else ""

    def set_model(self, model: str):
        if model and model.strip():
            self.model = model.strip()

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 10)

    def _call_gemini_api(self, prompt: str, is_json: bool = False, max_tokens: int = 1000) -> Optional[str]:
        """
        Gemini REST API'sine istek gönderir.
        Kullanıcının modeli (404 veya 503 gibi) hata verirse bilinen aktif Flash modellerine otomatik yedekleme yapar.
        """
        if not self.is_configured():
            return None

        preferred = self.model if self.model else "gemini-3.1-flash-lite"
        candidates = [preferred]
        for m in ("gemini-3.1-flash-lite", "gemini-3.8-flash", "gemini-flash-latest"):
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
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"
            try:
                req = urllib.request.Request(
                    url,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "ScreenLingo-Assistant/1.0"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates_resp = data.get("candidates", [])
                    if candidates_resp:
                        parts = candidates_resp[0].get("content", {}).get("parts", [])
                        if parts:
                            text_out = parts[0].get("text", "").strip()
                            if text_out:
                                if self.model != model_name and model_name in ("gemini-3.1-flash-lite", "gemini-3.8-flash"):
                                    self.model = model_name
                                return text_out
            except urllib.error.HTTPError as e:
                # 404 (model kaldırılmış) veya 503 (servis yoğun) durumunda bir sonraki aktif modeli dene
                if e.code in (404, 503, 500):
                    continue
                else:
                    print(f"Gemini API HTTP {e.code} hatası ({model_name}): {e}")
                    break
            except Exception:
                continue

        return None

    def test_connection(self, key_to_test: Optional[str] = None) -> Tuple[bool, str]:
        """
        Gemini API anahtarının çalışıp çalışmadığını test eder.
        Dönüş: (başarılı_mı: bool, durum_mesajı: str)
        """
        api_key = (key_to_test if key_to_test is not None else self.api_key).strip()
        if not api_key:
            return False, "⚠️ Lütfen önce bir Gemini API anahtarı girin."

        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "ScreenLingo-Assistant/1.0",
                    "Accept": "application/json"
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

            if e.code in (400, 401):
                return False, "❌ API Anahtarı Geçersiz: Google anahtarı doğrulamadı."
            elif e.code == 403:
                return False, "❌ Erişim Reddedildi: Gemini API etkin değil veya kısıtlanmış."
            elif e.code == 429:
                return False, "⚠️ İstek Limiti (Rate Limit): Lütfen biraz bekleyin."
            else:
                detail = f" ({err_msg})" if err_msg else ""
                return False, f"❌ Google API Hatası (HTTP {e.code}){detail}"

        except urllib.error.URLError as e:
            return False, f"⚠️ Bağlantı Kurulamadı: İnternet bağlantınızı kontrol edin. ({e.reason})"
        except Exception as e:
            return False, f"⚠️ Hata: {str(e)}"

    def translate_and_analyze(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Metni doğrudan Gemini API'ye sorarak çevirir ve dilbilgisi analizi yapar.
        Mümkün olan en az token tüketen Flash modeli kullanır.
        """
        if not self.is_configured():
            return None

        clean = text.strip()
        if not clean:
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

        raw_json = self._call_gemini_api(prompt, is_json=True, max_tokens=1000)
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

    def generate_explanation(self, text: str, source_lang: str = "de", target_lang: str = "tr") -> Optional[str]:
        """İsteğe bağlı olarak Gemini'den kısa dilbilgisi veya kullanım notu alır."""
        if not self.is_configured():
            return None

        prompt = (
            f"Almanca ve Türkçe dil asistanısın. Aşağıdaki metni açıkla. "
            f"Kaynak dil: {source_lang}, Hedef dil: {target_lang}.\n"
            f"Metin: '{text}'\n"
            f"Lütfen en fazla 2-3 cümleyle, varsa artikel kuralı, fiil çekimi veya günlük kullanım ipucu ver."
        )

        return self._call_gemini_api(prompt, is_json=False, max_tokens=500)
