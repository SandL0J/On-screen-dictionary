"""
Almanca İki Yönlü Edatlar Modülü (Wechselpräpositionen)
'an, auf, hinter, in, neben, über, unter, vor, zwischen' edatlarının
cümle bağlamındaki Akkusativ (Wohin? / Hareket) mi Dativ (Wo? / Konum) mi olduğunu belirler.
"""
import re
from typing import Dict, Optional, Any

TWO_WAY_PREPOSITIONS = {
    "an", "auf", "hinter", "in", "neben", "über", "unter", "vor", "zwischen"
}

# Kaynaşmış Edat Biçimleri (Präposition + Artikel)
CONTRACTED_PREPOSITIONS: Dict[str, Dict[str, Any]] = {
    "ins": {
        "prep": "in",
        "case": "Akkusativ",
        "direction": "wohin",
        "role": "Hareket / Yönelme",
        "question": "Wohin? (Nereye?)",
        "expanded": "in das (Nötr Akkusativ)",
        "badge": "🏃 Akkusativ (Wohin?)",
        "hint": "🏃 İki Yönlü Edat (in + das = ins): Akkusativ · Hareket / Yönelme (Wohin?)"
    },
    "ans": {
        "prep": "an",
        "case": "Akkusativ",
        "direction": "wohin",
        "role": "Hareket / Yönelme",
        "question": "Wohin? (Nereye?)",
        "expanded": "an das (Nötr Akkusativ)",
        "badge": "🏃 Akkusativ (Wohin?)",
        "hint": "🏃 İki Yönlü Edat (an + das = ans): Akkusativ · Hareket / Yönelme (Wohin?)"
    },
    "aufs": {
        "prep": "auf",
        "case": "Akkusativ",
        "direction": "wohin",
        "role": "Hareket / Yönelme",
        "question": "Wohin? (Nereye?)",
        "expanded": "auf das (Nötr Akkusativ)",
        "badge": "🏃 Akkusativ (Wohin?)",
        "hint": "🏃 İki Yönlü Edat (auf + das = aufs): Akkusativ · Hareket / Yönelme (Wohin?)"
    },
    "im": {
        "prep": "in",
        "case": "Dativ",
        "direction": "wo",
        "role": "Konum / Bulunma",
        "question": "Wo? (Nerede?)",
        "expanded": "in dem (Eril/Nötr Dativ)",
        "badge": "📍 Dativ (Wo?)",
        "hint": "📍 İki Yönlü Edat (in + dem = im): Dativ · Konum / Bulunma (Wo?)"
    },
    "am": {
        "prep": "an",
        "case": "Dativ",
        "direction": "wo",
        "role": "Konum / Bulunma",
        "question": "Wo? (Nerede?)",
        "expanded": "an dem (Eril/Nötr Dativ)",
        "badge": "📍 Dativ (Wo?)",
        "hint": "📍 İki Yönlü Edat (an + dem = am): Dativ · Konum / Bulunma (Wo?)"
    }
}

# Durum / Konum Bildiren Fiiller (Daima Dativ ister)
POSITION_VERBS = {
    "liegen", "liegt", "lag", "gelegen",
    "stehen", "steht", "stand", "gestanden",
    "sitzen", "sitzt", "saß", "gesessen",
    "hängen", "hängt", "hing", "gehangen",
    "sein", "ist", "war", "gewesen", "sind", "bist",
    "bleiben", "bleibt", "blieb", "geblieben",
    "wohnen", "wohnt", "wohnte", "gewohnt",
    "arbeiten", "arbeitet", "arbeitete", "gearbeitet",
    "schlafen", "schläft", "schlief", "geschlafen"
}

# Hareket / Yönelim Bildiren Fiiller (Daima Akkusativ ister)
DIRECTION_VERBS = {
    "legen", "legt", "legte", "gelegt",
    "stellen", "stellt", "stellte", "gestellt",
    "setzen", "setzt", "setzte", "gesetzt",
    "gehen", "geht", "ging", "gegangen",
    "fahren", "fährt", "fuhr", "gefahren",
    "laufen", "läuft", "lief", "gelaufen",
    "fliegen", "fliegt", "flog", "geflogen",
    "springen", "springt", "sprang", "gesprungen",
    "bringen", "bringt", "brachte", "gebracht",
    "kommen", "kommt", "kam", "gekommen",
    "werfen", "wirft", "warf", "geworfen"
}


def detect_two_way_preposition(word: str, sentence: str = "") -> Optional[Dict[str, Any]]:
    """
    Hedef kelime veya cümledeki iki yönlü edatı (Wechselpräposition) analiz eder.
    Akkusativ (Wohin? / Hareket) mi Dativ (Wo? / Konum) mi olduğunu belirler.
    """
    w_clean = (word or "").strip().lower()
    s_clean = (sentence or "").strip()
    s_lower = s_clean.lower()

    # 1. Kelimenin kendisi kaynaşmış bir edat mı? ('ins', 'im', 'ans', 'am', 'aufs')
    if w_clean in CONTRACTED_PREPOSITIONS:
        return dict(CONTRACTED_PREPOSITIONS[w_clean])

    # 2. Cümle içinde kaynaşmış edat var mı?
    if s_lower:
        words_in_s = re.findall(r"\b[a-zäöüß]+\b", s_lower)
        for contracted, info in CONTRACTED_PREPOSITIONS.items():
            if contracted in words_in_s:
                # Eğer hover kelimesi bu edat veya hemen ardındaki isim ise
                return dict(info)

    # 3. İki yönlü edat tespiti (Doğrudan edat veya cümledeki edat)
    target_prep = None
    if w_clean in TWO_WAY_PREPOSITIONS:
        target_prep = w_clean
    elif s_lower:
        for prep in TWO_WAY_PREPOSITIONS:
            if re.search(r"\b" + re.escape(prep) + r"\b", s_lower):
                target_prep = prep
                break

    # 4. Edat bulunduysa ve cümle varsa, öncelikle ardından gelen artikeli kontrol et
    if target_prep and s_lower:
        match = re.search(r"\b" + re.escape(target_prep) + r"\b\s+([a-zäöüß]+)", s_lower)
        if match:
            next_word = match.group(1)
            # Dativ ipuçları: 'dem', 'der', 'einem', 'einer', 'meinem', 'deinem', 'ihrem'
            if next_word in ("dem", "einem", "meinem", "deinem", "seinem", "ihrem", "unserem", "eurem"):
                return {
                    "prep": target_prep,
                    "case": "Dativ",
                    "direction": "wo",
                    "role": "Konum / Bulunma",
                    "question": "Wo? (Nerede?)",
                    "badge": "📍 Dativ (Wo?)",
                    "hint": f"📍 İki Yönlü Edat ({target_prep} + {next_word}): Dativ · Konum / Bulunma (Wo?)"
                }
            # Akkusativ ipuçları: 'den', 'einen', 'meinen', 'deinen', 'seinen', 'ihren' (Eril Akkusativ)
            if next_word in ("den", "einen", "meinen", "deinen", "seinen", "ihren", "unseren", "euren"):
                return {
                    "prep": target_prep,
                    "case": "Akkusativ",
                    "direction": "wohin",
                    "role": "Hareket / Yönelme",
                    "question": "Wohin? (Nereye?)",
                    "badge": "🏃 Akkusativ (Wohin?)",
                    "hint": f"🏃 İki Yönlü Edat ({target_prep} + {next_word}): Akkusativ · Hareket / Yönelme (Wohin?)"
                }

    # 4. Edat bulunduysa ancak artikel belirsizse fiile bak (Fiil Hareketi mi Konumu mu bildiriyor?)
    if target_prep and s_lower:
        s_words = set(re.findall(r"\b[a-zäöüß]+\b", s_lower))
        if s_words & POSITION_VERBS:
            return {
                "prep": target_prep,
                "case": "Dativ",
                "direction": "wo",
                "role": "Konum / Bulunma",
                "question": "Wo? (Nerede?)",
                "badge": "📍 Dativ (Wo?)",
                "hint": f"📍 İki Yönlü Edat ({target_prep}): Dativ · Konum / Bulunma (Fiil durumu bildirir)"
            }
        elif s_words & DIRECTION_VERBS:
            return {
                "prep": target_prep,
                "case": "Akkusativ",
                "direction": "wohin",
                "role": "Hareket / Yönelme",
                "question": "Wohin? (Nereye?)",
                "badge": "🏃 Akkusativ (Wohin?)",
                "hint": f"🏃 İki Yönlü Edat ({target_prep}): Akkusativ · Hareket / Yönelme (Fiil yönelim bildirir)"
            }

    # 5. Sadece edatın kendisi arandıysa genel kuralı döndür
    if target_prep:
        return {
            "prep": target_prep,
            "case": "Akkusativ / Dativ",
            "direction": "wohin / wo",
            "role": "Çift Yönlü",
            "question": "Wohin? veya Wo?",
            "badge": "🔄 İki Yönlü Edat",
            "hint": f"🔄 İki Yönlü Edat ({target_prep}): Hareket/Yönelmede Akkusativ (Wohin?), Konum/Bulunmada Dativ (Wo?) alır."
        }

    return None
