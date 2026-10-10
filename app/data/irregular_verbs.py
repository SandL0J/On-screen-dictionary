"""
Almanca Güçlü ve Düzensiz Fiiller Veritabanı (German Irregular Verbs Database)
Veri kaynağı: Goethe / Duden A1-C1 standart düzensiz ve güçlü fiil çekim tabloları.
Ters indeks (REVERSE_IRREGULAR_INDEX) ile çekimli biçimlerden sözlük biçimine (mastar/lemma)
yüksek güvenirlikle (confidence='high') çözümleme sağlar.
"""

from typing import Dict, Tuple, Optional, List

# Format:
# infinitive: (praeteritum_stem, partizip2, {irregular_praesens_form: form_label})
# praeteritum_stem üzerinden standart kişi çekimleri (ich/er, du, wir, ihr, sie) otomatik üretilir.
IRREGULAR_VERBS_DATA: Dict[str, Tuple[str, str, Dict[str, str]]] = {
    # Yardımcı Fiiller (Hilfsverben)
    "sein": ("war", "gewesen", {
        "bin": "Präsens (ich)",
        "bist": "Präsens (du)",
        "ist": "Präsens (er/sie/es)",
        "sind": "Präsens (wir/sie)",
        "seid": "Präsens (ihr)",
        "sei": "Imperativ / Konjunktiv I",
        "seien": "Konjunktiv I",
        "seist": "Konjunktiv I",
        "wäre": "Konjunktiv II",
        "wärest": "Konjunktiv II",
        "wären": "Konjunktiv II",
        "wäret": "Konjunktiv II",
    }),
    "haben": ("hatte", "gehabt", {
        "habe": "Präsens (ich)",
        "hast": "Präsens (du)",
        "hat": "Präsens (er/sie/es)",
        "habt": "Präsens (ihr)",
        "hätte": "Konjunktiv II",
        "hättest": "Konjunktiv II",
        "hätten": "Konjunktiv II",
        "hättet": "Konjunktiv II",
    }),
    "werden": ("wurde", "geworden", {
        "werde": "Präsens (ich)",
        "wirst": "Präsens (du)",
        "wird": "Präsens (er/sie/es)",
        "werdet": "Präsens (ihr)",
        "würde": "Konjunktiv II",
        "würdest": "Konjunktiv II",
        "würden": "Konjunktiv II",
        "würdet": "Konjunktiv II",
        "worden": "Partizip II (Passiv)",
    }),
    "wissen": ("wusste", "gewusst", {
        "weiß": "Präsens (ich/er/sie/es)",
        "weißt": "Präsens (du)",
        "wisst": "Präsens (ihr)",
        "wüsste": "Konjunktiv II",
        "wüsstest": "Konjunktiv II",
        "wüssten": "Konjunktiv II",
        "wüsstet": "Konjunktiv II",
    }),
    "tun": ("tat", "getan", {
        "tue": "Präsens (ich)",
        "tust": "Präsens (du)",
        "tut": "Präsens (er/sie/es)",
    }),

    # Modal Fiiller (Modalverben)
    "können": ("konnte", "gekonnt", {
        "kann": "Präsens (ich/er/sie/es)",
        "kannst": "Präsens (du)",
        "könnt": "Präsens (ihr)",
        "könnte": "Konjunktiv II",
        "könntest": "Konjunktiv II",
        "könnten": "Konjunktiv II",
        "könntet": "Konjunktiv II",
    }),
    "müssen": ("musste", "gemusst", {
        "muss": "Präsens (ich/er/sie/es)",
        "musst": "Präsens (du)",
        "müsst": "Präsens (ihr)",
        "müsste": "Konjunktiv II",
        "müsstest": "Konjunktiv II",
        "müssten": "Konjunktiv II",
        "müsstet": "Konjunktiv II",
    }),
    "wollen": ("wollte", "gewollt", {
        "will": "Präsens (ich/er/sie/es)",
        "willst": "Präsens (du)",
        "wollt": "Präsens (ihr)",
    }),
    "sollen": ("sollte", "gesollt", {
        "soll": "Präsens (ich/er/sie/es)",
        "sollst": "Präsens (du)",
        "sollt": "Präsens (ihr)",
    }),
    "dürfen": ("durfte", "gedurft", {
        "darf": "Präsens (ich/er/sie/es)",
        "darfst": "Präsens (du)",
        "dürft": "Präsens (ihr)",
        "dürfte": "Konjunktiv II",
        "dürftest": "Konjunktiv II",
        "dürften": "Konjunktiv II",
        "dürftet": "Konjunktiv II",
    }),
    "mögen": ("mochte", "gemocht", {
        "mag": "Präsens (ich/er/sie/es)",
        "magst": "Präsens (du)",
        "mögt": "Präsens (ihr)",
        "möchte": "Konjunktiv II (möchten)",
        "möchtest": "Konjunktiv II (möchten)",
        "möchten": "Konjunktiv II (möchten)",
        "möchtet": "Konjunktiv II (möchten)",
    }),

    # Yaygın Düzensiz ve Güçlü Fiiller
    "backen": ("backte", "gebacken", {"bäckst": "Präsens (du)", "bäckt": "Präsens (er/sie/es)"}),
    "befehlen": ("befahl", "befohlen", {"befiehlst": "Präsens (du)", "befiehlt": "Präsens (er/sie/es)", "befiehl": "Imperativ"}),
    "beginnen": ("begann", "begonnen", {}),
    "beißen": ("biss", "gebissen", {}),
    "bergen": ("barg", "geborgen", {"birgst": "Präsens (du)", "birgt": "Präsens (er/sie/es)", "birg": "Imperativ"}),
    "bersten": ("barst", "geborsten", {"birst": "Präsens (du/er/sie/es)"}),
    "betrügen": ("betrog", "betrogen", {}),
    "bewegen": ("bewog", "bewogen", {}),
    "biegen": ("bog", "gebogen", {}),
    "bieten": ("bot", "geboten", {}),
    "binden": ("band", "gebunden", {}),
    "bitten": ("bat", "gebeten", {}),
    "blasen": ("blies", "geblasen", {"bläst": "Präsens (du/er/sie/es)"}),
    "bleiben": ("blieb", "geblieben", {}),
    "braten": ("briet", "gebraten", {"brätst": "Präsens (du)", "brät": "Präsens (er/sie/es)"}),
    "brechen": ("brach", "gebrochen", {"brichst": "Präsens (du)", "bricht": "Präsens (er/sie/es)", "brich": "Imperativ"}),
    "brennen": ("brannte", "gebrannt", {}),
    "bringen": ("brachte", "gebracht", {}),
    "denken": ("dachte", "gedacht", {}),
    "dringen": ("drang", "gedrungen", {}),
    "empfangen": ("empfing", "empfangen", {"empfängst": "Präsens (du)", "empfängt": "Präsens (er/sie/es)"}),
    "empfehlen": ("empfahl", "empfohlen", {"empfiehlst": "Präsens (du)", "empfiehlt": "Präsens (er/sie/es)", "empfiehl": "Imperativ"}),
    "empfinden": ("empfand", "empfunden", {}),
    "erschrecken": ("erschrak", "erschrocken", {"erschrickst": "Präsens (du)", "erschrickt": "Präsens (er/sie/es)"}),
    "essen": ("aß", "gegessen", {"isst": "Präsens (du/er/sie/es)", "iss": "Imperativ"}),
    "fahren": ("fuhr", "gefahren", {"fährst": "Präsens (du)", "fährt": "Präsens (er/sie/es)"}),
    "fallen": ("fiel", "gefallen", {"fällst": "Präsens (du)", "fällt": "Präsens (er/sie/es)"}),
    "fangen": ("fing", "gefangen", {"fängst": "Präsens (du)", "fängt": "Präsens (er/sie/es)"}),
    "fechten": ("focht", "gefochten", {"fichtst": "Präsens (du)", "ficht": "Präsens (er/sie/es)"}),
    "finden": ("fand", "gefunden", {}),
    "flechten": ("flocht", "geflochten", {"flichst": "Präsens (du)", "flicht": "Präsens (er/sie/es)"}),
    "fliegen": ("flog", "geflogen", {}),
    "fliehen": ("floh", "geflohen", {}),
    "fließen": ("floss", "geflossen", {}),
    "fressen": ("fraß", "gefressen", {"frisst": "Präsens (du/er/sie/es)", "friss": "Imperativ"}),
    "frieren": ("fror", "gefroren", {}),
    "gebären": ("gebar", "geboren", {"gebierst": "Präsens (du)", "gebiert": "Präsens (er/sie/es)"}),
    "geben": ("gab", "gegeben", {"gibst": "Präsens (du)", "gibt": "Präsens (er/sie/es)", "gib": "Imperativ"}),
    "gedeihen": ("gedieh", "gediehen", {}),
    "gehen": ("ging", "gegangen", {}),
    "gelingen": ("gelang", "gelungen", {}),
    "gelten": ("galt", "gegolten", {"giltst": "Präsens (du)", "gilt": "Präsens (er/sie/es)"}),
    "genesen": ("genas", "genesen", {}),
    "genießen": ("genoss", "genossen", {}),
    "geschehen": ("geschah", "geschehen", {"geschieht": "Präsens (er/sie/es)"}),
    "gewinnen": ("gewann", "gewonnen", {}),
    "gießen": ("goss", "gegossen", {}),
    "gleichen": ("glich", "geglichen", {}),
    "gleiten": ("glitt", "geglitten", {}),
    "graben": ("grub", "gegraben", {"gräbst": "Präsens (du)", "gräbt": "Präsens (er/sie/es)"}),
    "greifen": ("griff", "gegriffen", {}),
    "halten": ("hielt", "gehalten", {"hältst": "Präsens (du)", "hält": "Präsens (er/sie/es)"}),
    "hängen": ("hing", "gehangen", {}),
    "heben": ("hob", "gehoben", {}),
    "heißen": ("hieß", "geheißen", {"heißt": "Präsens (du/er/sie/es)"}),
    "helfen": ("half", "geholfen", {"hilfst": "Präsens (du)", "hilft": "Präsens (er/sie/es)", "hilf": "Imperativ"}),
    "kennen": ("kannte", "gekannt", {}),
    "klingen": ("klang", "geklungen", {}),
    "kneifen": ("kniff", "gekniffen", {}),
    "kommen": ("kam", "gekommen", {}),
    "kriechen": ("kroch", "gekrochen", {}),
    "laden": ("lud", "geladen", {"lädst": "Präsens (du)", "lädt": "Präsens (er/sie/es)"}),
    "lassen": ("ließ", "gelassen", {"lässt": "Präsens (du/er/sie/es)"}),
    "laufen": ("lief", "gelaufen", {"läufst": "Präsens (du)", "läuft": "Präsens (er/sie/es)"}),
    "leiden": ("litt", "gelitten", {}),
    "leihen": ("lieh", "geliehen", {}),
    "lesen": ("las", "gelesen", {"liest": "Präsens (du/er/sie/es)", "lies": "Imperativ"}),
    "liegen": ("lag", "gelegen", {}),
    "lügen": ("log", "gelogen", {}),
    "meiden": ("mied", "gemieden", {}),
    "messen": ("maß", "gemessen", {"misst": "Präsens (du/er/sie/es)", "miss": "Imperativ"}),
    "misslingen": ("misslang", "misslungen", {}),
    "nehmen": ("nahm", "genommen", {"nimmst": "Präsens (du)", "nimmt": "Präsens (er/sie/es)", "nimm": "Imperativ"}),
    "nennen": ("nannte", "genannt", {}),
    "pfeifen": ("pfiff", "gepfiffen", {}),
    "preisen": ("pries", "gepriesen", {}),
    "quellen": ("quoll", "gequollen", {"quillst": "Präsens (du)", "quillt": "Präsens (er/sie/es)"}),
    "raten": ("riet", "geraten", {"rätst": "Präsens (du)", "rät": "Präsens (er/sie/es)"}),
    "reiben": ("rieb", "gerieben", {}),
    "reißen": ("riss", "gerissen", {}),
    "reiten": ("ritt", "geritten", {}),
    "rennen": ("rannte", "gerannt", {}),
    "riechen": ("roch", "gerochen", {}),
    "ringen": ("rang", "gerungen", {}),
    "rinnen": ("rann", "geronnen", {}),
    "rufen": ("rief", "gerufen", {}),
    "schaffen": ("schuf", "geschaffen", {}),
    "scheiden": ("schied", "geschieden", {}),
    "scheinen": ("schien", "geschienen", {}),
    "scheißen": ("schiss", "geschissen", {}),
    "schelten": ("schalt", "gescholten", {"schiltst": "Präsens (du)", "schilt": "Präsens (er/sie/es)"}),
    "scheren": ("schor", "geschoren", {}),
    "schieben": ("schob", "geschoben", {}),
    "schießen": ("schoss", "geschossen", {}),
    "schlafen": ("schlief", "geschlafen", {"schläfst": "Präsens (du)", "schläft": "Präsens (er/sie/es)"}),
    "schlagen": ("schlug", "geschlagen", {"schlägst": "Präsens (du)", "schlägt": "Präsens (er/sie/es)"}),
    "schleichen": ("schlich", "geschlichen", {}),
    "schleifen": ("schliff", "geschliffen", {}),
    "schließen": ("schloss", "geschlossen", {}),
    "schlingen": ("schlang", "geschlungen", {}),
    "schmeißen": ("schmiss", "geschmissen", {}),
    "schmelzen": ("schmolz", "geschmolzen", {"schmilzt": "Präsens (du/er/sie/es)"}),
    "schneiden": ("schnitt", "geschnitten", {}),
    "schreiben": ("schrieb", "geschrieben", {}),
    "schreien": ("schrie", "geschrien", {}),
    "schreiten": ("schritt", "geschritten", {}),
    "schweigen": ("schwieg", "geschwiegen", {}),
    "schwellen": ("schwoll", "geschwollen", {"schwillst": "Präsens (du)", "schwillt": "Präsens (er/sie/es)"}),
    "schwimmen": ("schwamm", "geschwommen", {}),
    "schwinden": ("schwand", "geschwunden", {}),
    "schwingen": ("schwang", "geschwungen", {}),
    "schwören": ("schwor", "geschworen", {}),
    "sehen": ("sah", "gesehen", {"siehst": "Präsens (du)", "sieht": "Präsens (er/sie/es)", "sieh": "Imperativ"}),
    "senden": ("sandte", "gesandt", {}),
    "sieden": ("sott", "gesotten", {}),
    "singen": ("sang", "gesungen", {}),
    "sinken": ("sank", "gesunken", {}),
    "sinnen": ("sann", "gesonnen", {}),
    "sitzen": ("saß", "gesessen", {}),
    "spalten": ("spaltete", "gespalten", {}),
    "speien": ("spie", "gespien", {}),
    "spinnen": ("spann", "gesponnen", {}),
    "sprechen": ("sprach", "gesprochen", {"sprichst": "Präsens (du)", "spricht": "Präsens (er/sie/es)", "sprich": "Imperativ"}),
    "sprießen": ("spross", "gesprossen", {}),
    "springen": ("sprang", "gesprungen", {}),
    "stechen": ("stach", "gestochen", {"stichst": "Präsens (du)", "sticht": "Präsens (er/sie/es)"}),
    "stehen": ("stand", "gestanden", {}),
    "stehlen": ("stahl", "gestohlen", {"stiehlst": "Präsens (du)", "stiehlt": "Präsens (er/sie/es)", "stiehl": "Imperativ"}),
    "steigen": ("stieg", "gestiegen", {}),
    "sterben": ("starb", "gestorben", {"stirbst": "Präsens (du)", "stirbt": "Präsens (er/sie/es)", "stirb": "Imperativ"}),
    "stinken": ("stank", "gestunken", {}),
    "stoßen": ("stieß", "gestoßen", {"stößt": "Präsens (du/er/sie/es)"}),
    "streichen": ("strich", "gestrichen", {}),
    "streiten": ("stritt", "gestritten", {}),
    "tragen": ("trug", "getragen", {"trägst": "Präsens (du)", "trägt": "Präsens (er/sie/es)"}),
    "treffen": ("traf", "getroffen", {"triffst": "Präsens (du)", "trifft": "Präsens (er/sie/es)", "triff": "Imperativ"}),
    "treiben": ("trieb", "getrieben", {}),
    "treten": ("trat", "getreten", {"trittst": "Präsens (du)", "tritt": "Präsens (er/sie/es)", "tritt": "Imperativ"}),
    "trinken": ("trank", "getrunken", {}),
    "trügen": ("trog", "getrogen", {}),
    "verderben": ("verdarb", "verdorben", {"verdirbst": "Präsens (du)", "verdirbt": "Präsens (er/sie/es)"}),
    "verdrießen": ("verdross", "verdrossen", {}),
    "vergessen": ("vergaß", "vergessen", {"vergisst": "Präsens (du/er/sie/es)", "vergiss": "Imperativ"}),
    "verlieren": ("verlor", "verloren", {}),
    "verstehen": ("verstand", "verstanden", {}),
    "verzeihen": ("verzieh", "verziehen", {}),
    "wachsen": ("wuchs", "gewachsen", {"wächst": "Präsens (du/er/sie/es)"}),
    "waschen": ("wusch", "gewaschen", {"wäschst": "Präsens (du)", "wäscht": "Präsens (er/sie/es)"}),
    "weichen": ("wich", "gewichen", {}),
    "weisen": ("wies", "gewiesen", {}),
    "wenden": ("wandte", "gewandt", {}),
    "werben": ("warb", "geworben", {"wirbst": "Präsens (du)", "wirbt": "Präsens (er/sie/es)"}),
    "werfen": ("warf", "geworfen", {"wirfst": "Präsens (du)", "wirft": "Präsens (er/sie/es)", "wirf": "Imperativ"}),
    "wiegen": ("wog", "gewogen", {}),
    "winden": ("wand", "gewunden", {}),
    "wringen": ("wrang", "gewrungen", {}),
    "ziehen": ("zog", "gezogen", {}),
    "zwingen": ("zwang", "gezwungen", {}),
}

def _generate_praeteritum_forms(stem: str) -> List[Tuple[str, str]]:
    """Präteritum kökünden olası şahıs çekimlerini (ich/er, du, wir, ihr, sie) üretir."""
    forms: List[Tuple[str, str]] = []
    # 1./3. tekil şahıs (ich, er/sie/es)
    forms.append((stem, "Präteritum"))

    # 2. tekil şahıs (du)
    if stem.endswith(("d", "t")):
        forms.append((stem + "est", "Präteritum (du)"))
        forms.append((stem + "st", "Präteritum (du)"))
    elif stem.endswith(("s", "ß", "z")):
        forms.append((stem + "est", "Präteritum (du)"))
        forms.append((stem + "t", "Präteritum (du)"))
    elif stem.endswith("e"):
        forms.append((stem + "st", "Präteritum (du)"))
    else:
        forms.append((stem + "st", "Präteritum (du)"))

    # 1./3. çoğul şahıs (wir, sie/Sie)
    if stem.endswith("e"):
        forms.append((stem + "n", "Präteritum (wir/sie)"))
    elif stem.endswith("el") or stem.endswith("er"):
        forms.append((stem + "n", "Präteritum (wir/sie)"))
    else:
        forms.append((stem + "en", "Präteritum (wir/sie)"))

    # 2. çoğul şahıs (ihr)
    if stem.endswith(("d", "t")):
        forms.append((stem + "et", "Präteritum (ihr)"))
    elif stem.endswith("e"):
        forms.append((stem + "t", "Präteritum (ihr)"))
    else:
        forms.append((stem + "t", "Präteritum (ihr)"))

    return forms

def _build_reverse_index() -> Dict[str, Tuple[str, str]]:
    """Tüm düzensiz fiillerin çekimli formlarından (infinitive, form_label) ters indeksini oluşturur."""
    rev: Dict[str, Tuple[str, str]] = {}

    for inf, (praet_stem, part2, praesens_dict) in IRREGULAR_VERBS_DATA.items():
        # Mastarın kendisi
        if inf not in rev:
            rev[inf] = (inf, "Infinitiv")

        # Partizip II
        if part2 and part2 not in rev:
            rev[part2] = (inf, "Partizip II")

        # Düzensiz Präsens formları
        for p_form, label in praesens_dict.items():
            if p_form not in rev:
                rev[p_form] = (inf, label)

        # Präteritum formları
        if praet_stem:
            for form, label in _generate_praeteritum_forms(praet_stem):
                if form not in rev:
                    rev[form] = (inf, label)

    return rev

# Modül yüklendiğinde hafızada hazır ters indeks (surface_lowercase -> (infinitive, form_label))
REVERSE_IRREGULAR_INDEX: Dict[str, Tuple[str, str]] = _build_reverse_index()
