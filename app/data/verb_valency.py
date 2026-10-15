"""
Almanca Fiil İstemleri Veritabanı (Rektion der Verben)
Almancada sık kullanılan fiillerin aldıkları edatlar (Präpositionen) ve haller (Kasus: Akkusativ / Dativ).
"""
import re
from typing import Dict, List, Optional, Any, Tuple

# Sık kullanılan ~100 fiil istemi (A1-B2 Goethe / Duden standartları)
# Yapı: verb -> liste [ {"prep": str, "case": str, "reflexive": bool, "meaning_tr": str, "sample": str} ]
VERB_VALENCY_DATA: Dict[str, List[Dict[str, Any]]] = {
    "warten": [
        {"prep": "auf", "case": "Akkusativ", "reflexive": False, "meaning_tr": "...-i / ...-e beklemek", "sample": "Ich warte auf den Bus."}
    ],
    "denken": [
        {"prep": "an", "case": "Akkusativ", "reflexive": False, "meaning_tr": "...-i düşünmek / aklına gelmek", "sample": "Ich denke an dich."}
    ],
    "nachdenken": [
        {"prep": "über", "case": "Akkusativ", "reflexive": False, "meaning_tr": "... hakkında enine boyuna düşünmek", "sample": "Ich denke über das Problem nach."}
    ],
    "freuen": [
        {"prep": "auf", "case": "Akkusativ", "reflexive": True, "meaning_tr": "(gelecek bir şeye) sabırsızlanmak / sevinmek", "sample": "Ich freue mich auf den Urlaub."},
        {"prep": "über", "case": "Akkusativ", "reflexive": True, "meaning_tr": "(olmuş/mevcut bir şeye) sevinmek", "sample": "Ich freue mich über das Geschenk."}
    ],
    "interessieren": [
        {"prep": "für", "case": "Akkusativ", "reflexive": True, "meaning_tr": "... ile ilgilenmek", "sample": "Er interessiert sich für Musik."}
    ],
    "teilnehmen": [
        {"prep": "an", "case": "Dativ", "reflexive": False, "meaning_tr": "...-e katılmak", "sample": "Sie nimmt an der Konferenz teil."}
    ],
    "abhängen": [
        {"prep": "von", "case": "Dativ", "reflexive": False, "meaning_tr": "...-e bağlı olmak", "sample": "Das hängt vom Wetter ab."}
    ],
    "achten": [
        {"prep": "auf", "case": "Akkusativ", "reflexive": False, "meaning_tr": "...-e dikkat etmek", "sample": "Achte auf den Verkehr!"}
    ],
    "anfangen": [
        {"prep": "mit", "case": "Dativ", "reflexive": False, "meaning_tr": "...-e başlamak", "sample": "Wir fangen mit der Arbeit an."}
    ],
    "aufhören": [
        {"prep": "mit", "case": "Dativ", "reflexive": False, "meaning_tr": "...-i bırakmak / son vermek", "sample": "Hör mit dem Rauchen auf!"}
    ],
    "ärgern": [
        {"prep": "über", "case": "Akkusativ", "reflexive": True, "meaning_tr": "...-e kızmak / sinirlenmek", "sample": "Er ärgert sich über den Stau."}
    ],
    "bedanken": [
        {"prep": "bei", "case": "Dativ", "reflexive": True, "meaning_tr": "birine teşekkür etmek", "sample": "Ich bedanke mich bei Ihnen."},
        {"prep": "für", "case": "Akkusativ", "reflexive": True, "meaning_tr": "bir şey için teşekkür etmek", "sample": "Ich bedanke mich für Ihre Hilfe."}
    ],
    "bitten": [
        {"prep": "um", "case": "Akkusativ", "reflexive": False, "meaning_tr": "... rica etmek / istemek", "sample": "Darf ich Sie um Hilfe bitten?"}
    ],
    "danken": [
        {"prep": "für", "case": "Akkusativ", "reflexive": False, "meaning_tr": "... için teşekkür etmek", "sample": "Ich danke dir für alles."}
    ],
    "einladen": [
        {"prep": "zu", "case": "Dativ", "reflexive": False, "meaning_tr": "...-e davet etmek", "sample": "Er lädt uns zur Party ein."}
    ],
    "entschuldigen": [
        {"prep": "bei", "case": "Dativ", "reflexive": True, "meaning_tr": "birinden özür dilemek", "sample": "Ich entschuldige mich bei dir."},
        {"prep": "für", "case": "Akkusativ", "reflexive": True, "meaning_tr": "bir şey için özür dilemek", "sample": "Er entschuldigt sich für den Fehler."}
    ],
    "erinnern": [
        {"prep": "an", "case": "Akkusativ", "reflexive": True, "meaning_tr": "...-i hatırlamak", "sample": "Erinnerst du dich an mich?"}
    ],
    "erkundigen": [
        {"prep": "nach", "case": "Dativ", "reflexive": True, "meaning_tr": "... hakkında bilgi almak / sormak", "sample": "Ich erkundige mich nach dem Weg."}
    ],
    "erzählen": [
        {"prep": "von", "case": "Dativ", "reflexive": False, "meaning_tr": "...-den bahsetmek / anlatmak", "sample": "Er erzählt von seiner Reise."},
        {"prep": "über", "case": "Akkusativ", "reflexive": False, "meaning_tr": "... hakkında anlatmak", "sample": "Sie erzählt über ihren Alltag."}
    ],
    "fragen": [
        {"prep": "nach", "case": "Dativ", "reflexive": False, "meaning_tr": "...-i sormak", "sample": "Der Tourist fragt nach dem Bahnhof."}
    ],
    "gehören": [
        {"prep": "zu", "case": "Dativ", "reflexive": False, "meaning_tr": "...-e ait olmak / parçası olmak", "sample": "Das gehört zu meinen Aufgaben."}
    ],
    "gewöhnen": [
        {"prep": "an", "case": "Akkusativ", "reflexive": True, "meaning_tr": "...-e alışmak", "sample": "Ich gewöhne mich an die Kälte."}
    ],
    "glauben": [
        {"prep": "an", "case": "Akkusativ", "reflexive": False, "meaning_tr": "...-e inanmak", "sample": "Glaubst du an Wunder?"}
    ],
    "gratulieren": [
        {"prep": "zu", "case": "Dativ", "reflexive": False, "meaning_tr": "...-i tebrik etmek / kutlamak", "sample": "Ich gratuliere dir zum Geburtstag."}
    ],
    "hoffen": [
        {"prep": "auf", "case": "Akkusativ", "reflexive": False, "meaning_tr": "...-i ummak / ümit etmek", "sample": "Wir hoffen auf besseres Wetter."}
    ],
    "handeln": [
        {"prep": "von", "case": "Dativ", "reflexive": False, "meaning_tr": "... hakkında olmak / konu etmek", "sample": "Das Buch handelt von der Liebe."},
        {"prep": "um", "case": "Akkusativ", "reflexive": True, "meaning_tr": "söz konusu olmak (es handelt sich um)", "sample": "Es handelt sich um ein Missverständnis."}
    ],
    "helfen": [
        {"prep": "bei", "case": "Dativ", "reflexive": False, "meaning_tr": "... konusunda yardım etmek (+ Dativ şahıs)", "sample": "Kannst du mir beim Kochen helfen?"}
    ],
    "kümmern": [
        {"prep": "um", "case": "Akkusativ", "reflexive": True, "meaning_tr": "... ile ilgilenmek / üstlenmek", "sample": "Ich kümmere mich um die Kinder."}
    ],
    "leiden": [
        {"prep": "an", "case": "Dativ", "reflexive": False, "meaning_tr": "(bir hastalıktan) muzdarip olmak", "sample": "Er leidet an einer Allergie."},
        {"prep": "unter", "case": "Dativ", "reflexive": False, "meaning_tr": "(bir durumdan/baskıdan) sıkıntı çekmek", "sample": "Sie leidet unter dem Stress."}
    ],
    "passen": [
        {"prep": "zu", "case": "Dativ", "reflexive": False, "meaning_tr": "...-e uymak / yakışmak", "sample": "Das Kleid passt gut zu dir."}
    ],
    "rechnen": [
        {"prep": "mit", "case": "Dativ", "reflexive": False, "meaning_tr": "...-i hesaba katmak / beklemek", "sample": "Wir rechnen mit Verspätungen."}
    ],
    "riechen": [
        {"prep": "nach", "case": "Dativ", "reflexive": False, "meaning_tr": "... gibi kokmak", "sample": "Es riecht nach frischem Kaffee."}
    ],
    "schmecken": [
        {"prep": "nach", "case": "Dativ", "reflexive": False, "meaning_tr": "... tadı gelmek", "sample": "Die Suppe schmeckt nach Knoblauch."}
    ],
    "schützen": [
        {"prep": "vor", "case": "Dativ", "reflexive": False, "meaning_tr": "...-den korumak", "sample": "Die Sonnencreme schützt vor Sonnenbrand."}
    ],
    "sorgen": [
        {"prep": "für", "case": "Akkusativ", "reflexive": False, "meaning_tr": "...-i sağlamak / bakımını üstlenmek", "sample": "Die Eltern sorgen für ihre Kinder."},
        {"prep": "um", "case": "Akkusativ", "reflexive": True, "meaning_tr": "... için endişelenmek", "sample": "Ich sorge mich um seine Gesundheit."}
    ],
    "sprechen": [
        {"prep": "mit", "case": "Dativ", "reflexive": False, "meaning_tr": "biriyle konuşmak", "sample": "Ich spreche mit meinem Chef."},
        {"prep": "über", "case": "Akkusativ", "reflexive": False, "meaning_tr": "bir şey hakkında konuşmak", "sample": "Wir sprechen über den Plan."}
    ],
    "streiten": [
        {"prep": "mit", "case": "Dativ", "reflexive": True, "meaning_tr": "biriyle tartışmak / kavga etmek", "sample": "Er streitet sich mit seinem Bruder."},
        {"prep": "über", "case": "Akkusativ", "reflexive": True, "meaning_tr": "bir konu üzerine tartışmak", "sample": "Sie streiten über Geld."}
    ],
    "suchen": [
        {"prep": "nach", "case": "Dativ", "reflexive": False, "meaning_tr": "...-i aramak", "sample": "Die Polizei sucht nach dem Täter."}
    ],
    "träumen": [
        {"prep": "von", "case": "Dativ", "reflexive": False, "meaning_tr": "...-i hayal etmek / rüyasını görmek", "sample": "Ich träume von einem Urlaub."}
    ],
    "vergleichen": [
        {"prep": "mit", "case": "Dativ", "reflexive": False, "meaning_tr": "... ile karşılaştırmak", "sample": "Vergleiche dich nicht mit anderen."}
    ],
    "verlassen": [
        {"prep": "auf", "case": "Akkusativ", "reflexive": True, "meaning_tr": "...-e güvenmek / bel bağlamak", "sample": "Du kannst dich auf mich verlassen."}
    ],
    "verlieben": [
        {"prep": "in", "case": "Akkusativ", "reflexive": True, "meaning_tr": "...-e aşık olmak", "sample": "Er hat sich in sie verliebt."}
    ],
    "verzichten": [
        {"prep": "auf", "case": "Akkusativ", "reflexive": False, "meaning_tr": "...-den vazgeçmek / feragat etmek", "sample": "Ich verzichte auf Zucker."}
    ],
    "warnen": [
        {"prep": "vor", "case": "Dativ", "reflexive": False, "meaning_tr": "... konusunda uyarmak", "sample": "Die Behörden warnen vor Sturm."}
    ],
    "zweifeln": [
        {"prep": "an", "case": "Dativ", "reflexive": False, "meaning_tr": "...-den şüphe etmek", "sample": "Er zweifelt an der Entscheidung."}
    ],
    "bestehen": [
        {"prep": "aus", "case": "Dativ", "reflexive": False, "meaning_tr": "...-den oluşmak", "sample": "Das Team besteht aus fünf Personen."},
        {"prep": "auf", "case": "Dativ", "reflexive": False, "meaning_tr": "... konusunda ısrar etmek", "sample": "Er besteht auf seinem Recht."}
    ],
    "bewerben": [
        {"prep": "um", "case": "Akkusativ", "reflexive": True, "meaning_tr": "(bir işe/pozisyona) başvurmak", "sample": "Ich bewerbe mich um die Stelle."},
        {"prep": "bei", "case": "Dativ", "reflexive": True, "meaning_tr": "(bir şirkete/kuruma) başvurmak", "sample": "Sie bewirbt sich bei Siemens."}
    ],
    "beschäftigen": [
        {"prep": "mit", "case": "Dativ", "reflexive": True, "meaning_tr": "... ile meşgul olmak / uğraşmak", "sample": "Ich beschäftige mich mit deutscher Grammatik."}
    ],
    "konzentrieren": [
        {"prep": "auf", "case": "Akkusativ", "reflexive": True, "meaning_tr": "...-e odaklanmak / konsantre olmak", "sample": "Konzentriere dich auf die Prüfung!"}
    ],
    "anpassen": [
        {"prep": "an", "case": "Akkusativ", "reflexive": True, "meaning_tr": "...-e uyum sağlamak", "sample": "Wir müssen uns an die Situation anpassen."}
    ],
    "sterben": [
        {"prep": "an", "case": "Dativ", "reflexive": False, "meaning_tr": "...-den ölmek (hastalık)", "sample": "Er starb an Krebs."}
    ]
}


def find_verb_valency(verb: str, sentence: str = "") -> Optional[Dict[str, Any]]:
    """
    Verilen fiil kökü veya mastarı için fiil istemi (edat ve hal) bilgisini döndürür.
    Eğer bağlam cümlesi verilmişse, cümledeki edatı tespit ederek en uygun valency'yi seçer.
    """
    if not verb:
        return None

    v_clean = verb.strip().lower()
    # 'sich' önekini ayır
    if v_clean.startswith("sich "):
        v_clean = v_clean[5:].strip()

    entries = VERB_VALENCY_DATA.get(v_clean)
    if not entries:
        return None

    sentence_lower = (sentence or "").lower()

    # 1. Cümlede geçen edatı eşleştir
    matched_entry = None
    if sentence_lower:
        words_in_sent = re.findall(r"\b[a-zäöüß]+\b", sentence_lower)
        for entry in entries:
            prep = entry["prep"].lower()
            # Edat tam kelime olarak cümlede var mı? (örn: 'auf', 'für', 'an')
            # Ya da kaynaşmış biçimi mi? ('am' -> 'an', 'im' -> 'in', 'zum' -> 'zu', 'zur' -> 'zu', 'vom' -> 'von', 'beim' -> 'bei')
            prep_variants = {prep}
            if prep == "an":
                prep_variants.update(["am", "ans"])
            elif prep == "in":
                prep_variants.update(["im", "ins"])
            elif prep == "zu":
                prep_variants.update(["zum", "zur"])
            elif prep == "von":
                prep_variants.update(["vom"])
            elif prep == "bei":
                prep_variants.update(["beim"])
            elif prep == "auf":
                prep_variants.update(["aufs"])

            if any(var in words_in_sent for var in prep_variants):
                matched_entry = entry
                break

    # Eşleşen yoksa ilk (varsayılan) girdiyi kullan
    if not matched_entry:
        matched_entry = entries[0]

    refl_str = "sich " if matched_entry.get("reflexive") else ""
    prep = matched_entry["prep"]
    case = matched_entry["case"]
    meaning = matched_entry["meaning_tr"]

    badge_text = f"🎯 {prep} + {case}"
    hint_line = f"🎯 İstem: {refl_str}{v_clean} + {prep} + {case} ({meaning})"

    return {
        "verb": v_clean,
        "reflexive": matched_entry.get("reflexive", False),
        "preposition": prep,
        "case": case,
        "meaning_tr": meaning,
        "sample": matched_entry.get("sample", ""),
        "badge": badge_text,
        "formatted_hint": hint_line
    }
