"""
Almanca Dil Bilgisi ve Morfoloji Analiz Modülü (German Linguistic Analyzer)
Artikeller (der/die/das), çoğul ekleri, ayrılabilir fiiller ve dil bilgisi ipuçlarını çözer.
"""
import re
from typing import Dict, Any, Optional, Tuple, List

# Der, Die, Das Renk Kodları (Görsel öğrenmeyi hızlandırmak için)
ARTICLE_COLORS = {
    "der": "#2563eb",  # Mavi (Maskulinum)
    "die": "#dc2626",  # Kırmızı (Femininum)
    "das": "#16a34a",  # Yeşil (Neutrum)
    "": "#6b7280"      # Nötr gri
}

ARTICLE_TURKISH = {
    "der": "Eril (Maskulinum)",
    "die": "Dişil (Femininum)",
    "das": "Nötr (Neutrum)"
}

# Almanca Kural Tabanlı Son Ek (Suffix) Tablosu
SUFFIX_RULES = [
    # Neutrum (das) kuralları (-ment önce kontrol edilir)
    (r"(chen|lein|ment|um|tum|ma)$", "das", "Son ek kuralı: -{suffix} biten kelimeler daima nötrdür (das)."),
    # Femininum (die) kuralları
    (r"(ung|heit|keit|schaft|tät|ik|ur|ion|ei|ie|anz|enz)$", "die", "Son ek kuralı: -{suffix} biten kelimeler daima dişildir (die)."),
    (r"in$", "die", "Dişil kişi/meslek eki: -in ile biten meslek ve şahıs isimleri dişildir (die)."),
    # Maskulinum (der) kuralları (-ment olmayan -ent)
    (r"(ling|ismus|ist|or|ant|eur|loge|(?<!m)ent)$", "der", "Son ek kuralı: -{suffix} biten kelimeler erildir (der)."),
    # Nötr isim ekleri
    (r"nis$", "das", "Son ek kuralı: -nis ile biten isimlerin çoğu nötrdür (das)."),
    # -e ile biten isimler (%90 die)
    (r"[a-zäöü]e$", "die", "Genel kural: -e ile biten iki heceli Almanca isimlerin %90'ı dişildir (die)."),
]

# Ayrılabilir Fiil Önekleri (Trennbare Verben)
SEPARABLE_PREFIXES = [
    "ab", "an", "auf", "aus", "bei", "ein", "fest", "fort", "her", "hin",
    "los", "mit", "nach", "vor", "weg", "weiter", "zu", "zurück", "zusammen"
]

# Almanca İsim Artikelleri ve Belirteçler
ARTICLES_SET = {
    "der", "die", "das",
    "ein", "eine", "einen", "einem", "einer", "eines",
    "kein", "keine", "keinen", "keinem", "keiner", "keines",
    "dem", "den", "des"
}

# Modal Fiiller (Präsens ve Präteritum - Tam Tablo)
MODAL_VERBS = {
    # können
    "kann": "können (yapabilmek / edebilmek)",
    "kannst": "können (yapabilmek)",
    "könnt": "können (yapabilmek)",
    "können": "können (yapabilmek)",
    "konnte": "können [Geçmiş] (yapabiliyordu)",
    "konntest": "können [Geçmiş] (yapabiliyordun)",
    "konntet": "können [Geçmiş] (yapabiliyordunuz)",
    "konnten": "können [Geçmiş] (yapabiliyorlardı)",
    # müssen
    "muss": "müssen (zorunda olmak)",
    "musst": "müssen (zorunda olmak)",
    "müsst": "müssen (zorunda olmak)",
    "müssen": "müssen (zorunda olmak)",
    "musste": "müssen [Geçmiş] (zorundaydı)",
    "musstest": "müssen [Geçmiş] (zorundaydın)",
    "musstet": "müssen [Geçmiş] (zorundaydınız)",
    "mussten": "müssen [Geçmiş] (zorundaydılar)",
    # wollen
    "will": "wollen (istemek / niyetinde olmak)",
    "willst": "wollen (istemek)",
    "wollt": "wollen (istemek)",
    "wollen": "wollen (istemek)",
    "wollte": "wollen [Geçmiş] (istiyordu)",
    "wolltest": "wollen [Geçmiş] (istiyordun)",
    "wolltet": "wollen [Geçmiş] (istiyordunuz)",
    "wollten": "wollen [Geçmiş] (istiyorlardı)",
    # sollen
    "soll": "sollen (-meli / tavsiye / görev)",
    "sollst": "sollen (-meli)",
    "sollt": "sollen (-meli)",
    "sollen": "sollen (-meli)",
    "sollte": "sollen [Geçmiş/Konjunktiv II] (-meliydi)",
    "solltest": "sollen [Geçmiş/Konjunktiv II] (-meliydin)",
    "solltet": "sollen [Geçmiş/Konjunktiv II] (-meliydiniz)",
    "sollten": "sollen [Geçmiş/Konjunktiv II] (-meliydiler)",
    # dürfen
    "darf": "dürfen (izinli olmak / hakkı olmak)",
    "darfst": "dürfen (izinli olmak)",
    "dürft": "dürfen (izinli olmak)",
    "dürfen": "dürfen (izinli olmak)",
    "durfte": "dürfen [Geçmiş] (izinliydi)",
    "durftest": "dürfen [Geçmiş] (izinliydin)",
    "durftet": "dürfen [Geçmiş] (izinliydiniz)",
    "durften": "dürfen [Geçmiş] (izinliydiler)",
    # mögen / möchten
    "mag": "mögen (sevmek / hoşlanmak)",
    "magst": "mögen (sevmek)",
    "mögt": "mögen (sevmek)",
    "mögen": "mögen (sevmek)",
    "mochte": "mögen [Geçmiş] (seviyordu)",
    "mochten": "mögen [Geçmiş] (seviyorlardı)",
    "möchte": "möchten (istemek / arzu etmek)",
    "möchtest": "möchten (istemek)",
    "möchtet": "möchten (istemek)",
    "möchten": "möchten (istemek)",
}

# Yan Cümle Bağlaçları (Fiili sona atan bağlaçlar)
SUBORDINATING_CONJUNCTIONS = {
    "weil": "çünkü (fiili yan cümlenin en sonuna gönderir)",
    "dass": "-dığı / -eceği (fiili yan cümlenin en sonuna gönderir)",
    "obwohl": "-e rağmen / karşın (fiili en sona gönderir)",
    "wenn": "eğer / -dığında (fiili en sona gönderir)",
    "damit": "böylece / -sın diye (fiili en sona gönderir)",
    "bevor": "-den önce (fiili en sona gönderir)",
    "nachdem": "-dikten sonra (fiili en sona gönderir)",
    "während": "-iken / sırasında (fiili en sona gönderir)"
}

# Çevrimdışı Temel Almanca-Türkçe Sözlük Veritabanı (Genişletilmiş A1-B1)
COMMON_VOCABULARY: Dict[str, Dict[str, str]] = {
    # İsimler (Nomen)
    "haus": {"article": "das", "plural": "die Häuser", "turkish": "ev, bina", "pos": "İsim (Nomen)", "ex_de": "Ich gehe nach Hause.", "ex_tr": "Eve gidiyorum."},
    "auto": {"article": "das", "plural": "die Autos", "turkish": "araba, otomobil", "pos": "İsim (Nomen)", "ex_de": "Das Auto ist neu.", "ex_tr": "Araba yenidir."},
    "buch": {"article": "das", "plural": "die Bücher", "turkish": "kitap", "pos": "İsim (Nomen)", "ex_de": "Ich lese ein spannendes Buch.", "ex_tr": "Heyecan verici bir kitap okuyorum."},
    "kind": {"article": "das", "plural": "die Kinder", "turkish": "çocuk", "pos": "İsim (Nomen)", "ex_de": "Das Kind spielt im Garten.", "ex_tr": "Çocuk bahçede oynuyor."},
    "mann": {"article": "der", "plural": "die Männer", "turkish": "adam, erkek, koca", "pos": "İsim (Nomen)", "ex_de": "Der Mann arbeitet im Büro.", "ex_tr": "Adam ofiste çalışıyor."},
    "frau": {"article": "die", "plural": "die Frauen", "turkish": "kadın, bayan, eş", "pos": "İsim (Nomen)", "ex_de": "Die Frau spricht fließend Deutsch.", "ex_tr": "Kadın akıcı Almanca konuşuyor."},
    "tag": {"article": "der", "plural": "die Tage", "turkish": "gün", "pos": "İsim (Nomen)", "ex_de": "Guten Tag! Wie geht es Ihnen?", "ex_tr": "İyi günler! Nasılsınız?"},
    "zeit": {"article": "die", "plural": "die Zeiten", "turkish": "zaman, vakit", "pos": "İsim (Nomen)", "ex_de": "Ich habe heute leider keine Zeit.", "ex_tr": "Bugün maalesef vaktim yok."},
    "arbeit": {"article": "die", "plural": "die Arbeiten", "turkish": "iş, çalışma", "pos": "İsim (Nomen)", "ex_de": "Er sucht eine neue Arbeit.", "ex_tr": "O yeni bir iş arıyor."},
    "frage": {"article": "die", "plural": "die Fragen", "turkish": "soru", "pos": "İsim (Nomen)", "ex_de": "Darf ich Ihnen eine Frage stellen?", "ex_tr": "Size bir soru sorabilir miyim?"},
    "antwort": {"article": "die", "plural": "die Antworten", "turkish": "cevap, yanıt", "pos": "İsim (Nomen)", "ex_de": "Ich warte auf deine Antwort.", "ex_tr": "Senin yanıtını bekliyorum."},
    "leben": {"article": "das", "plural": "-", "turkish": "hayat, yaşam", "pos": "İsim (Nomen)", "ex_de": "Das Leben ist schön.", "ex_tr": "Hayat güzeldir."},
    "weg": {"article": "der", "plural": "die Wege", "turkish": "yol, yöntem", "pos": "İsim (Nomen)", "ex_de": "Können Sie mir den Weg zeigen?", "ex_tr": "Bana yolu gösterebilir misiniz?"},
    "stadt": {"article": "die", "plural": "die Städte", "turkish": "şehir, kent", "pos": "İsim (Nomen)", "ex_de": "Berlin ist eine große Stadt.", "ex_tr": "Berlin büyük bir şehirdir."},
    "land": {"article": "das", "plural": "die Länder", "turkish": "ülke, memleket; kır", "pos": "İsim (Nomen)", "ex_de": "Deutschland ist ein schönes Land.", "ex_tr": "Almanya güzel bir ülkedir."},
    "schule": {"article": "die", "plural": "die Schulen", "turkish": "okul", "pos": "İsim (Nomen)", "ex_de": "Die Kinder gehen zur Schule.", "ex_tr": "Çocuklar okula gidiyor."},
    "freund": {"article": "der", "plural": "die Freunde", "turkish": "arkadaş, dost, erkek arkadaş", "pos": "İsim (Nomen)", "ex_de": "Er ist mein bester Freund.", "ex_tr": "O benim en iyi arkadaşım."},
    "freundin": {"article": "die", "plural": "die Freundinnen", "turkish": "kız arkadaş", "pos": "İsim (Nomen)", "ex_de": "Meine Freundin lernt auch Deutsch.", "ex_tr": "Kız arkadaşım da Almanca öğreniyor."},
    "wort": {"article": "das", "plural": "die Wörter / Worte", "turkish": "kelime, sözcük", "pos": "İsim (Nomen)", "ex_de": "Ich lerne jeden Tag zehn Wörter.", "ex_tr": "Her gün on kelime öğreniyorum."},
    "sprache": {"article": "die", "plural": "die Sprachen", "turkish": "dil, lisan", "pos": "İsim (Nomen)", "ex_de": "Deutsch ist eine interessante Sprache.", "ex_tr": "Almanca ilginç bir dildir."},
    "entscheidung": {"article": "die", "plural": "die Entscheidungen", "turkish": "karar", "pos": "İsim (Nomen)", "ex_de": "Das war eine schwierige Entscheidung.", "ex_tr": "Bu zor bir karardı."},
    "aufmerksamkeit": {"article": "die", "plural": "die Aufmerksamkeiten", "turkish": "dikkat, ilgi, nezaket", "pos": "İsim (Nomen)", "ex_de": "Vielen Dank für Ihre Aufmerksamkeit.", "ex_tr": "Dikkatiniz için çok teşekkür ederim."},
    "erfolg": {"article": "der", "plural": "die Erfolge", "turkish": "başarı", "pos": "İsim (Nomen)", "ex_de": "Ich wünsche dir viel Erfolg!", "ex_tr": "Sana bol başarılar dilerim!"},
    "tisch": {"article": "der", "plural": "die Tische", "turkish": "masa", "pos": "İsim (Nomen)", "ex_de": "Das Buch liegt auf dem Tisch.", "ex_tr": "Kitap masanın üzerinde duruyor."},
    "stuhl": {"article": "der", "plural": "die Stühle", "turkish": "sandalye", "pos": "İsim (Nomen)", "ex_de": "Nehmen Sie bitte auf dem Stuhl Platz.", "ex_tr": "Lütfen sandalyeye oturun."},
    "apfel": {"article": "der", "plural": "die Äpfel", "turkish": "elma", "pos": "İsim (Nomen)", "ex_de": "Ein Apfel am Tag hält gesund.", "ex_tr": "Günde bir elma sağlıklı tutar."},
    "tür": {"article": "die", "plural": "die Türen", "turkish": "kapı", "pos": "İsim (Nomen)", "ex_de": "Bitte schließen Sie die Tür.", "ex_tr": "Lütfen kapıyı kapatın."},
    "fenster": {"article": "das", "plural": "die Fenster", "turkish": "pencere", "pos": "İsim (Nomen)", "ex_de": "Er öffnet das Fenster.", "ex_tr": "O pencereyi açıyor."},
    "wasser": {"article": "das", "plural": "-", "turkish": "su", "pos": "İsim (Nomen)", "ex_de": "Ich trinke ein Glas kaltes Wasser.", "ex_tr": "Bir bardak soğuk su içiyorum."},
    "brot": {"article": "das", "plural": "die Brote", "turkish": "ekmek", "pos": "İsim (Nomen)", "ex_de": "Ich kaufe frisches Brot.", "ex_tr": "Taze ekmek alıyorum."},
    "kaffee": {"article": "der", "plural": "-", "turkish": "kahve", "pos": "İsim (Nomen)", "ex_de": "Möchten Sie einen Kaffee?", "ex_tr": "Bir kahve ister misiniz?"},
    "tee": {"article": "der", "plural": "-", "turkish": "çay", "pos": "İsim (Nomen)", "ex_de": "Ich trinke morgens schwarzen Tee.", "ex_tr": "Sabahları siyah çay içerim."},
    "hund": {"article": "der", "plural": "die Hunde", "turkish": "köpek", "pos": "İsim (Nomen)", "ex_de": "Der Hund bellt im Garten.", "ex_tr": "Köpek bahçede havlıyor."},
    "katze": {"article": "die", "plural": "die Katzen", "turkish": "kedi", "pos": "İsim (Nomen)", "ex_de": "Die Katze schläft auf dem Sofa.", "ex_tr": "Kedi kanepede uyuyor."},
    "geld": {"article": "das", "plural": "-", "turkish": "para", "pos": "İsim (Nomen)", "ex_de": "Zeit ist Geld.", "ex_tr": "Vakit nakittir."},
    "arzt": {"article": "der", "plural": "die Ärzte", "turkish": "doktor, hekim", "pos": "İsim (Nomen)", "ex_de": "Der Arzt untersucht den Patienten.", "ex_tr": "Doktor hastayı muayene ediyor."},
    "ärztin": {"article": "die", "plural": "die Ärztinnen", "turkish": "kadın doktor", "pos": "İsim (Nomen)", "ex_de": "Die Ärztin hilft den Menschen.", "ex_tr": "Kadın doktor insanlara yardım ediyor."},
    "lehrer": {"article": "der", "plural": "die Lehrer", "turkish": "öğretmen", "pos": "İsim (Nomen)", "ex_de": "Der Lehrer erklärt die Regel.", "ex_tr": "Öğretmen kuralı açıklıyor."},
    "lehrerin": {"article": "die", "plural": "die Lehrerinnen", "turkish": "kadın öğretmen", "pos": "İsim (Nomen)", "ex_de": "Unsere Lehrerin ist sehr nett.", "ex_tr": "Öğretmenimiz çok naziktir."},
    "mutter": {"article": "die", "plural": "die Mütter", "turkish": "anne", "pos": "İsim (Nomen)", "ex_de": "Meine Mutter kocht sehr gut.", "ex_tr": "Annem çok güzel yemek pişirir."},
    "vater": {"article": "der", "plural": "die Väter", "turkish": "baba", "pos": "İsim (Nomen)", "ex_de": "Mein Vater liest die Zeitung.", "ex_tr": "Babam gazete okuyor."},
    "bruder": {"article": "der", "plural": "die Brüder", "turkish": "erkek kardeş", "pos": "İsim (Nomen)", "ex_de": "Mein Bruder studiert Medizin.", "ex_tr": "Erkek kardeşim tıp okuyor."},
    "schwester": {"article": "die", "plural": "die Schwestern", "turkish": "kız kardeş", "pos": "İsim (Nomen)", "ex_de": "Meine Schwester wohnt in Köln.", "ex_tr": "Kız kardeşim Köln'de yaşıyor."},
    "sonne": {"article": "die", "plural": "-", "turkish": "güneş", "pos": "İsim (Nomen)", "ex_de": "Die Sonne scheint heute hell.", "ex_tr": "Güneş bugün parlak parlıyor."},
    "mond": {"article": "der", "plural": "-", "turkish": "ay", "pos": "İsim (Nomen)", "ex_de": "Der Mond steht am Himmel.", "ex_tr": "Ay gökyüzünde duruyor."},
    "nacht": {"article": "die", "plural": "die Nächte", "turkish": "gece", "pos": "İsim (Nomen)", "ex_de": "Gute Nacht und schlaf gut!", "ex_tr": "İyi geceler ve iyi uyu!"},
    "morgen": {"article": "der", "plural": "-", "turkish": "sabah", "pos": "İsim (Nomen)", "ex_de": "Guten Morgen!", "ex_tr": "Günaydın!"},
    "abend": {"article": "der", "plural": "die Abende", "turkish": "akşam", "pos": "İsim (Nomen)", "ex_de": "Guten Abend allerseits!", "ex_tr": "Herkese iyi akşamlar!"},
    "uhr": {"article": "die", "plural": "die Uhren", "turkish": "saat", "pos": "İsim (Nomen)", "ex_de": "Wie viel Uhr ist es?", "ex_tr": "Saat kaç?"},
    "jahr": {"article": "das", "plural": "die Jahre", "turkish": "yıl, sene", "pos": "İsim (Nomen)", "ex_de": "Frohes neues Jahr!", "ex_tr": "Mutlu yıllar!"},
    "monat": {"article": "der", "plural": "die Monate", "turkish": "ay (takvim)", "pos": "İsim (Nomen)", "ex_de": "Ein Monat hat vier Wochen.", "ex_tr": "Bir ayda dört hafta vardır."},
    "woche": {"article": "die", "plural": "die Wochen", "turkish": "hafta", "pos": "İsim (Nomen)", "ex_de": "Schönes Wochenende!", "ex_tr": "İyi hafta sonları!"},
    # Fiiller (Verben)
    "lernen": {"article": "", "plural": "", "turkish": "öğrenmek, ders çalışmak", "pos": "Fiil (Verb)", "ex_de": "Ich lerne gern Deutsch.", "ex_tr": "Almanca öğrenmeyi seviyorum."},
    "verstehen": {"article": "", "plural": "", "turkish": "anlamak, kavramak", "pos": "Fiil (Verb)", "ex_de": "Ich verstehe diesen Satz nicht.", "ex_tr": "Bu cümleyi anlamıyorum."},
    "sprechen": {"article": "", "plural": "", "turkish": "konuşmak", "pos": "Fiil (Verb)", "ex_de": "Sprechen Sie Deutsch?", "ex_tr": "Almanca konuşuyor musunuz?"},
    "sehen": {"article": "", "plural": "", "turkish": "görmek, izlemek", "pos": "Fiil (Verb)", "ex_de": "Wir sehen einen deutschen Film.", "ex_tr": "Almanca bir film izliyoruz."},
    "gehen": {"article": "", "plural": "", "turkish": "gitmek, yürümek", "pos": "Fiil (Verb)", "ex_de": "Wohin gehst du?", "ex_tr": "Nereye gidiyorsun?"},
    "kommen": {"article": "", "plural": "", "turkish": "gelmek", "pos": "Fiil (Verb)", "ex_de": "Woher kommst du?", "ex_tr": "Nerelisin / nereden geliyorsun?"},
    "machen": {"article": "", "plural": "", "turkish": "yapmak, etmek", "pos": "Fiil (Verb)", "ex_de": "Was machst du heute?", "ex_tr": "Bugün ne yapıyorsun?"},
    "haben": {"article": "", "plural": "", "turkish": "sahip olmak", "pos": "Fiil (Verb)", "ex_de": "Ich habe eine Frage.", "ex_tr": "Bir sorum var."},
    "sein": {"article": "", "plural": "", "turkish": "olmak (yardımcı fiil)", "pos": "Fiil (Verb)", "ex_de": "Ich bin Student.", "ex_tr": "Ben öğrenciyim."},
    "helfen": {"article": "", "plural": "", "turkish": "yardım etmek (+Dativ)", "pos": "Fiil (Verb)", "ex_de": "Kann ich Ihnen helfen?", "ex_tr": "Size yardım edebilir miyim?"},
    "wissen": {"article": "", "plural": "", "turkish": "bilmek", "pos": "Fiil (Verb)", "ex_de": "Ich weiß es nicht.", "ex_tr": "Bunu bilmiyorum."},
    "fragen": {"article": "", "plural": "", "turkish": "sormak", "pos": "Fiil (Verb)", "ex_de": "Darf ich etwas fragen?", "ex_tr": "Bir şey sorabilir miyim?"},
    "antworten": {"article": "", "plural": "", "turkish": "cevap vermek", "pos": "Fiil (Verb)", "ex_de": "Bitte antworte mir schnell.", "ex_tr": "Lütfen bana çabuk cevap ver."},
    # Sıfatlar (Adjektive)
    "wichtig": {"article": "", "plural": "", "turkish": "önemli", "pos": "Sıfat (Adjektiv)", "ex_de": "Diese Regel ist sehr wichtig.", "ex_tr": "Bu kural çok önemlidir."},
    "schwierig": {"article": "", "plural": "", "turkish": "zor, güç", "pos": "Sıfat (Adjektiv)", "ex_de": "Die Grammatik ist nicht so schwierig.", "ex_tr": "Gramer o kadar zor değil."},
    "einfach": {"article": "", "plural": "", "turkish": "kolay, basit; sadece", "pos": "Sıfat (Adjektiv)", "ex_de": "Mit dieser App ist es ganz einfach.", "ex_tr": "Bu uygulama ile tamamen kolay."},
    "gut": {"article": "", "plural": "", "turkish": "iyi, güzel", "pos": "Sıfat (Adjektiv)", "ex_de": "Das ist eine sehr gute Idee.", "ex_tr": "Bu çok iyi bir fikir."},
    "schön": {"article": "", "plural": "", "turkish": "güzel, hoş", "pos": "Sıfat (Adjektiv)", "ex_de": "Das Wetter ist heute schön.", "ex_tr": "Hava bugün güzel."},
    "groß": {"article": "", "plural": "", "turkish": "büyük, uzun (boy)", "pos": "Sıfat (Adjektiv)", "ex_de": "Er hat ein großes Haus.", "ex_tr": "Onun büyük bir evi var."},
    "klein": {"article": "", "plural": "", "turkish": "küçük, ufak", "pos": "Sıfat (Adjektiv)", "ex_de": "Das ist ein kleines Problem.", "ex_tr": "Bu küçük bir problem."},
    "neu": {"article": "", "plural": "", "turkish": "yeni", "pos": "Sıfat (Adjektiv)", "ex_de": "Ich habe ein neues Buch.", "ex_tr": "Yeni bir kitabım var."},
    "alt": {"article": "", "plural": "", "turkish": "eski, yaşlı", "pos": "Sıfat (Adjektiv)", "ex_de": "Wie alt bist du?", "ex_tr": "Kaç yaşındasın?"},
    "schnell": {"article": "", "plural": "", "turkish": "hızlı, çabuk", "pos": "Sıfat (Adjektiv)", "ex_de": "Er lernt sehr schnell.", "ex_tr": "O çok hızlı öğreniyor."},
}

# Çoğul Form Eşleme İndeksi (Plural -> Singular Mapping)
PLURAL_INDEX: Dict[str, str] = {}
for base_singular, item in COMMON_VOCABULARY.items():
    pl = item.get("plural", "")
    if pl and pl != "-":
        # 'die Häuser' -> 'häuser'
        clean_pl = re.sub(r"^die\s+", "", pl.lower().strip())
        for variant in clean_pl.split("/"):
            v = variant.strip()
            if v:
                PLURAL_INDEX[v] = base_singular
                # ae, oe, ue transliterasyonlarını da ekle
                v_trans = v.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
                if v_trans != v:
                    PLURAL_INDEX[v_trans] = base_singular

# Ters İndeks: Türkçe Kelimeden Almancaya Çevrimdışı Eşleme (Türkçe -> Almanca)
TURKISH_TO_GERMAN_INDEX: Dict[str, str] = {}
for base_singular, item in COMMON_VOCABULARY.items():
    tr_text = item.get("turkish", "")
    for part in re.split(r"[,;/]", tr_text):
        clean_tr = part.strip().lower()
        if clean_tr and clean_tr not in TURKISH_TO_GERMAN_INDEX:
            TURKISH_TO_GERMAN_INDEX[clean_tr] = base_singular


def clean_text(raw_text: str) -> str:
    """
    Metindeki gereksiz boşlukları ve dış noktalama işaretlerini temizler.
    Kullanıcının seçtiği kelimenin etrafındaki tırnak, parantez veya sonundaki noktayı atar.
    """
    if not raw_text:
        return ""
    text = raw_text.strip()
    # Çoklu boşlukları teke indir
    text = re.sub(r"\s+", " ", text)
    # Eğer tek bir kelime veya 'der/die/das/ein/eine ...' kalıbıysa baştaki ve sondaki noktalama işaretlerini temizle
    # Ancak soru işareti veya ünlem cümle ise iç yapıyı bozma
    words = text.split()
    if len(words) <= 2:
        text = text.strip(".,!?:;\"'()[]{}„“»«-_~|` \t\r\n")
    return text


def is_single_word(text: str) -> bool:
    """Metnin tek bir kelime veya 'artikel + kelime' olup olmadığını tespit eder."""
    if not text:
        return False
    clean = clean_text(text)
    words = clean.strip().split()
    if len(words) == 1:
        # Tek bir kelime
        return True
    if len(words) == 2 and words[0].lower() in ARTICLES_SET:
        return True
    return False


def extract_base_word(text: str) -> Tuple[str, str]:
    """
    Kullanıcı 'der Tisch', 'die Frau', 'ein Auto' gibi bir ifade girdiyse
    artikeli ve esas isim kelimesini ayıklar.
    Döner: (artikel, kelime)
    """
    clean = clean_text(text)
    words = clean.strip().split()
    if not words:
        return "", ""

    if len(words) >= 2:
        first = words[0].lower()
        if first in ("der", "die", "das"):
            return first, words[1]
        elif first in ("eine", "keine"):
            # 'eine' veya 'keine' dişil belirtecidir
            return "die", words[1]
        elif first in ARTICLES_SET:
            # Diğer artikeller (ein, einen, einem vb.) için esas kelimeyi ver
            return "", words[1]

    return "", words[0]


def predict_gender_by_rules(word: str) -> Tuple[str, str]:
    """
    Almanca son ek kurallarına göre kelimenin artikelini tahmin eder.
    Döner: (artikel, kural_aciklamasi)
    """
    if not word:
        return "", ""
    w_clean = word.strip(".,!?:;\"'()[]{}„“»«-_~")
    w_lower = w_clean.lower()
    for pattern, article, explanation in SUFFIX_RULES:
        m = re.search(pattern, w_lower)
        if m:
            matched_suffix = m.group(1) if m.groups() else ""
            return article, explanation.format(suffix=matched_suffix)
    return "", ""


def analyze_sentence_grammar(sentence: str) -> List[Dict[str, str]]:
    """
    Cümledeki modal fiiller, ayrılabilen fiiller ve bağlaçları tespit eder.
    Almanca öğrenen kullanıcıya kesin ve hatasız gramer ipuçları üretir.
    """
    notes = []
    if not sentence or not sentence.strip():
        return notes

    raw_tokens = sentence.split()
    tokens_clean = [t.strip(".,!?:;\"'()[]{}„“»«") for t in raw_tokens]
    tokens_lower = [t.lower() for t in tokens_clean]

    # 1. Yan cümle bağlaç kontrolü (Fiili sona atanlar)
    for conj, desc in SUBORDINATING_CONJUNCTIONS.items():
        if conj in tokens_lower:
            notes.append({
                "type": "baglac",
                "badge": "Kural",
                "title": f"'{conj}' Bağlacı",
                "text": f"'{conj}' ({desc}) bağlacı bulunduğu yan cümlenin çekimli fiilini cümlenin EN SONUNA atar."
            })

    # 'da' bağlacı vs 'da' zarfı ("Ich bin da" zarftır, ", da ..." bağlaçtır)
    if "da" in tokens_lower:
        idx = tokens_lower.index("da")
        # Eğer cümlenin ilk kelimesi ise veya virgülle ayrılmış yan cümlenin başı ise ve devamında kelimeler varsa
        is_clause_start = (idx == 0 or (idx > 0 and raw_tokens[idx - 1].endswith(",")))
        if is_clause_start and len(tokens_lower) > idx + 2:
            notes.append({
                "type": "baglac",
                "badge": "Kural",
                "title": "'da' Bağlacı",
                "text": "'da' (için / -dığından dolayı) bağlacı yan cümlenin çekimli fiilini cümlenin sonuna gönderir."
            })

    # 'als' bağlacı vs 'als' karşılaştırma ("größer als ich" karşılaştırmadır, "als ich klein war" bağlaçtır)
    if "als" in tokens_lower:
        idx = tokens_lower.index("als")
        # Yanında fiil barındıran bir yan cümle mi?
        sub_clause = tokens_lower[idx:]
        if len(sub_clause) >= 3 and idx == 0:
            notes.append({
                "type": "baglac",
                "badge": "Kural",
                "title": "'als' Bağlacı",
                "text": "'als' (-dığı zaman) geçmişte tek seferlik bir olayı anlatan yan cümlenin fiilini en sona gönderir."
            })

    # 2. Modal fiil kontrolü
    for token in tokens_lower:
        if token in MODAL_VERBS:
            inf = MODAL_VERBS[token]
            notes.append({
                "type": "modal",
                "badge": "Modal Fiil",
                "title": f"'{token}' -> {inf}",
                "text": "Modal fiil çekimlenerek cümlenin 2. konumuna gelir; esas fiil ise yalın (mastar) halde cümlenin en sonuna gider."
            })
            break

    # 3. Ayrılabilen fiil (Trennbare Verben) kontrolü
    if len(tokens_clean) >= 2:
        last_token = tokens_clean[-1]
        last_lower = last_token.lower()

        # Durum A: Cümlenin sonunda tek başına ayrılabilir önek kalmış (örn: "Er steht früh auf.")
        if last_lower in SEPARABLE_PREFIXES:
            # Cümledeki çekimli fiili bulmaya çalış
            finite_verb = ""
            for tok in tokens_lower[1:]:
                if tok != last_lower and len(tok) >= 3:
                    finite_verb = tok
                    break
            verb_hint = f" ({last_lower} + {finite_verb})" if finite_verb else ""
            notes.append({
                "type": "trennbare",
                "badge": "Ayrılabilir Fiil",
                "title": f"Ayrılan Önek Sonda: '... {last_lower}'",
                "text": f"Cümlenin sonunda '{last_lower}' öneki bulunuyor. Bu cümlenin fiili ayrılabilen bir fiildir{verb_hint}."
            })
        # Durum B: Cümlenin sonunda veya mastar olarak birleşik ayrılabilir fiil var (örn: aufstehen, mitkommen)
        # ÖNEMLİ: Almanca isimler (Abend, Vorname, Aufgabe, Einkauf) ve sıfatlar elenmelidir!
        elif not last_token[0].isupper() and (last_lower.endswith("en") or last_lower.endswith("eln") or last_lower.endswith("ern")):
            for pfx in SEPARABLE_PREFIXES:
                if last_lower.startswith(pfx) and len(last_lower) >= len(pfx) + 3:
                    base_stem = last_lower[len(pfx):]
                    notes.append({
                        "type": "trennbare",
                        "badge": "Ayrılabilir Fiil",
                        "title": f"Ayrılabilir Fiil: '{last_lower}'",
                        "text": f"'{last_lower}' fiili '{pfx}-' ayrılabilir öneki içerir (Kök: {base_stem}, Präsens çekiminde '{pfx}' sona gider)."
                    })
                    break

    return notes


def get_offline_analysis(text: str) -> Optional[Dict[str, Any]]:
    """
    Eğer kelime veya çoğul hali temel Almanca veritabanımızda varsa anında çevrimdışı sonuç üretir.
    """
    clean = clean_text(text)
    if not is_single_word(clean):
        return None

    art, base = extract_base_word(clean)
    if not base:
        return None
    base_lower = base.lower()

    # 1. Doğrudan tekil kelime eşleşmesi
    if base_lower in COMMON_VOCABULARY:
        item = COMMON_VOCABULARY[base_lower].copy()
        article = art or item.get("article", "")
        return {
            "source": "offline_db",
            "german": base.capitalize() if article else base,
            "article": article,
            "article_color": ARTICLE_COLORS.get(article, "#6b7280"),
            "plural": item.get("plural", ""),
            "turkish": item.get("turkish", ""),
            "pos": item.get("pos", ""),
            "example_de": item.get("ex_de", ""),
            "example_tr": item.get("ex_tr", ""),
            "grammar_note": f"Artikeli '{article}' olan bir isimdir." if article else "",
            "is_sentence": False
        }

    # 2. Çoğul form eşleşmesi (Örn: 'Häuser' arandığında 'das Haus'u bul)
    if base_lower in PLURAL_INDEX:
        singular_key = PLURAL_INDEX[base_lower]
        item = COMMON_VOCABULARY[singular_key].copy()
        article = item.get("article", "")
        return {
            "source": "offline_db",
            "german": f"{singular_key.capitalize()} (Çoğul: die {base.capitalize()})",
            "article": article,
            "article_color": ARTICLE_COLORS.get(article, "#6b7280"),
            "plural": item.get("plural", ""),
            "turkish": item.get("turkish", ""),
            "pos": item.get("pos", ""),
            "example_de": item.get("ex_de", ""),
            "example_tr": item.get("ex_tr", ""),
            "grammar_note": f"Bu kelime çoğul formdadır ('die {base.capitalize()}'). Tekil hali: '{article} {singular_key.capitalize()}'.",
            "is_sentence": False
        }

    return None


def get_offline_reverse_analysis(text: str) -> Optional[Dict[str, Any]]:
    """
    Türkçe bir kelime verildiğinde çevrimdışı sözlükten Almanca karşılığını ve artikelini bulur.
    Örn: 'kitap' -> 'das Buch', 'araba' -> 'das Auto', 'ev' -> 'das Haus'
    """
    clean = clean_text(text).lower()
    if not is_single_word(clean):
        return None

    if clean in TURKISH_TO_GERMAN_INDEX:
        singular_key = TURKISH_TO_GERMAN_INDEX[clean]
        item = COMMON_VOCABULARY[singular_key].copy()
        article = item.get("article", "")
        display_german = singular_key.capitalize() if (article or item.get("pos") == "İsim (Nomen)") else singular_key
        return {
            "source": "offline_db",
            "direction": "tr_to_de",
            "detected_lang": "tr",
            "german": display_german,
            "article": article,
            "article_color": ARTICLE_COLORS.get(article, "#6b7280"),
            "plural": item.get("plural", ""),
            "turkish": text,
            "pos": item.get("pos", ""),
            "example_de": item.get("ex_de", ""),
            "example_tr": item.get("ex_tr", ""),
            "grammar_note": f"Almanca karşılığı: '{article} {display_german}'.",
            "original": text,
            "translation": f"{article} {display_german}".strip(),
            "is_sentence": False
        }
    return None

