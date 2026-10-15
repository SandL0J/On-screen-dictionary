"""
Almanca Pedagojik Dilbilgisi ve Öğrenme Asistanı (Pedagogy Engine)
Almanca öğrenenlere özel:
1. Fiil İstemleri (Rektion der Verben: warten auf + Akk)
2. İki Yönlü Edat Rehberi (Wechselpräpositionen: in/an/auf Akkusativ mi Dativ mi?)
3. Kalıp ve Deyim Tespiti (Collocations & Redewendungen: es geht um, auf jeden Fall)
"""
from typing import Dict, Optional, Any, List

from app.data.verb_valency import find_verb_valency
from app.data.two_way_prepositions import detect_two_way_preposition
from app.data.collocations import find_collocation


def analyze_pedagogy(word: str, sentence: str = "", lemma: str = "") -> Dict[str, Any]:
    """
    Hedef kelime, bağlam cümlesi ve çözümlenmiş sözlük biçimi (lemma) üzerinden
    üç temel pedagojik dilbilgisi ipucunu analiz eder.
    """
    clean_word = (word or "").strip()
    clean_sent = (sentence or "").strip()
    clean_lemma = (lemma or "").strip()

    # 1. Kalıp ve Deyim Tespiti (Öncelikli: birden fazla kelimeden oluşan anlamlar)
    collocation = find_collocation(clean_word, clean_sent)

    # 2. Fiil İstemleri (Rektion der Verben)
    # Önce çözümlenmiş lemma (mastar), yoksa kelimenin kendisiyle sorgula
    lookup_verb = clean_lemma if clean_lemma else clean_word
    valency = find_verb_valency(lookup_verb, clean_sent)
    if not valency and clean_word and clean_word != lookup_verb:
        valency = find_verb_valency(clean_word, clean_sent)

    # 3. İki Yönlü Edat Rehberi (Wechselpräpositionen)
    two_way_prep = detect_two_way_preposition(clean_word, clean_sent)

    # Görsel listelenecek ipuçları
    hints: List[str] = []
    if collocation:
        hints.append(collocation["hint"])
    if valency:
        hints.append(valency["formatted_hint"])
    if two_way_prep:
        hints.append(two_way_prep["hint"])

    return {
        "collocation": collocation,
        "valency": valency,
        "two_way_prep": two_way_prep,
        "pedagogy_hints": hints
    }
