# 🇩🇪 Ekran Sözlüğü (ScreenLingo • DeutschOverlay)
## Mimari Tasarım ve Geliştirme Planı

Bu belge, video izlerken veya yazı okurken ekran başındaki kullanıcının akışını (flow state) bozmadan anında Almanca kelime ve cümle çevirisi yapmasını sağlayan **Ekran Sözlüğü** uygulamasının mimarisini, kullanıcı deneyimi planını ve teknik detaylarını açıklamaktadır.

---

### 1. Problem Tanımı ve Kullanıcı Deneyimi Analizi

#### Mevcut Durumdaki Sürtünme (Friction Points):
- Kullanıcı YouTube, Netflix veya Udemy'de Almanca video izlerken bilmediği bir kelimeyle karşılaştığında:
  1. Videoyu durdurmak zorunda kalıyor.
  2. Tarayıcıya geçip Google Çeviri veya sözlük sekmesini açıyor.
  3. Kelimeyi veya cümleyi klavyeyle (ä, ö, ü, ß gibi özel karakterlerle) yazmaya çalışıyor.
  4. Çeviriyi okuyup tekrar videoya dönüyor ve devam ettiriyor.
- **Sonuç:** Dikkat dağılıyor, odak kayboluyor, video zevki ve dil öğrenme verimi %70 oranında düşüyor.

#### Ekran Sözlüğü Çözümü (0 Sürtünme Prensibi):
- Kullanıcı hiçbir sekmeye geçmez, videoyu durdurma zorunluluğu ortadan kalkar.
- **Seçilebilir Metinler için:** Metni seçip `Ctrl+C` yapmak yeterlidir; anında şık bir HUD kartı belirir.
- **Videolar ve Gömülü Altyazılar için:** "Kırp (OCR)" butonuna basarak altyazıyı fareyle çerçeve içine alır; Windows yerel OCR motoru mili saniyeler içinde okur ve ekrana çeviriyi getirir.

---

### 2. Sistem Mimarisi

```
+-------------------------------------------------------------------------+
|                              KULLANICI ARAYÜZÜ                           |
|  [ Yüzen Kontrol Çubuğu ]  <--->  [ Anlık Çeviri HUD Kartı ]  <--->   |
|  [ Ekran Bölge Seçici (OCR) ]     [ Kelime Defteri & Flashcards ]      |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                             ÇEKİRDEK SERVİSLER                          |
|                                                                         |
|  +---------------------+  +---------------------+  +--------------------+  |
|  |   Pano Dinleyicisi  |  |   OCR Motoru        |  |  Ses Motoru (TTS)  |  |
|  |  (Clipboard Watcher)|  | (Windows Media OCR) |  | (Kullanıcı İsteği  |  |
|  |   Win32 / Ctypes    |  | PIL Image Preproc   |  |  ile Çıkarıldı)    |  |
|  +---------------------+  +---------------------+  +--------------------+  |
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  |                     ÇEVİRİ VE DİLBİLGİSİ MOTORU                   |  |
|  | - Artikel & Renk Çözücü (der: Mavi, die: Kırmızı, das: Yeşil)    |  |
|  | - Kural Tabanlı Son Ek Ayrıştırıcı (-ung, -heit, -keit, -ment)    |  |
|  | - Ayrılabilen Fiil (Trennbare Verben) ve Modal Fiil Dedektörü     |  |
|  | - Yan Cümle Bağlaç Uyarısı ('weil', 'dass' fiili sona atar)        |  |
|  | - Wiktionary Morfoloji Ayrıştırıcısı + Google Translate Engine    |  |
|  | - İsteğe Bağlı Gemini AI Derin Açıklama Entegrasyonu              |  |
|  +-------------------------------------------------------------------+  |
+------------------------------------+------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                        VERİ DEPOLAMA VE ÖNBELLEK                        |
|   SQLite Veritabanı (ekran_sozlugu.db):                                  |
|   1. cache: Çevrilen kelimeleri saklar (0ms çevrimdışı anında erişim)   |
|   2. wordbook: Kullanıcının yıldızladığı kelimeler ve durumları          |
|   3. history: Son yapılan arama geçmişi                                 |
+-------------------------------------------------------------------------+
```

---

### 3. Almanca Öğrenenlere Özel Gelişmiş Özellikler

1. **Görsel Artikel Kodlaması (Visual Gender Encoding):**
   - Almancada artikeller isim öğrenmenin temelidir.
   - `der` -> **Mavi** (Eril / Maskulinum)
   - `die` -> **Kırmızı** (Dişil / Femininum)
   - `das` -> **Yeşil** (Nötr / Neutrum)
   - Kelime kartında artikel büyük puntolarla ve bu renklerle vurgulanır.

2. **Kural Tabanlı Artikel Tahmini (Suffix Prediction):**
   - Bilinmeyen veya nadir kelimelerde bile Almanca kuralları devreye girer:
     - `-ung`, `-heit`, `-keit`, `-schaft`, `-ion`, `-tät` -> **die**
     - `-ling`, `-ismus`, `-ist`, `-or`, `-ent` -> **der**
     - `-chen`, `-lein`, `-ment`, `-um`, `-tum` -> **das**

3. **Cümle İçi Gramer Tespiti:**
   - Cümle çevirilerinde Türkçe karşılığın altında gramer ipuçları listelenir:
     - *'weil'* bağlacı görüldüğünde: *"Bu bağlaç fiili cümlenin en sonuna gönderir."*
     - *'muss/musste/kann'* görüldüğünde: *"Modal fiil 2. pozisyondadır, esas fiil mastar olarak cümlenin sonundadır."*
     - *'aufstehen'* veya *'steht... auf'* görüldüğünde: *"Ayrılabilir fiil (Trennbare Verben)."*

4. **Sesli Telaffuz / Dinleme (Kullanıcı İsteği ile Kaldırıldı):**
   - Kullanıcının telaffuzları kendi tercih ettiği harici kaynaktan dinlemesi doğrultusunda bu özellik uygulamadan ve arayüzden tamamen çıkarılmıştır.

5. **Kişisel Kelime Defteri ve Anki Entegrasyonu:**
   - Videoyu izlerken tek tıkla ⭐ butonuna basarak kelime defterine ekleme.
   - İstenildiğinde kelimeleri Anki (.txt / .csv) formatında tek tıkla dışa aktarabilme.
   - Uygulama içinde dahili Flashcard çalışma modu.

---

### 4. Teknik Yol Haritası ve Fazlar

| Faz | Açıklama | Durum |
| :--- | :--- | :--- |
| **Faz 1: Çekirdek Motorlar** | SQLite, Çeviri motoru, Wiktionary ayrıştırıcı, Almanca kuralları (TTS kaldırıldı) | Tamamlandı |
| **Faz 2: OCR ve Görüntü İşleme** | Windows Media OCR entegrasyonu, Lanczos upscale, kontrast artırma | Tamamlandı |
| **Faz 3: Kullanıcı Arayüzü** | Yüzen kontrol çubuğu, Result HUD kartı, Bölge kırpıcı, Ayarlar | Tamamlandı |
| **Faz 4: Kelime Defteri & Flashcards** | Filtreleme, arama, interaktif kartlar, Anki dışa aktarma | Tamamlandı |
| **Faz 5: Test ve Kararlılık** | 23 otomatik birim ve uç nokta (edge-case) testi | Tamamlandı |
| **Gelecek Faz: Global Kısayol Tuşları** | Windows API RegisterHotKey ile arka planda çalışırken genel tuş ataması | Sıradaki Adım |
