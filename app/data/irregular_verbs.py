"""
Almanca Güçlü ve Düzensiz Fiiller Veritabanı (German Irregular Verbs Database)
Veri kaynağı: Goethe / Duden A1-C1 standart düzensiz ve güçlü fiil çekim tabloları.
Ters indeks (REVERSE_IRREGULAR_INDEX) ile çekimli biçimlerden sözlük biçimine (mastar/lemma)
yüksek güvenirlikle (confidence='high') çözümleme sağlar.
"""

from typing import Dict, Tuple, Optional, List, Set, Any

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

# ==============================================================================
# GÜÇLÜ & DÜZENSİZ FİİLLER TRİAD MOTORU (STRONG & IRREGULAR VERBS TRIAD ENGINE)
# ==============================================================================

SEIN_AUXILIARY_VERBS: Set[str] = {
    "sein", "werden", "gehen", "kommen", "fahren", "fliegen", "bleiben", "fallen",
    "steigen", "sinken", "sterben", "laufen", "rennen", "schwimmen", "springen",
    "wachsen", "genesen", "gelingen", "misslingen", "geschehen", "passieren",
    "kriechen", "gleiten", "schleichen", "schreiten", "verreisen", "aufstehen",
    "aufwachen", "einschlafen", "ankommen", "abfahren", "ausgehen", "umziehen",
    "einsteigen", "aussteigen", "umsteigen", "mitkommen", "zurückkommen",
    "verschwinden", "erscheinen", "bersten", "dringen", "erlöschen", "erschrecken",
    "fliehen", "fließen", "gedeihen", "quellen", "rinnen", "schwellen", "schwinden",
    "sprießen", "stieben", "weichen", "entstehen", "einziehen"
}

EXTRA_STRONG_VERBS: Dict[str, Tuple[str, str, str, str, Dict[str, str]]] = {
    "abfahren": ("fuhr ab", "abgefahren", "ist", "fährt ab", {"abgefahren": "Partizip II", "fährst ab": "Präsens (du)", "fährt ab": "Präsens (er/sie/es)"}),
    "abfliegen": ("flog ab", "abgeflogen", "ist", "fliegt ab", {"abgeflogen": "Partizip II"}),
    "abgeben": ("gab ab", "abgegeben", "hat", "gibt ab", {"abgegeben": "Partizip II", "gibst ab": "Präsens (du)", "gibt ab": "Präsens (er/sie/es)", "gib ab": "Imperativ"}),
    "abnehmen": ("nahm ab", "abgenommen", "hat", "nimmt ab", {"abgenommen": "Partizip II", "nimmst ab": "Präsens (du)", "nimmt ab": "Präsens (er/sie/es)", "nimm ab": "Imperativ"}),
    "anbieten": ("bot an", "angeboten", "hat", "bietet an", {"angeboten": "Partizip II"}),
    "anfangen": ("fing an", "angefangen", "hat", "fängt an", {"angefangen": "Partizip II", "fängst an": "Präsens (du)", "fängt an": "Präsens (er/sie/es)"}),
    "ankommen": ("kam an", "angekommen", "ist", "kommt an", {"angekommen": "Partizip II"}),
    "annehmen": ("nahm an", "angenommen", "hat", "nimmt an", {"angenommen": "Partizip II", "nimmst an": "Präsens (du)", "nimmt an": "Präsens (er/sie/es)", "nimm an": "Imperativ"}),
    "anrufen": ("rief an", "angerufen", "hat", "ruft an", {"angerufen": "Partizip II"}),
    "ansehen": ("sah an", "angesehen", "hat", "sieht an", {"angesehen": "Partizip II", "siehst an": "Präsens (du)", "sieht an": "Präsens (er/sie/es)", "sieh an": "Imperativ"}),
    "ansprechen": ("sprach an", "angesprochen", "hat", "spricht an", {"angesprochen": "Partizip II", "sprichst an": "Präsens (du)", "sprich an": "Präsens (er/sie/es)", "sprich an": "Imperativ"}),
    "anziehen": ("zog an", "angezogen", "hat", "zieht an", {"angezogen": "Partizip II"}),
    "aufstehen": ("stand auf", "aufgestanden", "ist", "steht auf", {"aufgestanden": "Partizip II"}),
    "aufgeben": ("gab auf", "aufgegeben", "hat", "gibt auf", {"aufgegeben": "Partizip II", "gibst auf": "Präsens (du)", "gibt auf": "Präsens (er/sie/es)", "gib auf": "Imperativ"}),
    "aufnehmen": ("nahm auf", "aufgenommen", "hat", "nimmt auf", {"aufgenommen": "Partizip II", "nimmst auf": "Präsens (du)", "nimmt auf": "Präsens (er/sie/es)", "nimm auf": "Imperativ"}),
    "ausgeben": ("gab aus", "ausgegeben", "hat", "gibt aus", {"ausgegeben": "Partizip II", "gibst aus": "Präsens (du)", "gibt aus": "Präsens (er/sie/es)", "gib aus": "Imperativ"}),
    "ausgehen": ("ging aus", "ausgegangen", "ist", "geht aus", {"ausgegangen": "Partizip II"}),
    "aussehen": ("sah aus", "ausgesehen", "hat", "sieht aus", {"ausgesehen": "Partizip II", "siehst aus": "Präsens (du)", "sieht aus": "Präsens (er/sie/es)", "sieh aus": "Imperativ"}),
    "aussteigen": ("stieg aus", "ausgestiegen", "ist", "steigt aus", {"ausgestiegen": "Partizip II"}),
    "beitragen": ("trug bei", "beigetragen", "hat", "trägt bei", {"beigetragen": "Partizip II", "trägst bei": "Präsens (du)", "trägt bei": "Präsens (er/sie/es)"}),
    "bekommen": ("bekam", "bekommen", "hat", "bekommt", {"bekommen": "Partizip II"}),
    "beschreiben": ("beschrieb", "beschrieben", "hat", "beschreibt", {"beschrieben": "Partizip II"}),
    "besprechen": ("besprach", "besprochen", "hat", "bespricht", {"besprochen": "Partizip II", "besprichst": "Präsens (du)", "bespricht": "Präsens (er/sie/es)", "besprich": "Imperativ"}),
    "bestehen": ("bestand", "bestanden", "hat", "besteht", {"bestanden": "Partizip II"}),
    "einladen": ("lud ein", "eingeladen", "hat", "lädt ein", {"eingeladen": "Partizip II", "lädst ein": "Präsens (du)", "lädt ein": "Präsens (er/sie/es)"}),
    "einschlafen": ("schlief ein", "eingeschlafen", "ist", "schläft ein", {"eingeschlafen": "Partizip II", "schläfst ein": "Präsens (du)", "schläft ein": "Präsens (er/sie/es)"}),
    "einsteigen": ("stieg ein", "eingestiegen", "ist", "steigt ein", {"eingestiegen": "Partizip II"}),
    "einziehen": ("zog ein", "eingezogen", "ist", "zieht ein", {"eingezogen": "Partizip II"}),
    "entlassen": ("entließ", "entlassen", "hat", "entlässt", {"entlassen": "Partizip II", "entlässt": "Präsens (du/er/sie/es)"}),
    "entstehen": ("entstand", "entstanden", "ist", "entsteht", {"entstanden": "Partizip II"}),
    "erfahren": ("erfuhr", "erfahren", "hat", "erfährt", {"erfahren": "Partizip II", "erfährst": "Präsens (du)", "erfährt": "Präsens (er/sie/es)"}),
    "erfinden": ("erfand", "erfunden", "hat", "erfindet", {"erfunden": "Partizip II"}),
    "erkennen": ("erkannte", "erkannt", "hat", "erkennt", {"erkannt": "Partizip II"}),
    "erscheinen": ("erschien", "erschienen", "ist", "erscheint", {"erschienen": "Partizip II"}),
    "ertragen": ("ertrug", "ertragen", "hat", "erträgt", {"ertragen": "Partizip II", "erträgst": "Präsens (du)", "erträgt": "Präsens (er/sie/es)"}),
    "erziehen": ("erzog", "erzogen", "hat", "erzieht", {"erzogen": "Partizip II"}),
    "gefallen": ("gefiel", "gefallen", "hat", "gefällt", {"gefallen": "Partizip II", "gefällst": "Präsens (du)", "gefällt": "Präsens (er/sie/es)"}),
    "mitbringen": ("brachte mit", "mitgebracht", "hat", "bringt mit", {"mitgebracht": "Partizip II"}),
    "mitkommen": ("kam mit", "mitgekommen", "ist", "kommt mit", {"mitgekommen": "Partizip II"}),
    "mitnehmen": ("nahm mit", "mitgenommen", "hat", "nimmt mit", {"mitgenommen": "Partizip II", "nimmst mit": "Präsens (du)", "nimmt mit": "Präsens (er/sie/es)", "nimm mit": "Imperativ"}),
    "nachdenken": ("dachte nach", "nachgedacht", "hat", "denkt nach", {"nachgedacht": "Partizip II"}),
    "stattfinden": ("fand statt", "stattgefunden", "hat", "findet statt", {"stattgefunden": "Partizip II"}),
    "teilnehmen": ("nahm teil", "teilgenommen", "hat", "nimmt teil", {"teilgenommen": "Partizip II", "nimmst teil": "Präsens (du)", "nimmt teil": "Präsens (er/sie/es)", "nimm teil": "Imperativ"}),
    "übertreiben": ("übertrieb", "übertrieben", "hat", "übertreibt", {"übertrieben": "Partizip II"}),
    "umsteigen": ("stieg um", "umgestiegen", "ist", "steigt um", {"umgestiegen": "Partizip II"}),
    "umziehen": ("zog um", "umgezogen", "ist", "zieht um", {"umgezogen": "Partizip II"}),
    "verbringen": ("verbrachte", "verbracht", "hat", "verbringt", {"verbracht": "Partizip II"}),
    "vergeben": ("vergab", "vergeben", "hat", "vergibt", {"vergeben": "Partizip II", "vergibst": "Präsens (du)", "vergibt": "Präsens (er/sie/es)", "vergib": "Imperativ"}),
    "vergleichen": ("verglich", "verglichen", "hat", "vergleicht", {"verglichen": "Partizip II"}),
    "verlassen": ("verließ", "verlassen", "hat", "verlässt", {"verlassen": "Partizip II", "verlässt": "Präsens (du/er/sie/es)"}),
    "versprechen": ("versprach", "versprochen", "hat", "verspricht", {"versprochen": "Partizip II", "versprichst": "Präsens (du)", "verspricht": "Präsens (er/sie/es)", "versprich": "Imperativ"}),
    "vorhaben": ("hatte vor", "vorgehabt", "hat", "hat vor", {"vorgehabt": "Partizip II"}),
    "vorschlagen": ("schlug vor", "vorgeschlagen", "hat", "schlägt vor", {"vorgeschlagen": "Partizip II", "schlägst vor": "Präsens (du)", "schlägt vor": "Präsens (er/sie/es)"}),
    "wehtun": ("tat weh", "wehgetan", "hat", "tut weh", {"wehgetan": "Partizip II"}),
    "zurückkommen": ("kam zurück", "zurückgekommen", "ist", "kommt zurück", {"zurückgekommen": "Partizip II"}),
    "zunehmen": ("nahm zu", "zugenommen", "hat", "nimmt zu", {"zugenommen": "Partizip II", "nimmst zu": "Präsens (du)", "nimmt zu": "Präsens (er/sie/es)", "nimm zu": "Imperativ"})
}

def _build_strong_verbs_and_index() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    strong: Dict[str, Dict[str, Any]] = {}
    index: Dict[str, str] = {}

    # 1. Standart düzensiz fiiller tablosu (169 fiil)
    for inf, (praet, part2, praes) in IRREGULAR_VERBS_DATA.items():
        aux = "ist" if inf in SEIN_AUXILIARY_VERBS else "hat"
        praes_3sg = ""
        for p_form, p_lbl in praes.items():
            if "er/sie/es" in p_lbl or "er" in p_lbl:
                praes_3sg = p_form
                break
        if not praes_3sg:
            praes_3sg = inf[:-2] + "t" if inf.endswith("en") else inf + "t"

        perf = f"{aux} {part2}"
        triad = f"Mastar: {inf} • Prät: {praet} • Perf: {perf}"
        triad_disp = f"📌 Mastar: {inf} • Prät: {praet} • Perf: {perf}"

        strong[inf] = {
            "infinitive": inf,
            "praeteritum": praet,
            "partizip2": part2,
            "auxiliary": aux,
            "perfekt": perf,
            "praesens_3sg": praes_3sg,
            "triad": triad,
            "triad_display": triad_disp,
            "forms": praes.copy()
        }
        index[inf] = inf
        if part2:
            index[part2] = inf
        for p in praes:
            index[p] = inf
        for f_form, f_lbl in _generate_praeteritum_forms(praet):
            index[f_form] = inf
            strong[inf]["forms"][f_form] = f_lbl

    # 2. Ek yaygın güçlü ve bileşik fiiller (56 fiil -> Toplam 225 fiil)
    for inf, (praet, part2, aux, praes_3sg, praes) in EXTRA_STRONG_VERBS.items():
        perf = f"{aux} {part2}"
        triad = f"Mastar: {inf} • Prät: {praet} • Perf: {perf}"
        triad_disp = f"📌 Mastar: {inf} • Prät: {praet} • Perf: {perf}"

        strong[inf] = {
            "infinitive": inf,
            "praeteritum": praet,
            "partizip2": part2,
            "auxiliary": aux,
            "perfekt": perf,
            "praesens_3sg": praes_3sg,
            "triad": triad,
            "triad_display": triad_disp,
            "forms": praes.copy()
        }
        index[inf] = inf
        if part2:
            index[part2] = inf
        for p in praes:
            index[p] = inf
        if " " in praet:
            stem, sep = praet.split(" ", 1)
            for f_form, f_lbl in _generate_praeteritum_forms(stem):
                index[f"{f_form} {sep}"] = inf
                index[f"{sep}{f_form}"] = inf
                strong[inf]["forms"][f"{f_form} {sep}"] = f_lbl
        else:
            for f_form, f_lbl in _generate_praeteritum_forms(praet):
                index[f_form] = inf
                strong[inf]["forms"][f_form] = f_lbl

    return strong, index

STRONG_VERBS, VERB_CONJUGATIONS_INDEX = _build_strong_verbs_and_index()

def get_verb_conjugation_info(word: str) -> Optional[Dict[str, Any]]:
    """
    Verilen kelimenin (çekimli form veya mastar) güçlü/düzensiz fiil triadını ve çekim detaylarını döner.
    $O(1)$ erişimle VERB_CONJUGATIONS_INDEX üzerinden kök mastar tespit edilir.

    Örnek Dönüş:
    {
        "infinitive": "gehen",
        "praeteritum": "ging",
        "partizip2": "gegangen",
        "auxiliary": "ist",
        "perfekt": "ist gegangen",
        "praesens_3sg": "geht",
        "triad": "Mastar: gehen • Prät: ging • Perf: ist gegangen",
        "triad_display": "📌 Mastar: gehen • Prät: ging • Perf: ist gegangen",
        "form": "Präteritum",
        "is_inflected": True
    }
    """
    if not word or not isinstance(word, str):
        return None
    clean = word.strip().lower()
    infinitive = VERB_CONJUGATIONS_INDEX.get(clean)
    if not infinitive and clean in STRONG_VERBS:
        infinitive = clean
    if not infinitive:
        # Birleşik geçmiş zaman: 'ist gegangen', 'hat gelesen'
        parts = clean.split()
        if len(parts) == 2 and parts[0] in ("ist", "hat", "war", "hatte", "bin", "bist", "sind", "seid", "habe", "hast", "haben", "habt"):
            infinitive = VERB_CONJUGATIONS_INDEX.get(parts[1])
    if not infinitive:
        return None

    info = STRONG_VERBS.get(infinitive)
    if not info:
        return None

    res = dict(info)
    forms = info.get("forms", {})
    if clean in forms:
        res["form"] = forms[clean]
        res["is_inflected"] = (clean != infinitive)
    elif clean == infinitive:
        res["form"] = "Infinitiv"
        res["is_inflected"] = False
    elif clean == info.get("partizip2") or clean == info.get("perfekt"):
        res["form"] = "Partizip II"
        res["is_inflected"] = True
    elif clean == info.get("praeteritum") or clean.startswith(info.get("praeteritum", "---")):
        res["form"] = "Präteritum"
        res["is_inflected"] = True
    else:
        res["form"] = "Çekimli Fiil"
        res["is_inflected"] = (clean != infinitive)

    return res
