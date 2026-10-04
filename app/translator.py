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
import time
from typing import Dict, Any, Optional

from app.database import Database
from app.german_analyzer import (
    clean_text, is_single_word, extract_base_word, predict_gender_by_rules,
    analyze_sentence_grammar, get_offline_analysis, get_offline_reverse_analysis,
    ARTICLE_COLORS, COMMON_VOCABULARY, PLURAL_INDEX
)
from app.gemini_service import GeminiService


class TranslationEngine:
    def __init__(
        self,
        db: Optional[Database] = None,
        gemini_api_key: str = "",
        use_gemini_direct: bool = False,
        gemini_model: str = "gemini-3.5-flash-lite"
    ):
        self.db = db or Database()
        self.gemini_service = GeminiService(gemini_api_key, model=gemini_model)
        self.use_gemini_direct = use_gemini_direct
        self.default_timeout_budget: float = 3.5
        self._wiktionary_cooldown_until: float = 0.0

    def set_gemini_key(self, key: str):
        self.gemini_service.set_api_key(key)

    def set_gemini_options(self, use_direct: bool, model: str = "gemini-3.5-flash-lite"):
        self.use_gemini_direct = use_direct
        self.gemini_service.set_model(model)

    def translate_and_analyze(self, text: str, timeout_budget: Optional[float] = None) -> Dict[str, Any]:
        """
        Metinleri ve kelimeleri analiz eder ve SADECE TÜRKÇEYE çevirir.
        Almanca artikel (der/die/das), çoğul ve dilbilgisi kurallarını ekler.
        Zaman bütçesi (timeout_budget) basamaklı gecikmeyi sınırlandırmak için kullanılan yumuşak bir bütçedir
        (best-effort deadline). Kalan süre alt servislere aktarılır ve normal ağ koşullarında toplam süre
        bütçe + tolerans (~0.15s-0.25s) aralığında tutulur.
        """
        clean = clean_text(text)
        if not clean:
            return {"error": "Boş metin"}

        budget = timeout_budget if timeout_budget is not None else self.default_timeout_budget
        deadline = time.monotonic() + budget

        # 1. Önce Önbelleğe (Cache) Bak (Token tasarrufu ve 0ms yanıt için)
        cached = self.db.get_cache(clean)
        if cached:
            tr_val = (cached.get("turkish") or cached.get("translation") or "").strip()
            invalid_terms = ("çeviri bulunamadı", "çeviri alınamadı", "error", "hata")
            # Önbellekteki Türkçe çeviri geçerli bir çeviriyse ve hata mesajı değilse kullan
            if tr_val and tr_val.lower() != clean.lower() and not any(term in tr_val.lower() for term in invalid_terms):
                hist_ok = self.db.add_history(clean, cached)
                if hist_ok is False:
                    print("[Ekran Sözlüğü UYARI] Arama geçmişi veritabanına kaydedilemedi (veritabanı kapalı veya erişilemez).")
                    cached["db_saved"] = False
                else:
                    cached["db_saved"] = True
                cached["from_cache"] = True
                return cached

        # 2. Doğrudan Gemini AI Seçeneği Aktifse (En ekonomik Flash model ile sor)
        if self.use_gemini_direct and self.gemini_service.is_configured():
            if (deadline - time.monotonic()) > 0.3:
                try:
                    gemini_res = self.gemini_service.translate_and_analyze(clean, deadline=deadline)
                    if gemini_res and "error" not in gemini_res:
                        tr_text = (gemini_res.get("turkish") or "").strip()
                        if tr_text and tr_text.lower() != clean.lower():
                            cache_ok = self.db.set_cache(clean, gemini_res)
                            hist_ok = self.db.add_history(clean, gemini_res)
                            if cache_ok is False or hist_ok is False:
                                print("[Ekran Sözlüğü UYARI] Gemini çeviri sonucu veritabanına kaydedilemedi (veritabanı kapalı veya erişilemez).")
                                gemini_res["db_saved"] = False
                            else:
                                gemini_res["db_saved"] = True
                            return gemini_res
                except Exception as e:
                    print(f"[Gemini Direct Error] Standart motora geçiliyor: {type(e).__name__}")

        # 3. Tek kelimeler için kontrol
        is_word = is_single_word(clean)
        if is_word:
            # 3a. Çevrimdışı Almanca Sözlük (0ms)
            offline_de = get_offline_analysis(clean)
            if offline_de:
                offline_de["direction"] = "de_to_tr"
                offline_de["translation"] = offline_de["turkish"]
                cache_ok = self.db.set_cache(clean, offline_de)
                hist_ok = self.db.add_history(clean, offline_de)
                if cache_ok is False or hist_ok is False:
                    print("[Ekran Sözlüğü UYARI] Çevrimdışı sözlük sonucu veritabanına kaydedilemedi (veritabanı kapalı veya erişilemez).")
                    offline_de["db_saved"] = False
                else:
                    offline_de["db_saved"] = True
                return offline_de

            # 3b. Çevrimiçi Detaylı Kelime Çevirisi (Wiktionary + Google Translate)
            result = self._lookup_word(clean, deadline=deadline)
        else:
            # 4. Cümleler için Çeviri (Google Translate ile Kesin Türkçe: sl="auto", tl="tr")
            result = self._translate_sentence(clean, deadline=deadline)

        # 5. Gemini AI Ek Açıklaması (Yapılandırılmışsa ve doğrudan mod kapalıysa, zaman bütçesi yetiyorsa)
        remaining = deadline - time.monotonic()
        if remaining > 0.4 and result and "error" not in result and self.gemini_service.is_configured():
            try:
                gemini_note = self.gemini_service.generate_explanation(
                    clean,
                    source_lang="de",
                    target_lang="tr",
                    deadline=deadline
                )
                if gemini_note:
                    result["gemini_explanation"] = gemini_note
                    if not result.get("rule_note"):
                        result["rule_note"] = gemini_note
            except Exception:
                pass

        # 6. Sonucu önbelleğe ve geçmişe kaydet (Yalnızca geçerli çeviriler)
        if result and "error" not in result:
            tr_res = (result.get("turkish") or result.get("translation") or "").strip().lower()
            invalid_terms = ("çeviri bulunamadı", "çeviri alınamadı", "error", "hata")
            if tr_res and not any(term in tr_res for term in invalid_terms):
                cache_ok = self.db.set_cache(clean, result)
                hist_ok = self.db.add_history(clean, result)
                if cache_ok is False or hist_ok is False:
                    print("[Ekran Sözlüğü UYARI] Çeviri sonucu veritabanına kaydedilemedi (veritabanı kapalı veya erişilemez).")
                    result["db_saved"] = False
                else:
                    result["db_saved"] = True

        return result

    def _translate_sentence(self, text: str, deadline: Optional[float] = None) -> Dict[str, Any]:
        """Cümleyi Google Translate (veya Gemini AI yedeği) üzerinden Türkçeye çevirir ve dilbilgisi kurallarını ekler."""
        is_offline = False
        turkish_meaning = ""
        now = time.monotonic()
        if deadline is not None and (deadline - now) <= 0.15:
            is_offline = True
        else:
            try:
                gt_data = self._translate_via_gt(text, sl="auto", tl="tr", deadline=deadline)
                turkish_meaning = gt_data["translated_text"]
            except Exception:
                # Google Translate başarısız olursa Gemini AI yedek olarak devreye girsin (zaman bütçesi varsa)
                now = time.monotonic()
                if deadline is None or (deadline - now) > 0.3:
                    if self.gemini_service.is_configured():
                        try:
                            g_res = self.gemini_service.translate_and_analyze(text, deadline=deadline)
                            if g_res and g_res.get("turkish"):
                                turkish_meaning = g_res["turkish"]
                        except Exception:
                            pass

                if not turkish_meaning:
                    turkish_meaning = "Çeviri alınamadı (İnternet bağlantısı yok veya servis meşgul)"
                    is_offline = True

        grammar_notes = analyze_sentence_grammar(text)
        return {
            "source": "sentence_translator",
            "direction": "de_to_tr",
            "german": text,
            "turkish": turkish_meaning,
            "original": text,
            "translation": turkish_meaning,
            "is_sentence": True,
            "grammar_notes": grammar_notes,
            "offline_mode": is_offline
        }

    def _translate_via_gt(
        self,
        text: str,
        sl: str = "auto",
        tl: str = "tr",
        deadline: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Google Translate API üzerinden çoklu istemci desteğiyle (dict-chrome-ex, gtx, t)
        hızlı ve kesintisiz çeviri ve sözlük bilgisi çeker.
        Global zaman bütçesi (Global Timeout Budget) uygulayarak basamaklı gecikmeyi (cascading latency) engeller.
        """
        clients = ["dict-chrome-ex", "gtx", "t"]
        last_error = None

        for client in clients:
            now = time.monotonic()
            if deadline is not None:
                remaining = deadline - now
                if remaining <= 0.15:
                    break
                per_client_timeout = max(0.1, min(1.0, remaining))
            else:
                per_client_timeout = 2.0

            try:
                url = (
                    f"https://translate.googleapis.com/translate_a/single?"
                    f"client={client}&sl={sl}&tl={tl}&dt=t&dt=bd&dt=rm&q={urllib.parse.quote(text)}"
                )
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                        "Accept": "*/*",
                    }
                )
                with urllib.request.urlopen(req, timeout=per_client_timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                # Cümle veya ana çeviri
                translated_text = "".join([item[0] for item in data[0] if item and item[0]])
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

                if translated_text:
                    return {
                        "translated_text": translated_text,
                        "detected_lang": detected_lang,
                        "dict_entries": dict_entries
                    }
            except Exception as e:
                last_error = e
                continue

        raise last_error or Exception("Tüm çeviri istemcileri yanıt vermedi veya zaman aşımına uğradı.")

    def _fetch_wiktionary_info(
        self,
        word: str,
        timeout: float = 1.5,
        pos_hint: str = "",
        deadline: Optional[float] = None
    ) -> Dict[str, str]:
        """
        Almanca Wiktionary üzerinden artikel, çoğul ve sözcük türünü ayrıştırır.
        Fiiller ve sıfatlar için isim artikeli (das) dayatmaz; Wikimedia politikasına uygun User-Agent kullanır.
        """
        info = {"article": "", "plural": "", "pos": ""}
        if not word or not word.strip():
            return info

        # Eğer kelimenin fiil veya sıfat olduğu GT veya bağlamdan biliniyorsa artikel aranmaz
        if pos_hint in ("Fiil (Verb)", "Sıfat (Adjektiv)", "Zarf (Adverb)", "Edat (Präposition)", "Bağlaç (Konjunktion)"):
            info["pos"] = pos_hint
            return info

        # 429 veya bağlantı hatası sonrası cooldown kontrolü
        if time.monotonic() < getattr(self, "_wiktionary_cooldown_until", 0.0):
            return info

        headers = {
            "User-Agent": "ScreenLingo/1.0 (https://github.com/SandL0J/On-screen-dictionary; dictionary-app@screenlingo.org)"
        }

        def _query_wiki(page_title: str) -> Optional[str]:
            if deadline is not None:
                rem = deadline - time.monotonic()
                if rem <= 0.15:
                    return None
                call_timeout = max(0.1, min(timeout, rem))
            else:
                call_timeout = timeout

            url = (
                f"https://de.wiktionary.org/w/api.php?action=parse&page="
                f"{urllib.parse.quote(page_title)}&prop=wikitext&format=json"
            )
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=call_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if "parse" in data and "wikitext" in data["parse"]:
                return data["parse"]["wikitext"]["*"]
            return None

        clean_w = word.strip()
        try:
            wikitext = None
            # 1. Kullanıcı küçük harf girdiyse önce küçük harfle sorgula (fiil veya sıfat ise doğru sayfa budur)
            if not clean_w[0].isupper():
                wikitext = _query_wiki(clean_w)
                if wikitext:
                    if "Wortart|Verb|Deutsch" in wikitext:
                        info["pos"] = "Fiil (Verb)"
                        return info
                    elif "Wortart|Adjektiv|Deutsch" in wikitext:
                        info["pos"] = "Sıfat (Adjektiv)"
                        return info

            # 2. Küçük harfte fiil/sıfat bulunamadıysa veya kelime zaten büyük harfle başlıyorsa büyük harfle dene
            if not wikitext:
                wikitext = _query_wiki(clean_w.capitalize())

            if wikitext:
                # Genus / Artikel tespiti
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

                # Çoğul tespiti
                plural_match = re.search(r"Nominativ Plural(?:\s*\d+)?\s*=\s*([^|\}\n]+)", wikitext)
                if plural_match:
                    plural_clean = re.sub(r"[\[\]<>]", "", plural_match.group(1)).strip()
                    if plural_clean and plural_clean != "—":
                        info["plural"] = f"die {plural_clean}" if not plural_clean.startswith("die") else plural_clean

                if not info["pos"] and "Wortart|Verb|Deutsch" in wikitext:
                    info["pos"] = "Fiil (Verb)"
                elif not info["pos"] and "Wortart|Adjektiv|Deutsch" in wikitext:
                    info["pos"] = "Sıfat (Adjektiv)"
        except urllib.error.HTTPError as he:
            if he.code == 429:
                self._wiktionary_cooldown_until = time.monotonic() + 60.0
        except Exception:
            pass

        return info

    def _lookup_word(
        self,
        word_text: str,
        gt_data: Optional[Dict[str, Any]] = None,
        deadline: Optional[float] = None
    ) -> Dict[str, Any]:
        """Tek bir kelimenin tam dilbilgisi ve anlam analizini yapar."""
        if not word_text or not word_text.strip():
            return {"error": "Boş kelime"}

        given_art, base_word = extract_base_word(word_text)
        if not base_word:
            return {"error": "Geçerli kelime bulunamadı"}

        # Çeviri API'si çağrısı
        gt_network_failed = False
        now = time.monotonic()
        if deadline is not None and (deadline - now) <= 0.15:
            gt_network_failed = True
            turkish_meaning = ""
            dict_entries = []
        else:
            try:
                if not gt_data:
                    gt_data = self._translate_via_gt(base_word, sl="de", tl="tr", deadline=deadline)
                turkish_meaning = gt_data["translated_text"]
                dict_entries = gt_data["dict_entries"]
            except Exception:
                turkish_meaning = ""
                dict_entries = []
                gt_network_failed = True

        pos_hint = dict_entries[0]["pos"] if dict_entries else ""

        # Wiktionary'den artikel ve çoğul çek (Eğer GT ağ hatası verdiyse Wiktionary ağ çağrısı da atlanmalı)
        wiki_info = {"article": "", "plural": "", "pos": ""}
        if not gt_network_failed:
            now = time.monotonic()
            rem = (deadline - now) if deadline is not None else 1.5
            if rem > 0.2:
                wiki_timeout = max(0.1, min(1.2, rem))
                wiki_info = self._fetch_wiktionary_info(base_word, timeout=wiki_timeout, pos_hint=pos_hint, deadline=deadline)

        article = given_art or wiki_info["article"]
        plural = wiki_info["plural"]
        pos = wiki_info["pos"] or pos_hint
        is_predicted = False

        # Google Translate başarısız olduysa ve Gemini yapılandırılmışsa Gemini AI ile dene
        if not turkish_meaning and self.gemini_service.is_configured():
            now = time.monotonic()
            if deadline is None or (deadline - now) > 0.3:
                try:
                    g_res = self.gemini_service.translate_and_analyze(base_word, deadline=deadline)
                    if g_res and g_res.get("turkish"):
                        turkish_meaning = g_res["turkish"]
                        if not article and g_res.get("article"):
                            article = g_res["article"]
                        if not plural and g_res.get("plural"):
                            plural = g_res["plural"]
                        if not pos and g_res.get("pos"):
                            pos = g_res["pos"]
                        if not dict_entries and g_res.get("dict_entries"):
                            dict_entries = g_res["dict_entries"]
                except Exception:
                    pass

        # Eğer kelime fiil veya sıfat ise artikel zorla aranmaz/atanmaz
        is_verb_or_adj = pos in ("Fiil (Verb)", "Sıfat (Adjektiv)", "Zarf (Adverb)")
        if is_verb_or_adj and not given_art:
            article = ""

        rule_explanation = ""

        # Eğer Wiktionary bulamadıysa, son ek kuralıyla artikel tahmin et (Yalnızca isim veya olası isimler için)
        if not article and not is_verb_or_adj and (base_word[0].isupper() or given_art):
            predicted_art, explanation = predict_gender_by_rules(base_word)
            if predicted_art:
                article = predicted_art
                rule_explanation = explanation
                is_predicted = True

        # Bileşik İsim Kuralı (Komposita)
        if not article and not is_verb_or_adj and len(base_word) >= 5 and (base_word[0].isupper() or given_art):
            bw_lower = base_word.lower()
            for key, val in COMMON_VOCABULARY.items():
                if len(key) >= 3 and bw_lower.endswith(key) and len(bw_lower) > len(key):
                    tail_art = val.get("article", "")
                    if tail_art:
                        article = tail_art
                        tail_word = key.capitalize()
                        rule_explanation = f"Bileşik isim kuralı: İsim '{tail_word}' ile bittiği için artikeli '{tail_art}' olur."
                        # Sayılamayan isimlerde ("-") sahte çoğul üretilmesini engelle
                        if not plural and val.get("plural") and val.get("plural").strip() != "-":
                            tail_pl = re.sub(r"^die\s+", "", val["plural"]).strip()
                            stem = base_word[:-len(key)]
                            plural = f"die {stem}{tail_pl.lower()}"
                        break

            # Çoğul bileşik kelime tespiti (Örn: Krankenhäuser -> sonu 'häuser' ile biter, tekili 'haus')
            if not article:
                for pl_key, sing_key in PLURAL_INDEX.items():
                    if len(pl_key) >= 3 and bw_lower.endswith(pl_key) and len(bw_lower) > len(pl_key):
                        val = COMMON_VOCABULARY.get(sing_key, {})
                        tail_art = val.get("article", "")
                        if tail_art:
                            article = tail_art
                            sing_word = sing_key.capitalize()
                            rule_explanation = f"Bileşik isim kuralı (Çoğul): Tekil hali '{sing_word}' ('{tail_art}') ile biter."
                            if not plural:
                                plural = f"die {base_word.capitalize()}"
                            break

        # Pos bulunamadıysa dict_entries'den al
        if not pos and dict_entries:
            pos = dict_entries[0]["pos"]

        # Eğer isimse kelimenin ilk harfi büyük olsun, fiil/sıfatsa küçük harf korunsun
        display_german = base_word
        if base_word and not is_verb_or_adj and (article or pos == "İsim (Nomen)" or base_word[0].isupper()):
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
            "is_predicted": is_predicted,
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
