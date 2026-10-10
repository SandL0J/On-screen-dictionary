"""
Almanca Sözlük Biçimi (Lemma) ve Ayrılabilir Fiil Çözümleme Modülü
(German Lemmatizer and Separable Verb Analyzer)

Windows için Tkinter ve GUI bağımlılığı olmadan, saf Python ile çalışır.
Kullanıcı bir çekimli fiil (ging, fängt) veya ayrılmış önek (an) üzerine geldiğinde
sözlük biçimini (gehen, anfangen) ve çekim bilgisini yüksek güvenilirlikle çözümler.
"""

from dataclasses import dataclass
import re
from typing import Optional, List, Tuple, Set

from app.data.irregular_verbs import REVERSE_IRREGULAR_INDEX, IRREGULAR_VERBS_DATA
from app.german_analyzer import (
    SEPARABLE_PREFIXES,
    MODAL_VERBS,
    SUBORDINATING_CONJUNCTIONS,
    COMMON_VOCABULARY
)

# Ayrılmayan Önekler (Inseparable Prefixes - Asla ayrılamazlar)
INSEPARABLE_PREFIXES: Tuple[str, ...] = (
    "be", "ge", "er", "ver", "zer", "ent", "emp", "miss"
)

# Çift Yönlü Önekler (Zweifelsfälle / Trennbar oder untrennbar)
DUBIOUS_PREFIXES: Set[str] = {
    "über", "unter", "durch", "um", "wider", "wieder"
}

# Çekimli fiil ararken atlanacak edat, zamir, sayı ve zarf sözcükleri
NON_VERB_TOKENS: Set[str] = {
    "um", "am", "im", "in", "an", "auf", "aus", "bei", "mit", "nach", "von",
    "zu", "vor", "über", "unter", "durch", "für", "gegen", "ohne", "bis",
    "eins", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun", "zehn", "elf", "zwölf",
    "ich", "du", "er", "sie", "es", "wir", "ihr", "mich", "dich", "ihn", "uns", "euch", "ihnen",
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer", "eines",
    "kein", "keine", "keinen", "keinem", "keiner", "keines",
    "nicht", "nie", "oft", "immer", "heute", "morgen", "gestern", "jetzt", "hier", "dort", "sehr",
    "auch", "so", "dann", "schon", "nur", "mal", "doch", "noch", "wieder", "etwas", "nichts", "alles"
}

# Yaygın düzenli mastarlar (Regular verbs vocabulary for verification)
KNOWN_REGULAR_VERBS: Set[str] = {
    "machen", "lernen", "arbeiten", "fragen", "antworten", "wohnen", "leben",
    "kaufen", "verkaufen", "suchen", "spielen", "hoffen", "glauben", "warten",
    "öffnen", "schließen", "hören", "schauen", "zeigen", "erklären", "erzählen",
    "reisen", "feiern", "kosten", "zahlen", "bezahlen", "tanzen", "kochen",
    "putzen", "bauen", "planen", "studieren", "probieren", "brauchen", "lieben",
    "passieren", "funktionieren", "interessieren", "informieren", "reparieren"
}

# Tüm bilinen temel mastarlar kümesi
ALL_BASE_VERBS: Set[str] = set(IRREGULAR_VERBS_DATA.keys()) | KNOWN_REGULAR_VERBS
for k, v in COMMON_VOCABULARY.items():
    if "fiil" in v.get("pos", "").lower():
        ALL_BASE_VERBS.add(k)


@dataclass
class LemmaResult:
    surface: str              # Ekrandaki biçim: "ging", "fängt", "an"
    lemma: str                # Sözlük biçimi: "gehen", "anfangen"; bulunamazsa surface
    form_label: str           # "Präteritum", "Partizip II", "Präsens (er/sie/es)", "zu-Infinitiv", "ayrılabilir fiil", ""
    separable_prefix: str     # "an" veya ""
    confidence: str           # "high" | "medium" | "low" | "none"
    source: str               # "irregular_table" | "separable_rule" | "participle_rule" | "regular_rule" | "none"
    verb_surface: str = ""    # Ayrılabilir fiillerde çekimli fiil parçası (örn. "fängt")


def format_lemma_hint(res: LemmaResult) -> str:
    """UI üzerinde gösterilmek üzere tek satırlık açıklama metni üretir. Değişiklik yoksa boş döner."""
    if not res or res.confidence not in ("high", "medium"):
        return ""
    if res.lemma.lower() == res.surface.lower() and not res.separable_prefix:
        return ""

    if res.separable_prefix:
        prefix = res.separable_prefix
        verb_part = res.verb_surface if res.verb_surface else res.surface
        if verb_part.lower() == prefix.lower():
            verb_part = "…"
        label = res.form_label or "ayrılabilir fiil"
        return f"🧩 {verb_part} … {prefix} → {res.lemma} · {label}"

    label = f" · {res.form_label}" if res.form_label else ""
    return f"🔁 {res.surface} → {res.lemma}{label}"


def _clean_token(token: str) -> str:
    """Kelime token'ını çevreleyen noktalama ve tırnaklardan arındırır."""
    if not token:
        return ""
    return token.strip(".,!?:;\"'()[]{}„“»«-_~ \t\r\n")


def _is_known_verb(verb: str) -> bool:
    """Verilen mastarın bilinen temel veya bileşik fiillerden biri olup olmadığını doğrular."""
    v_clean = verb.lower().strip()
    if v_clean in ALL_BASE_VERBS:
        return True
    # Ayrılabilir önek + bilinen kök kontrolü (örn. anfangen = an + fangen)
    for pfx in SEPARABLE_PREFIXES:
        if v_clean.startswith(pfx):
            root = v_clean[len(pfx):]
            if root in ALL_BASE_VERBS:
                return True
    # Ayrılmayan önek + bilinen kök (örn. verstehen = ver + stehen)
    for pfx in INSEPARABLE_PREFIXES:
        if v_clean.startswith(pfx):
            root = v_clean[len(pfx):]
            if root in ALL_BASE_VERBS:
                return True
    return False


def _get_clause_for_word(word: str, sentence: str) -> List[str]:
    """
    Cümleyi yan cümle ve noktalama sınırlarına göre ayırır ve
    hover edilen kelimenin yer aldığı yan cümlenin token listesini döndürür.
    """
    if not sentence or not word:
        return []

    w_clean = _clean_token(word).lower()
    if not w_clean:
        return []

    # Cümleyi virgül, noktalı virgül, iki nokta, nokta, ünlem, soru işareti ile yan cümlelere böl
    raw_clauses = re.split(r'[,;:\.!\?\n\t]+', sentence)
    matching_tokens: List[str] = []

    for clause in raw_clauses:
        raw_words = clause.split()
        cleaned_words = [_clean_token(w) for w in raw_words if _clean_token(w)]
        lowered_words = [w.lower() for w in cleaned_words]

        # Ayrıca yan cümle bağlaçlarıyla bölünme varsa (örn. "weil", "dass")
        # Eğer bağlaç ortadaysa yan cümleyi böl
        sub_splits: List[List[str]] = [[]]
        for cw, lw in zip(cleaned_words, lowered_words):
            if lw in SUBORDINATING_CONJUNCTIONS and sub_splits[-1]:
                sub_splits.append([cw])
            else:
                sub_splits[-1].append(cw)

        for sub_clause in sub_splits:
            sub_lowered = [w.lower() for w in sub_clause]
            if w_clean in sub_lowered:
                matching_tokens = sub_clause
                break
        if matching_tokens:
            break

    return matching_tokens


def _resolve_separable_context(word: str, sentence: str) -> Optional[LemmaResult]:
    """
    Katman 2: Bağlam cümlesindeki ayrılabilir fiil (trennbare Verben) yapısını çözümler.
    - Durum 1: Kelime çekimli fiil, yan cümlenin sonundaki sözcük ayrılabilir önek.
    - Durum 2: Kelime yan cümlenin sonundaki ayrılabilir önek, geriye doğru çekimli fiili bulur.
    """
    if not sentence or not word:
        return None

    clause_tokens = _get_clause_for_word(word, sentence)
    if len(clause_tokens) < 2:
        return None

    w_clean = _clean_token(word)
    w_lower = w_clean.lower()
    last_token = clause_tokens[-1]
    last_lower = last_token.lower()

    # Ayrılabilir önek kontrolü
    # Edat tuzağı: Önek MUTLAKA yan cümlenin en sonundaki kelime olmalıdır!
    # Eğer cümlenin sonundaki kelime ayrılabilir önek listesinde değilse ayrılabilir fiil değildir.
    if last_lower not in SEPARABLE_PREFIXES:
        return None

    # Ayrılmayan önekler (be, ver...) asla ayrılamaz
    if any(last_lower.startswith(inpfx) for inpfx in INSEPARABLE_PREFIXES):
        return None

    confidence = "medium" if last_lower in DUBIOUS_PREFIXES else "high"

    # Durum 1: Hover edilen kelime çekimli fiil ve son kelime önek
    # Örnek: "Er fängt morgen an." -> word="fängt", last_lower="an"
    if w_lower != last_lower:
        # Fiilin kökünü veya mastarını bul
        base_inf = ""
        form_lbl = "ayrılabilir fiil"

        # 1a. Düzensiz fiil tablosundan kök
        if w_lower in REVERSE_IRREGULAR_INDEX:
            base_inf, form_lbl = REVERSE_IRREGULAR_INDEX[w_lower]
        else:
            # 1b. Düzenli fiil çekim kuralından kök
            reg_res = _resolve_regular_verb(w_lower)
            if reg_res:
                base_inf = reg_res[0]

        if base_inf:
            combined_lemma = last_lower + base_inf
            # Doğrulama
            if _is_known_verb(combined_lemma) or base_inf in ALL_BASE_VERBS:
                return LemmaResult(
                    surface=w_clean,
                    lemma=combined_lemma,
                    form_label="ayrılabilir fiil",
                    separable_prefix=last_lower,
                    confidence=confidence,
                    source="separable_rule",
                    verb_surface=w_clean
                )

    # Durum 2: Hover edilen kelime son kelimedeki önek
    # Örnek: "Er fängt morgen an." -> word="an", last_lower="an"
    elif w_lower == last_lower:
        # Geriye doğru çekimli fiili ara (V2 konumu veya ilk uygun fiil)
        finite_verb_cand = ""
        base_inf = ""

        # clause_tokens[:-1] içinde çekimli fiil tara
        for cand in clause_tokens[:-1]:
            cand_lower = cand.lower()
            if cand[0].isupper() and cand_lower in NON_VERB_TOKENS:
                continue
            if cand_lower in NON_VERB_TOKENS:
                continue
            if len(cand_lower) < 3:
                continue

            # Düzensiz fiil mi?
            if cand_lower in REVERSE_IRREGULAR_INDEX:
                finite_verb_cand = cand
                base_inf = REVERSE_IRREGULAR_INDEX[cand_lower][0]
                break

            # Düzenli fiil mi?
            reg_res = _resolve_regular_verb(cand_lower)
            if reg_res:
                finite_verb_cand = cand
                base_inf = reg_res[0]
                break

        if finite_verb_cand and base_inf:
            combined_lemma = last_lower + base_inf
            return LemmaResult(
                surface=w_clean,
                lemma=combined_lemma,
                form_label="ayrılabilir fiil",
                separable_prefix=last_lower,
                confidence=confidence,
                source="separable_rule",
                verb_surface=finite_verb_cand
            )

    return None


def _resolve_participle_and_zu_infinitive(w_lower: str, surface: str) -> Optional[LemmaResult]:
    """
    Katman 3: Partizip II ve zu-Infinitiv kuralları (bağlamsız).
    Örnekler:
    - aufgestanden -> auf + ge + standen -> aufstehen
    - angefangen -> an + ge + fangen -> anfangen
    - gemacht -> ge + mach + t -> machen
    - anzufangen -> an + zu + fangen -> anfangen
    - aufzustehen -> auf + zu + stehen -> aufstehen
    - aufsteht -> auf + steht -> aufstehen
    """
    # 3.1 zu-Infinitiv (Ayrılabilir fiillerde önek ile mastar arasına -zu- girer: anzufangen, aufzustehen)
    if "zu" in w_lower and (w_lower.endswith("en") or w_lower.endswith("eln") or w_lower.endswith("ern")):
        for pfx in SEPARABLE_PREFIXES:
            if w_lower.startswith(pfx + "zu"):
                root = w_lower[len(pfx) + 2:]
                combined = pfx + root
                if _is_known_verb(root) or _is_known_verb(combined):
                    return LemmaResult(
                        surface=surface,
                        lemma=combined,
                        form_label="zu-Infinitiv",
                        separable_prefix=pfx,
                        confidence="high",
                        source="participle_rule"
                    )

    # 3.2 Ayrılabilir fiil birleşik çekimi (Örn. yan cümlede: "aufsteht", "mitmacht", "aufgestanden")
    for pfx in SEPARABLE_PREFIXES:
        if w_lower.startswith(pfx) and len(w_lower) > len(pfx) + 2:
            rest = w_lower[len(pfx):]

            # 3.2.1 Partizip II: auf + ge + standen
            if rest.startswith("ge"):
                sub_rest = rest[2:]  # "standen" veya "macht"
                # sub_rest düzensiz mi?
                if rest in REVERSE_IRREGULAR_INDEX:
                    inf, lbl = REVERSE_IRREGULAR_INDEX[rest]
                    return LemmaResult(
                        surface=surface,
                        lemma=pfx + inf,
                        form_label="Partizip II",
                        separable_prefix=pfx,
                        confidence="high",
                        source="participle_rule"
                    )
                # düzenli ge + stem + t
                if sub_rest.endswith("t"):
                    stem = sub_rest[:-1]
                    cand_inf = stem + "en"
                    if _is_known_verb(cand_inf) or _is_known_verb(pfx + cand_inf):
                        return LemmaResult(
                            surface=surface,
                            lemma=pfx + cand_inf,
                            form_label="Partizip II",
                            separable_prefix=pfx,
                            confidence="high",
                            source="participle_rule"
                        )

            # 3.2.2 Präsens / Präteritum yan cümle birleşik formu (örn: "aufsteht" -> "aufstehen")
            if rest in REVERSE_IRREGULAR_INDEX:
                inf, lbl = REVERSE_IRREGULAR_INDEX[rest]
                return LemmaResult(
                    surface=surface,
                    lemma=pfx + inf,
                    form_label=lbl or "ayrılabilir fiil",
                    separable_prefix=pfx,
                    confidence="high",
                    source="participle_rule"
                )

            # 3.2.3 Düzenli çekimli: auf + macht -> aufmachen
            reg_sub = _resolve_regular_verb(rest)
            if reg_sub:
                cand_inf = reg_sub[0]
                if _is_known_verb(cand_inf) or _is_known_verb(pfx + cand_inf):
                    return LemmaResult(
                        surface=surface,
                        lemma=pfx + cand_inf,
                        form_label=reg_sub[1],
                        separable_prefix=pfx,
                        confidence="high",
                        source="participle_rule"
                    )

    # 3.3 Ayrılmayan önekli fiillerin Partizip II veya Präsens formu (örn: verstehe -> verstehen, befohlen -> befehlen)
    for pfx in INSEPARABLE_PREFIXES:
        if w_lower.startswith(pfx) and len(w_lower) > len(pfx) + 2:
            rest = w_lower[len(pfx):]
            if rest in REVERSE_IRREGULAR_INDEX:
                inf, lbl = REVERSE_IRREGULAR_INDEX[rest]
                combined = pfx + inf
                if _is_known_verb(combined):
                    return LemmaResult(
                        surface=surface,
                        lemma=combined,
                        form_label=lbl,
                        separable_prefix="",
                        confidence="high",
                        source="participle_rule"
                    )
            # Düzenli çekim
            reg_sub = _resolve_regular_verb(rest)
            if reg_sub:
                cand_inf = pfx + reg_sub[0]
                if _is_known_verb(cand_inf):
                    return LemmaResult(
                        surface=surface,
                        lemma=cand_inf,
                        form_label=reg_sub[1],
                        separable_prefix="",
                        confidence="high",
                        source="participle_rule"
                    )

    # 3.4 Standart düzenli Partizip II: ge + stem + t (örn: gemacht -> machen)
    if w_lower.startswith("ge") and len(w_lower) >= 5:
        sub = w_lower[2:]
        if sub.endswith("t"):
            stem = sub[:-1]
            if stem.endswith("e"):
                stem = stem[:-1]
            cand_inf = stem + "en"
            if _is_known_verb(cand_inf):
                return LemmaResult(
                    surface=surface,
                    lemma=cand_inf,
                    form_label="Partizip II",
                    separable_prefix="",
                    confidence="high",
                    source="participle_rule"
                )

    return None


def _resolve_regular_verb(w_lower: str) -> Optional[Tuple[str, str]]:
    """
    Düzenli fiil çekim eklerini soyarak (stem + en) olası mastarı ve çekim etiketini döndürür.
    Döner: (mastar, form_label)
    """
    if len(w_lower) < 4:
        return None

    # Präteritum ekleri (-test, -ten, -tet, -te)
    for end, lbl in [
        ("test", "Präteritum (du)"),
        ("ten", "Präteritum (wir/sie)"),
        ("tet", "Präteritum (ihr)"),
        ("te", "Präteritum"),
    ]:
        if w_lower.endswith(end):
            stem = w_lower[:-len(end)]
            if stem.endswith("e"):
                stem = stem[:-1]
            if len(stem) >= 2:
                cand = stem + "en"
                return cand, lbl

    # Präsens ekleri (-est, -st, -et, -t, -e)
    for end, lbl in [
        ("est", "Präsens (du)"),
        ("st", "Präsens (du)"),
        ("et", "Präsens (er/sie/es)"),
        ("t", "Präsens (er/sie/es)"),
        ("e", "Präsens (ich)"),
    ]:
        if w_lower.endswith(end):
            stem = w_lower[:-len(end)]
            if len(stem) >= 2:
                cand = stem + "en"
                return cand, lbl

    return None


def resolve_lemma(word: str, sentence: str = "") -> LemmaResult:
    """
    Verilen kelimenin Almanca sözlük biçimini (lemma) ve gramer formunu çözümler.

    Öncelik Sırası:
    1. Geçersiz / boş girdi kontrolü.
    2. Büyük harfli isim kontrolü (kapsam dışı).
    3. Cümle bağlamında ayrılabilir fiil tespiti (Katman 2).
    4. Düzensiz fiil tablosu (Katman 1 - Goethe/Duden ters indeks).
    5. Partizip II / zu-Infinitiv kuralları (Katman 3).
    6. Düzenli fiil çekim kuralları (Katman 4).
    7. Bulunamazsa 'none' sonucu (Katman 5).
    """
    if not word:
        return LemmaResult("", "", "", "", "none", "none")

    w_clean = _clean_token(word)
    if not w_clean:
        return LemmaResult(word, word, "", "", "none", "none")

    # Kural: Büyük harfle başlayan isimler kapsam dışıdır.
    # Ancak cümlenin ilk kelimesi olarak büyük harfle başlamış bir fiil olabilir (örn: "Ging er...")
    if w_clean[0].isupper():
        is_sentence_initial = False
        if sentence:
            first_token = _clean_token(sentence.strip().split()[0]) if sentence.strip().split() else ""
            if first_token.lower() == w_clean.lower():
                is_sentence_initial = True

        # Cümlenin başı değilse veya cümle verilmemişse büyük harfli sözcüğü isim kabul et ve dokunma
        if not is_sentence_initial:
            return LemmaResult(w_clean, w_clean, "", "", "none", "none")

    w_lower = w_clean.lower()

    # Katman 2: Ayrılabilir fiil (Bağlamlı, sentence gerekir)
    # Er fängt morgen an -> fängt ... an -> anfangen
    if sentence:
        sep_res = _resolve_separable_context(w_clean, sentence)
        if sep_res:
            return sep_res

    # Katman 1: Düzensiz fiil tablosu (REVERSE_IRREGULAR_INDEX)
    if w_lower in REVERSE_IRREGULAR_INDEX:
        infinitive, form_label = REVERSE_IRREGULAR_INDEX[w_lower]
        # Eğer kelimenin kendisi zaten mastarsa (Infinitiv) ve formu değişmediyse
        if w_lower == infinitive:
            return LemmaResult(
                surface=w_clean,
                lemma=infinitive,
                form_label="Infinitiv",
                separable_prefix="",
                confidence="high",
                source="irregular_table"
            )
        return LemmaResult(
            surface=w_clean,
            lemma=infinitive,
            form_label=form_label,
            separable_prefix="",
            confidence="high",
            source="irregular_table"
        )

    # Katman 3: Partizip II ve zu-Infinitiv kuralları (bağlamsız)
    part_res = _resolve_participle_and_zu_infinitive(w_lower, w_clean)
    if part_res:
        return part_res

    # Katman 4: Düzenli fiil çekim kuralları (bağlamsız)
    reg_tuple = _resolve_regular_verb(w_lower)
    if reg_tuple:
        cand_inf, form_lbl = reg_tuple
        if _is_known_verb(cand_inf):
            return LemmaResult(
                surface=w_clean,
                lemma=cand_inf,
                form_label=form_lbl,
                separable_prefix="",
                confidence="medium",
                source="regular_rule"
            )
        else:
            # Bilinmeyen kök -> low confidence (UI'da gösterilmez ve çevrilmez)
            return LemmaResult(
                surface=w_clean,
                lemma=cand_inf,
                form_label=form_lbl,
                separable_prefix="",
                confidence="low",
                source="regular_rule"
            )

    # Katman 5: Hiçbiri eşleşmezse
    return LemmaResult(
        surface=w_clean,
        lemma=w_clean,
        form_label="",
        separable_prefix="",
        confidence="none",
        source="none"
    )
