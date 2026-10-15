"""
Almanca Deyimler, Kalıplar ve Birleşik Fiil Yapıları (Collocations & Redewendungen)
Birden fazla kelimeden oluşan, sözcük sözcük çevrildiğinde anlamını yitiren kalıpları tespit eder.
"""
import re
from typing import Dict, List, Optional, Any, Tuple

# Sık kullanılan kalıplar ve fonksiyonel fiil yapıları (Funktionsverbgefüge / Redewendungen)
COLLOCATIONS_DATA: List[Dict[str, Any]] = [
    {
        "phrase": "es geht um",
        "pattern": r"\b(es\s+(?:ging|geht|gehe)\s+um)\b",
        "words": {"es", "geht", "ging", "um"},
        "meaning_tr": "konu ... ile ilgili olmak / ... söz konusu olmak",
        "example_de": "Es geht um Leben und Tod.",
        "badge": "🧩 Kalıp: es geht um"
    },
    {
        "phrase": "auf jeden Fall",
        "pattern": r"\b(auf\s+jeden\s+fall)\b",
        "words": {"auf", "jeden", "fall"},
        "meaning_tr": "kesinlikle / her halükarda / mutlaka",
        "example_de": "Ich komme auf jeden Fall.",
        "badge": "🧩 Kalıp: auf jeden Fall"
    },
    {
        "phrase": "auf keinen Fall",
        "pattern": r"\b(auf\s+keinen\s+fall)\b",
        "words": {"auf", "keinen", "fall"},
        "meaning_tr": "asla / hiçbir şekilde / katiyen",
        "example_de": "Das darf auf keinen Fall passieren.",
        "badge": "🧩 Kalıp: auf keinen Fall"
    },
    {
        "phrase": "zur Verfügung stehen",
        "pattern": r"\b(?:zur\s+verf[üu]gung\s+(?:stehen|steht|stand|standen|gestanden))\b|\b(?:(?:stehen|steht|stand|standen|gestanden)\s+.*?zur\s+verf[üu]gung)\b",
        "words": {"verfügung", "verfuegung", "stehen", "steht", "stand", "standen", "gestanden"},
        "meaning_tr": "kullanıma hazır olmak / emre amade olmak",
        "example_de": "Die Mittel stehen zur Verfügung.",
        "badge": "🧩 Kalıp: zur Verfügung stehen"
    },
    {
        "phrase": "zur Verfügung stellen",
        "pattern": r"\b(?:zur\s+verf[üu]gung\s+(?:stellen|stellt|stellte|stellten|gestellt))\b|\b(?:(?:stellen|stellt|stellte|stellten|gestellt)\s+.*?zur\s+verf[üu]gung)\b",
        "words": {"verfügung", "verfuegung", "stellen", "stellt", "stellte", "stellten", "gestellt"},
        "meaning_tr": "tahsis etmek / kullanıma sunmak",
        "example_de": "Die Stadt stellt Räume zur Verfügung.",
        "badge": "🧩 Kalıp: zur Verfügung stellen"
    },
    {
        "phrase": "in Frage kommen",
        "pattern": r"\b(?:in\s+frage\s+(?:kommen|kommt|kam|kamen|gekommen))\b|\b(?:(?:kommen|kommt|kam|kamen|gekommen)\s+.*?in\s+frage)\b",
        "words": {"frage", "kommen", "kommt", "kam", "kamen", "gekommen"},
        "meaning_tr": "söz konusu olmak / ihtimal dahilinde olmak",
        "example_de": "Das kommt überhaupt nicht in Frage.",
        "badge": "🧩 Kalıp: in Frage kommen"
    },
    {
        "phrase": "Angst haben vor",
        "pattern": r"\b(?:(?:habe|hast|hat|haben|hatte|hatten)\s+.*?angst\s+vor)\b|\b(?:angst\s+vor\s+.*?(?:haben|hat|hast|hatte|hatten))\b|\b(?:angst\s+vor)\b",
        "words": {"angst", "vor", "haben", "hat", "hast", "hatte", "hatten"},
        "meaning_tr": "...-den korkmak / çekinmek",
        "example_de": "Er hat Angst vor Hunden.",
        "badge": "🧩 Kalıp: Angst haben vor"
    },
    {
        "phrase": "Bescheid wissen",
        "pattern": r"\b(?:bescheid\s+(?:wissen|wei[ßs]|wei[ßs]t|wusste|wussten|gewusst))\b|\b(?:(?:wissen|wei[ßs]|wei[ßs]t|wusste|wussten|gewusst)\s+.*?bescheid)\b",
        "words": {"bescheid", "wissen", "weiß", "weiss", "wusste", "wussten", "gewusst"},
        "meaning_tr": "haberi olmak / bilgi sahibi olmak",
        "example_de": "Ich weiß darüber Bescheid.",
        "badge": "🧩 Kalıp: Bescheid wissen"
    },
    {
        "phrase": "Bescheid geben",
        "pattern": r"\b(?:bescheid\s+(?:geben|gibt|gab|gaben|gegeben))\b|\b(?:(?:geben|gibt|gab|gaben|gib|gegeben)\s+.*?bescheid)\b",
        "words": {"bescheid", "geben", "gibt", "gab", "gaben", "gib", "gegeben"},
        "meaning_tr": "haber vermek / bilgilendirmek",
        "example_de": "Gib mir bitte Bescheid!",
        "badge": "🧩 Kalıp: Bescheid geben"
    },
    {
        "phrase": "eine Entscheidung treffen",
        "pattern": r"\b(?:(?:eine\s+)?(?:\w+\s+)?entscheidung\s+(?:treffen|trifft|traf|trafen|getroffen))\b|\b(?:(?:treffen|trifft|traf|trafen|getroffen)\s+.*?entscheidung)\b",
        "words": {"entscheidung", "treffen", "trifft", "traf", "trafen", "getroffen"},
        "meaning_tr": "karar vermek / karara varmak",
        "example_de": "Wir müssen jetzt eine Entscheidung treffen.",
        "badge": "🧩 Kalıp: eine Entscheidung treffen"
    },
    {
        "phrase": "Abschied nehmen",
        "pattern": r"\b(?:abschied\s+(?:nehmen|nimmt|nahm|nahmen|genommen))\b|\b(?:(?:nehmen|nimmt|nahm|nahmen|genommen)\s+.*?abschied)\b",
        "words": {"abschied", "nehmen", "nimmt", "nahm", "nahmen", "genommen"},
        "meaning_tr": "veda etmek / ayrılmak",
        "example_de": "Er nahm Abschied von seinen Freunden.",
        "badge": "🧩 Kalıp: Abschied nehmen"
    },
    {
        "phrase": "einen Eindruck machen",
        "pattern": r"\b(?:(?:einen\s+)?(?:\w+\s+)?eindruck\s+(?:machen|macht|machte|machten|gemacht))\b|\b(?:(?:machen|macht|machte|machten|gemacht)\s+.*?eindruck)\b",
        "words": {"eindruck", "machen", "macht", "machte", "machten", "gemacht"},
        "meaning_tr": "izlenim bırakmak / tesir etmek",
        "example_de": "Er macht einen sehr guten Eindruck.",
        "badge": "🧩 Kalıp: einen Eindruck machen"
    },
    {
        "phrase": "Rücksicht nehmen auf",
        "pattern": r"\b(?:r[üu]cksicht\s+(?:nehmen|nimmt|nahm|nahmen|genommen)\s+auf)\b|\b(?:(?:nehmen|nimmt|nahm|nahmen|genommen)\s+.*?r[üu]cksicht\s+auf)\b",
        "words": {"rücksicht", "ruecksicht", "nehmen", "auf", "nimmt", "nahm", "nahmen", "genommen"},
        "meaning_tr": "...-i dikkate almak / saygı göstermek",
        "example_de": "Nehmen Sie bitte Rücksicht auf die Nachbarn!",
        "badge": "🧩 Kalıp: Rücksicht nehmen auf"
    },
    {
        "phrase": "ums Leben kommen",
        "pattern": r"\b(?:ums\s+leben\s+(?:kommen|kommt|kam|kamen|gekommen))\b|\b(?:(?:kommen|kommt|kam|kamen|gekommen)\s+.*?ums\s+leben)\b",
        "words": {"leben", "kommen", "kommt", "kam", "kamen", "ums", "gekommen"},
        "meaning_tr": "hayatını kaybetmek / ölmek",
        "example_de": "Zwei Personen kamen ums Leben.",
        "badge": "🧩 Kalıp: ums Leben kommen"
    },
    {
        "phrase": "keine Ahnung",
        "pattern": r"\b(?:keine\s+ahnung)\b",
        "words": {"ahnung", "keine"},
        "meaning_tr": "hiçbir fikri olmamak / bilmiyorum",
        "example_de": "Ich habe keine Ahnung.",
        "badge": "🧩 Kalıp: keine Ahnung"
    },
    {
        "phrase": "auf den ersten Blick",
        "pattern": r"\b(?:auf\s+den\s+ersten\s+blick)\b",
        "words": {"blick", "ersten"},
        "meaning_tr": "ilk bakışta",
        "example_de": "Auf den ersten Blick sah alles gut aus.",
        "badge": "🧩 Kalıp: auf den ersten Blick"
    },
    {
        "phrase": "eine Rolle spielen",
        "pattern": r"\b(?:(?:eine\s+)?(?:\w+\s+)?rolle\s+(?:spielen|spielt|spielte|spielten|gespielt))\b|\b(?:(?:spielen|spielt|spielte|spielten|gespielt)\s+.*?rolle)\b",
        "words": {"rolle", "spielen", "spielt", "spielte", "spielten", "gespielt"},
        "meaning_tr": "rol oynamak / önemli olmak",
        "example_de": "Geld spielt keine Rolle.",
        "badge": "🧩 Kalıp: eine Rolle spielen"
    },
    {
        "phrase": "in Anspruch nehmen",
        "pattern": r"\b(?:in\s+anspruch\s+(?:nehmen|nimmt|nahm|nahmen|genommen))\b|\b(?:(?:nehmen|nimmt|nahm|nahmen|genommen)\s+.*?in\s+anspruch)\b",
        "words": {"anspruch", "nehmen", "nimmt", "nahm", "nahmen", "genommen"},
        "meaning_tr": "zamanını almak / talep etmek / yararlanmak",
        "example_de": "Das Projekt nimmt viel Zeit in Anspruch.",
        "badge": "🧩 Kalıp: in Anspruch nehmen"
    },
    {
        "phrase": "in Kauf nehmen",
        "pattern": r"\b(?:in\s+kauf\s+(?:nehmen|nimmt|nahm|nahmen|genommen))\b|\b(?:(?:nehmen|nimmt|nahm|nahmen|genommen)\s+.*?in\s+kauf)\b",
        "words": {"kauf", "nehmen", "nimmt", "nahm", "nahmen", "genommen"},
        "meaning_tr": "göze almak / razı olmak / katlanmak",
        "example_de": "Wir müssen das Risiko in Kauf nehmen.",
        "badge": "🧩 Kalıp: in Kauf nehmen"
    },
    {
        "phrase": "in der Lage sein",
        "pattern": r"\b(?:in\s+der\s+lage\s+(?:sein|ist|war|waren|sind|bist|seid|gewesen))\b|\b(?:(?:sein|ist|war|waren|sind|bist|seid)\s+.*?in\s+der\s+lage)\b",
        "words": {"lage", "sein", "ist", "war", "waren", "sind", "bist"},
        "meaning_tr": "yapabilecek durumda olmak / gücü yetmek",
        "example_de": "Er ist nicht in der Lage zu arbeiten.",
        "badge": "🧩 Kalıp: in der Lage sein"
    },
    {
        "phrase": "sich Sorgen machen",
        "pattern": r"\b(?:sorgen\s+(?:machen|macht|machte|machten|gemacht))\b|\b(?:(?:machen|macht|machte|machten|mach|gemacht)\s+.*?sorgen)\b",
        "words": {"sorgen", "machen", "macht", "machte", "machten", "mach"},
        "meaning_tr": "endişelenmek / dert etmek",
        "example_de": "Mach dir keine Sorgen!",
        "badge": "🧩 Kalıp: sich Sorgen machen"
    },
    {
        "phrase": "zu Ende gehen",
        "pattern": r"\b(?:zu\s+ende\s+(?:gehen|geht|ging|gingen|gegangen))\b|\b(?:(?:gehen|geht|ging|gingen|gegangen)\s+.*?zu\s+ende)\b",
        "words": {"ende", "gehen", "geht", "ging", "gingen", "gegangen"},
        "meaning_tr": "sona ermek / bitmek",
        "example_de": "Der Sommer geht zu Ende.",
        "badge": "🧩 Kalıp: zu Ende gehen"
    },
    {
        "phrase": "vor allem",
        "pattern": r"\b(?:vor\s+allem)\b",
        "words": {"vor", "allem"},
        "meaning_tr": "özellikle / her şeyden önce",
        "example_de": "Er liebt Musik, vor allem Jazz.",
        "badge": "🧩 Kalıp: vor allem"
    },
    {
        "phrase": "im Grunde genommen",
        "pattern": r"\b(?:im\s+grunde\s+genommen)\b",
        "words": {"grunde", "genommen"},
        "meaning_tr": "esasında / temelde",
        "example_de": "Im Grunde genommen hat er recht.",
        "badge": "🧩 Kalıp: im Grunde genommen"
    },
    {
        "phrase": "Recht haben",
        "pattern": r"\b(?:recht\s+(?:haben|hat|hast|hatte|hatten))\b|\b(?:(?:haben|hast|hat|hatte|hatten)\s+.*?recht)\b",
        "words": {"recht", "haben", "hat", "hast", "hatte", "hatten"},
        "meaning_tr": "haklı olmak",
        "example_de": "Du hast vollkommen Recht.",
        "badge": "🧩 Kalıp: Recht haben"
    },
    {
        "phrase": "in Ruhe lassen",
        "pattern": r"\b(?:in\s+ruhe\s+(?:lassen|l[äa]sst|lie[ßs]|lie[ßs]en|gelassen))\b|\b(?:(?:lassen|l[äa]sst|lie[ßs]|lie[ßs]en|lass|gelassen)\s+.*?in\s+ruhe)\b",
        "words": {"ruhe", "lassen", "lässt", "laesst", "lass", "ließ", "liess", "gelassen"},
        "meaning_tr": "rahat bırakmak",
        "example_de": "Lass mich bitte in Ruhe!",
        "badge": "🧩 Kalıp: in Ruhe lassen"
    },
    {
        "phrase": "Schluss machen",
        "pattern": r"\b(?:schluss\s+(?:machen|macht|machte|machten|gemacht))\b|\b(?:(?:machen|macht|machte|machten|mach|gemacht)\s+.*?schluss)\b",
        "words": {"schluss", "machen", "macht", "machte", "machten", "mach", "gemacht"},
        "meaning_tr": "ilişkiyi bitirmek / noktalamak",
        "example_de": "Sie hat mit ihm Schluss gemacht.",
        "badge": "🧩 Kalıp: Schluss machen"
    }
]


def find_collocation(word: str, sentence: str = "") -> Optional[Dict[str, Any]]:
    """
    Hedef kelime veya cümle içindeki deyim/kalıbı (Collocation) tespit eder.
    Hover edilen kelime kalıbın bir parçasıysa veya doğrudan kalıp aranmışsa eşleştirir.
    """
    w_clean = (word or "").strip().lower()
    s_clean = (sentence or "").strip()
    s_lower = s_clean.lower()

    # 1. Doğrudan kelime/öbek eşleşmesi (kullanıcı birden fazla kelime seçmişse)
    for item in COLLOCATIONS_DATA:
        if w_clean == item["phrase"].lower():
            return {
                "phrase": item["phrase"],
                "meaning_tr": item["meaning_tr"],
                "example_de": item["example_de"],
                "badge": item["badge"],
                "hint": f"{item['badge']} → {item['meaning_tr']}"
            }

    # 2. Cümle içinde kalıp arama
    if s_lower:
        for item in COLLOCATIONS_DATA:
            pattern = item["pattern"]
            if re.search(pattern, s_lower, re.IGNORECASE):
                # Eşleşti; eğer bir hedef kelime verilmişse, hedef kelime bu kalıbın parçası mı kontrol et
                if not w_clean or w_clean in item["words"] or any(w in w_clean for w in item["words"]):
                    return {
                        "phrase": item["phrase"],
                        "meaning_tr": item["meaning_tr"],
                        "example_de": item["example_de"],
                        "badge": item["badge"],
                        "hint": f"{item['badge']} → {item['meaning_tr']}"
                    }

    return None
