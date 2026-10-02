# 🇩🇪 Ekran Sözlüğü (ScreenLingo • DeutschOverlay)

> **Almanca Öğrenenler İçin Akıllı Masaüstü Ekran ve Video Altyazı Çeviri Asistanı**

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6.svg)](https://www.microsoft.com/windows)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![OCR Engine](https://img.shields.io/badge/OCR-Windows%20Media%20OCR-brightgreen.svg)]()

Almanca dizi, film, YouTube videosu izlerken veya internette makale okurken bilmediğiniz bir kelime ya da ifade çıktığında videoyu durdurup tarayıcıda sözlük arama derdine son!

**Ekran Sözlüğü**, Windows masaüstünüzün üzerinde sessizce çalışan modern, yarı saydam ve hafif bir asistandır. Farenizi altyazının üzerine getirip yan tuşa basarak veya tek bir kısayolla ekrandaki kelimeleri çok kısa sürede algılar, **renkli artikelleri (`der`, `die`, `das`)**, **çoğul biçimleri** ve **Türkçe anlamlarıyla** ekrana getirir.

---

## 📸 Kullanım Önizlemesi

```text
┌───────────────────────────────────────────────────────────────────────────┐
│ [Video / YouTube / Netflix Altyazısı]                                     │
│                                                                           │
│               "Wir müssen heute diese Entscheidung treffen."              │
│                                           ▲                               │
│                                           │ (Fare Yan Tuşu: Mouse 4/5)    │
│                                                                           │
│       ┌───────────────────────────────────────────────────────────┐       │
│       │  🔴 DIE Entscheidung  (Pl: die Entscheidungen)         ⭐ │       │
│       │  karar (seçim, hüküm)                                     │       │
│       │  💡 İpucu: -ung eki alan isimler 'die' artikeli alır.     │       │
│       └───────────────────────────────────────────────────────────┘       │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Öne Çıkan Özellikler

### 1. 🖱️ Fare Yan Tuşları ile Canlı Çeviri (Mouse 4/5 Hover OCR)
- Videoyu izlerken farenizi altyazıdaki herhangi bir kelimenin üzerine getirin ve farenizin yan tuşuna (**Mouse 4** veya **Mouse 5**) basın.
- Ekranın o küçük bölgesini anında mikro-kırpma ile Windows Media OCR motoruna gönderir; farenin altındaki tam kelimeyi koordinatlarıyla bularak farenin üzerinde yarı saydam bir mini çeviri kartı açar.
- Video oynatıcınızın veya tarayıcınızın "Geri/İleri" gitmesini engelleyerek video akışını kesintiye uğratmaz.
- Fare kelimeden uzaklaştığı an kart kendiliğinden kaybolur.

### 2. ✂️ Dondurulmuş Kare Ekran Kırpıcı (`Tab + Space`)
- Kopyalanamayan veya hızlı geçen video altyazılarında **`Tab + Space`** tuşlarına basın.
- Ekran o karede dondurulur; altyazıyı farenizle çerçeve içine alıp bıraktığınız anda çeviri sonuç kartı (HUD) açılır.

### 3. 🎨 Renk Kodlu Artikeller ve Gramer Ayrıştırıcı
- Almanca isimlerin artikelleri renk kodlamasıyla sunulur:
  - 🔵 **der** (Maskulinum - Mavi)
  - 🔴 **die** (Femininum - Kırmızı)
  - 🟢 **das** (Neutrum - Yeşil)
- Kelimenin çoğul hali (`die Häuser`, `die Entscheidungen`), kelime türü (`Nomen`, `Verb`, `Adjektiv`) ve dilbilgisi son ek kuralları (`-ung`, `-heit`, `-keit`, `-ment` vb.) otomatik açıklanır.

### 4. 🤖 Google Gemini AI Entegrasyonu (Düşük Tüketimli Flash Modelleri)
- Ayarlar menüsünden Google Gemini API anahtarınızı bağlayabilirsiniz.
- **Hafif ve Ekonomik:** Google AI Studio'nun yüksek performanslı ve düşük token tüketen Flash modelleriyle (`gemini-1.5-flash`, `gemini-2.0-flash` vb.) tüm metinleri ve cümleleri derin dilbilgisi analizleriyle Türkçeye çevirir.
- **Canlı Test Butonu:** API anahtarınızın çalışıp çalışmadığını ayarlar menüsündeki `🔍 Test Et` butonuyla anında doğrulayabilirsiniz.

### 5. 📋 Otomatik Pano Takibi (`Ctrl + C`)
- İnternette veya PDF okurken herhangi bir Almanca metni seçip `Ctrl+C` yaptığınız an, arka plan dinleyicisi metni yakalar ve ekranınızda çevirisini gösterir.

### 6. 📚 Kişisel Kelime Defteri ve Flashcards
- Beğendiğiniz veya öğrenmek istediğiniz kelimeleri tek tıkla (**⭐**) defterinize ekleyin.
- Dahili Flashcard arayüzü ile kelimeleri pratik yapın.
- Kelimelerinizi **Anki** uyumlu CSV formatında dışa aktarın.

### 7. ⚡ Çevrimdışı SQLite Önbellek (Offline Cache)
- Daha önce bakılan veya sık kullanılan 1.000+ temel Almanca kelime çevrimdışı yerel veritabanında saklanır.
- İnternet bağlantınız olmasa dahi anında yanıt verir ve gereksiz kota tüketmez.

---

## ⌨️ Global Kısayol Tuşları (Tam Ekran ve Video Dostu)

Uygulama arka plandayken veya tam ekran bir video/oyun açıkken dahi kısayollar doğrudan çalışır:

| Kısayol | Fonksiyon | Açıklama |
| :--- | :--- | :--- |
| **`Ctrl + C`** | **Otomatik Pano Çevirisi** | Herhangi bir uygulamada metin seçip kopyaladığınız anda çeviri kartı otomatik açılır. |
| **`Fare Yan Tuşları`** | **Nokta Atışı Hover OCR** | Farenin altındaki kelimeyi okur ve üzerinde mini çeviri balonu açar (Mouse 4/5). |
| **`Tab + Space`** | **Ekran Kırp / OCR** | Ekranı o karede dondurur ve altyazıyı çerçeve içine alıp çevirmenizi sağlar. |
| **`Alt + V`** | **Hover Modu Aç/Kapa** | Canlı fare okuma özelliğini klavyeden anında açıp kapatır. |
| **`Alt + H`** | **Çubuğu Gizle / Göster** | Yüzen kontrol çubuğunu gizler veya geri getirir. |
| **`Alt + C`** | **Seçili Metni / Panoyu Çevir** | Ekranda seçtiğiniz kelimeyi veya panodaki metni klavyeden anında kopyalayıp çevirir. |

> ⚙️ **Kısayolları Özelleştirme:** Çubuktaki **`⚙` (Ayarlar)** butonuna tıklayarak kısayolları dilediğiniz tuş kombinasyonuyla (`tab+space`, `alt+x`, `ctrl+space`, `f2` vb.) değiştirebilirsiniz.

---

## 🚀 Kurulum ve Çalıştırma

### Gereksinimler
- **İşletim Sistemi:** Windows 10 veya Windows 11 (64-bit)
- **Python:** Python 3.10 veya üzeri
- Windows yerel OCR desteği (Windows Türkçe veya Almanca OCR dil paketleri yüklü olmalıdır)

### 1. Repoyu Klonlayın
```bash
git clone https://github.com/SandL0J/On-screen-dictionary.git
cd On-screen-dictionary
```

### 2. Gerekli Paketleri Yükleyin
```bash
pip install -r requirements.txt
```

### 3. Uygulamayı Başlatın
**Windows Tek Tık ile Başlatma:**
Klasör içindeki `run_app.bat` dosyasına çift tıklayarak doğrudan başlatabilirsiniz.

**Komut Satırından Başlatma:**
```bash
python main.py
```

---

## 💾 Veri Konumu ve Yedekleme

Ekran Sözlüğü kullanıcı ayarlarını, kelime defterini ve hata günlüklerini Windows standart kullanıcı veri klasöründe saklar:

- **Veri Klasörü:** `%APPDATA%\EkranSozlugu` (örneğin: `C:\Users\<Kullanıcı>\AppData\Roaming\EkranSozlugu`)
- **Saklanan Dosyalar:**
  - `config.json`: Kullanıcı tercihleri, kısayol tuşları ve Gemini API ayarları
  - `ekran_sozlugu.db`: Kelime defteri (SM-2 aralıklı tekrar verileri), çevrimdışı önbellek ve geçmiş
  - `ekran_sozlugu_error.log`: Uygulama hata günlüğü

> 🔄 **Otomatik Veri Göçü (Migration):** Uygulama başlatıldığında, proje klasöründeki eski kullanıcı verileri (`config.json`, `ekran_sozlugu.db` ve SQLite `-wal`/`-shm` yan dosyaları) hedefte henüz yoksa `%APPDATA%\EkranSozlugu` altına **otomatik olarak kopyalanır**. Kaynak dosyalar asla silinmez veya mevcut verilerin üzerine yazılmaz; kullanıcı verileri her zaman güvendedir.
>
> 📦 **Yedek Alma:** Kelime defterinizi ve ayarlarınızı yedeklemek veya yeni bir bilgisayara aktarmak için `%APPDATA%\EkranSozlugu` klasörünü kopyalamanız yeterlidir.

---

## 📁 Proje Mimarisi

```
On-screen-dictionary/
├── app/
│   ├── config.py              # Uygulama ayarları yönetimi
│   ├── database.py            # SQLite veritabanı (önbellek, defter, geçmiş)
│   ├── gemini_service.py      # Google Gemini REST API entegrasyonu ve doğrulaması
│   ├── german_analyzer.py     # Almanca artikel tahmincisi ve dilbilgisi kuralları
│   ├── hotkey_manager.py      # Win32 düşük seviyeli global klavye dinleyicisi
│   ├── hover_tracker.py       # Fare yan tuşları (Mouse 4/5) ve imleç takip motoru
│   ├── ocr_engine.py          # Windows Media OCR & kelime koordinat eşleştiricisi
│   ├── paths.py               # Kullanıcı veri yolları (%APPDATA%) ve otomatik veri göçü
│   ├── startup_manager.py     # Windows başlangıç kayıt defteri yönetimi
│   ├── translator.py          # Türkçe hedef dilli ana çeviri motoru
│   ├── tray_manager.py        # Windows sistem tepsisi (System Tray) entegrasyonu
│   └── gui/
│       ├── hover_tooltip.py   # Fare üstü yarı saydam mini çeviri balonu
│       ├── main_overlay.py    # Yüzen modern kontrol çubuğu
│       ├── result_hud.py      # Çeviri sonuç ve dilbilgisi kartı (HUD)
│       ├── settings_window.py # Ayarlar ve Gemini API yönetim penceresi
│       ├── snipper.py         # Ekran dondurmalı bölge kırpıcı
│       └── wordbook_window.py # Kelime defteri ve flashcard arayüzü
├── tests/                     # 155 birim ve regresyon testinden oluşan test paketi
├── main.py                    # Uygulama ana giriş noktası
├── run_app.bat                # Hızlı Windows başlatıcı
├── test_mouse_trigger.py      # Fare tuşu ve OCR teşhis aracı
├── requirements.txt           # Python bağımlılıkları
├── config.example.json        # Örnek yapılandırma şablonu
├── .gitignore                 # Git yoksayma kuralları
├── LICENSE                    # MIT Lisansı
└── README.md                  # Proje dokümantasyonu
```

---

## 🧪 Testleri Çalıştırma

Tüm test paketini çalıştırmak için:
```bash
python -m unittest discover -s tests -v
```

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) altında lisanslanmıştır. Dilediğiniz gibi kullanabilir, geliştirebilir ve paylaşabilirsiniz.
