"""
Çeviri ve Sözlük Motoru (Translator & Dictionary Engine)
Çift Yönlü Çeviri (Almanca <-> Türkçe):
1. Otomatik Dil Tespiti (Türkçe ise Almancaya, Almanca ise Türkçeye)
2. Yerel Veritabanı ve Önbellek (Offline, 0ms)
3. Hızlı Çevrimiçi Çeviri API'si (Google Translate gtx)
4. Almanca Wiktionary Dilbilgisi Ayrıştırıcısı (Artikel, Çoğul ve Detaylar)
5. Gramer Kuralı Tahmincisi (-ung, -heit, Komposita vb.)
6. Entegre Google Gemini AI Servisi ve Bağlantı Doğrulayıcısı
"""
import urllib.request
import urllib.parse
import json
import re
from typing import Dict, Any, Optional

from app.database import Database
from app.german_analyzer import (
    clean_text, is_single_word, extract_base_word, predict_gender_by_rules,
    analyze_sentence_grammar, get_offline_analysis, get_offline_reverse_analysis,
    ARTICLE_COLORS, COMMON_VOCABULARY
)
from app.gemini_service import GeminiService


class TranslationEngine:
    def __init__(
        self,
        db: Optional[Database] = None,
        gemini_api_key: str = "",
        use_gemini_direct: bool = False,
        gemini_model: str = "gemini-1.5-flash"
    ):
        self.db = db or Database()
        self.gemini_service = GeminiService(gemini_api_key, model=gemini_model)
        self.use_gemini_direct = use_gemini_direct

    def set_gemini_key(self, key: str):
        self.gemini_service.set_api_key(key)

    def set_gemini_options(self, use_direct: bool, model: str = "gemini-1.5-flash"):
        self.use_gemini_direct = use_direct
        self.gemini_service.set_model(model)

    def translate_and_analyze(self, text: str) -> Dict[str, Any]:
        """
        Metinleri ve kelimeleri analiz eder ve SADECE TÜRKÇEYE çevirir.
        Almanca artikel (der/die/das), çoğul ve dilbilgisi kurallarını ekler.
        """
        clean = clean_text(text)
        if not clean:
            return {"error": "Boş metin"}

        # 1. Önce Önbelleğe (Cache) Bak (Token tasarrufu ve 0ms yanıt için)
        cached = self.db.get_cache(clean)
        if cached:
            tr_val = (cached.get("turkish") or cached.get("translation") or "").strip()
            # Önbellekteki Türkçe çeviri metnin orijinaliyle aynı değilse kullan
            if tr_val and tr_val.lower() != clean.lower():
                self.db.add_history(clean, cached)
                cached["from_cache"] = True
                return cached

        # 2. Doğrudan Gemini AI Seçeneği Aktifse (En ekonomik Flash model ile sor)
        if self.use_gemini_direct and self.gemini_service.is_configured():
            try:
                gemini_res = self.gemini_service.translate_and_analyze(clean)
                if gemini_res and "error" not in gemini_res:
                    tr_text = (gemini_res.get("turkish") or "").strip()
                    if tr_text and tr_text.lower() != clean.lower():
                        self.db.set_cache(clean, gemini_res)
                        self.db.add_history(clean, gemini_res)
                        return gemini_res
            except Exception as e:
                print(f"[Gemini Direct Error] Standart motora geçiliyor: {e}")

        # 3. Tek kelimeler için kontrol
        is_word = is_single_word(clean)
        if is_word:
            # 3a. Çevrimdışı Almanca Sözlük (0ms)
            offline_de = get_offline_analysis(clean)
            if offline_de:
                offline_de["direction"] = "de_to_tr"
                offline_de["translation"] = offline_de["turkish"]
                self.db.set_cache(clean, offline_de)
                self.db.add_history(clean, offline_de)
                return offline_de

            # 3b. Çevrimiçi Detaylı Kelime Çevirisi (Wiktionary + Google Translate)
            result = self._lookup_word(clean)
        else:
            # 4. Cümleler için Çeviri (Google Translate ile Kesin Türkçe: sl="auto", tl="tr")
            result = self._translate_sentence(clean)

        # 5. Gemini AI Ek Açıklaması (Yapılandırılmışsa ve doğrudan mod kapalıysa)
        if result and "error" not in result and self.gemini_service.is_configured():
            try:
                gemini_note = self.gemini_service.generate_explanation(
                    clean,
                    source_lang="de",
                    target_lang="tr"
                )
                if gemini_note:
                    result["gemini_explanation"] = gemini_note
                    if not result.get("rule_note"):
                        result["rule_note"] = gemini_note
            except Exception:
                pass

        # 6. Sonucu önbelleğe ve geçmişe kaydet
        if result and "error" not in result:
            self.db.set_cache(clean, result)
            self.db.add_history(clean, result)

        return result

    def _translate_sentence(self, text: str) -> Dict[str, Any]:
        """Cümleyi Google Translate üzerinden Türkçeye çevirir ve dilbilgisi kurallarını ekler."""
        try:
            gt_data = self._translate_via_gt(text, sl="auto", tl="tr")
            turkish_meaning = gt_data["translated_text"]
        except Exception as e:
            return {"error": f"Çeviri hatası: {e}"}

        grammar_notes = analyze_sentence_grammar(text)
        return {
            "source": "sentence_translator",
            "direction": "de_to_tr",
            "german": text,
            "turkish": turkish_meaning,
            "original": text,
            "translation": turkish_meaning,
            "is_sentence": True,
            "grammar_notes": grammar_notes
        }

    def _translate_via_gt(self, text: str, sl: str = "auto", tl: str = "tr") -> Dict[str, Any]:
        """Google Translate gtx API üzerinden hızlı çeviri ve sözlük bilgisi çeker."""
        url = (
            f"https://translate.googleapis.com/translate_a/single?"
            f"client=gtx&sl={sl}&tl={tl}&dt=t&dt=bd&dt=rm&q={urllib.parse.quote(text)}"
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        # Cümle veya ana çeviri
        translated_text = "".join([item[0] for item in data[0] if item[0]])
        detected_lang = data[2] if len(data) > 2 and data[2] else (sl if sl != "auto" else "de")

        # Detaylı sözlük karşılıkları (kelime ise)
        dict_entries = []
        if len(data) > 1 and data[1]:
            for pos in data[1]:
                pos_name = pos[0]
                meanings = pos[1]
                dict_entries.append({
                    "pos": self._map_pos_to_turkish(pos_name),
                    "meanings": meanings[:6]
                })

        return {
            "translated_text": translated_text,
            "detected_lang": detected_lang,
            "dict_entries": dict_entries
        }

    def _fetch_wiktionary_info(self, word: str) -> Dict[str, str]:
        """Almanca Wiktionary üzerinden artikel ve çoğul bilgisini ayrıştırır."""
        info = {"article": "", "plural": "", "pos": ""}
        if not word or not word.strip():
            return info

        clean_w = word.strip().capitalize()
        url = (
            f"https://de.wiktionary.org/w/api.php?action=parse&page="
            f"{urllib.parse.quote(clean_w)}&prop=wikitext&format=json"
        )
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "ScreenLingo-Dictionary/1.0"}
            )
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if "parse" in data and "wikitext" in data["parse"]:
                wikitext = data["parse"]["wikitext"]["*"]

                # 1. Genus / Artikel tespiti
                genus_match = re.search(r"Genus(?:\s*\d+)?\s*=\s*([fmn])\b", wikitext)
                if genus_match:
                    g = genus_match.group(1).lower()
                    if g == "m":
                        info["article"] = "der"
                        info["pos"] = "İsim (Nomen)"
                    elif g == "f":
                        info["article"] = "die"
                        info["pos"] = "İsim (Nomen)"
                    elif g == "n":
                        info["article"] = "das"
                        info["pos"] = "İsim (Nomen)"

                # 2. Çoğul tespiti
                plural_match = re.search(r"Nominativ Plural(?:\s*\d+)?\s*=\s*([^|\}\n]+)", wikitext)
                if plural_match:
                    plural_clean = re.sub(r"[\[\]<>]", "", plural_match.group(1)).strip()
                    if plural_clean and plural_clean != "—":
                        info["plural"] = f"die {plural_clean}" if not plural_clean.startswith("die") else plural_clean

                # Fiil / Sıfat kontrolü
                if not info["pos"] and "Wortart|Verb|Deutsch" in wikitext:
                    info["pos"] = "Fiil (Verb)"
                elif not info["pos"] and "Wortart|Adjektiv|Deutsch" in wikitext:
                    info["pos"] = "Sıfat (Adjektiv)"
        except Exception:
            pass
        return info

    def _lookup_word(self, word_text: str, gt_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Tek bir kelimenin tam dilbilgisi ve anlam analizini yapar."""
        if not word_text or not word_text.strip():
            return {"error": "Boş kelime"}

        given_art, base_word = extract_base_word(word_text)
        if not base_word:
            return {"error": "Geçerli kelime bulunamadı"}

        # Çeviri API'si çağrısı
        try:
            if not gt_data:
                gt_data = self._translate_via_gt(base_word, sl="de", tl="tr")
            turkish_meaning = gt_data["translated_text"]
            dict_entries = gt_data["dict_entries"]
        except Exception as e:
            turkish_meaning = ""
            dict_entries = []

        # Wiktionary'den artikel ve çoğul çek
        wiki_info = self._fetch_wiktionary_info(base_word)
        article = given_art or wiki_info["article"]
        plural = wiki_info["plural"]
        pos = wiki_info["pos"]

        # Eğer Wiktionary bulamadıysa, son ek kuralıyla artikel tahmin et
        rule_explanation = ""
        if not article and (base_word[0].isupper() or given_art):
            predicted_art, explanation = predict_gender_by_rules(base_word)
            if predicted_art:
                article = predicted_art
                rule_explanation = explanation

        # Bileşik İsim Kuralı (Komposita)
        if not article and len(base_word) >= 5 and (base_word[0].isupper() or given_art):
            bw_lower = base_word.lower()
            for key, val in COMMON_VOCABULARY.items():
                if len(key) >= 3 and bw_lower.endswith(key) and len(bw_lower) > len(key):
                    tail_art = val.get("article", "")
                    if tail_art:
                        article = tail_art
                        tail_word = key.capitalize()
                        rule_explanation = f"Bileşik isim kuralı: İsim '{tail_word}' ile bittiği için artikeli '{tail_art}' olur."
                        if not plural and val.get("plural"):
                            tail_pl = re.sub(r"^die\s+", "", val["plural"])
                            stem = base_word[:-len(key)]
                            plural = f"die {stem}{tail_pl.lower()}"
                        break

        # Pos bulunamadıysa dict_entries'den al
        if not pos and dict_entries:
            pos = dict_entries[0]["pos"]

        # Eğer isimse kelimenin ilk harfi büyük olsun
        display_german = base_word
        if base_word and (article or pos == "İsim (Nomen)" or base_word[0].isupper()):
            display_german = base_word.capitalize()

        return {
            "source": "online_lexicon",
            "direction": "de_to_tr",
            "detected_lang": "de",
            "german": display_german,
            "article": article,
            "article_color": ARTICLE_COLORS.get(article, "#6b7280"),
            "plural": plural,
            "turkish": turkish_meaning or "Çeviri bulunamadı",
            "pos": pos or "Kelime",
            "dict_entries": dict_entries,
            "rule_note": rule_explanation,
            "original": word_text,
            "translation": turkish_meaning,
            "is_sentence": False
        }

    def _map_pos_to_turkish(self, pos_name: str) -> str:
        mapping = {
            "noun": "İsim (Nomen)",
            "verb": "Fiil (Verb)",
            "adjective": "Sıfat (Adjektiv)",
            "adverb": "Zarf (Adverb)",
            "preposition": "Edat (Präposition)",
            "conjunction": "Bağlaç (Konjunktion)",
            "pronoun": "Zamir (Pronomen)"
        }
        return mapping.get(pos_name.lower(), pos_name.capitalize())
