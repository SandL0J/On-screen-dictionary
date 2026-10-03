# Değişiklik Günlüğü (Changelog)

Bu projedeki tüm önemli değişiklikler bu dosyada belgelenmektedir.
Biçim [Keep a Changelog](https://keepachangelog.com/tr/1.0.0/) standardına dayanmaktadır.

## [0.9.0] - 2026-10-03

### Yenilikler ve İyileştirmeler
- SM-2 aralıklı tekrar sistemi (1 gün → 6 gün → aralık × ease factor, ease alt sınırı 1.3)
- Flashcard arayüzü: kart çevrilince 4 dereceli puanlama (Yeniden/Zor/İyi/Kolay), vadesi gelenler kuyruğu, "Tüm Kelimeler" modu
- Canlı sayaçlar: Toplam / Bugün Tekrar / Öğrenilen
- Hover modu kapalıyken fare yan tuşları (Mouse 4/5) tarayıcıya serbest bırakılır
- Hover kartına kapatma çarpısı (✕) ve ayarlanabilir otomatik kapanma süresi (Ayarlar'dan 0–60 sn)
- Kullanıcı verisi (config.json, ekran_sozlugu.db, hata logu) %APPDATA%\EkranSozlugu altına taşındı; eski dosyalar ilk açılışta oraya KOPYALANIR, kod klasöründeki orijinaller silinmez
- Test paketi: 155 testin tamamı başarıyla geçti (0 hata, 0 atlama, süre: 14.6 saniye)

### Bilinen Sınırlar
- Yalnızca Windows 10/11 desteklenmektedir.
- Python 3.10+ ve pip ile kurulum gerekir (henüz .exe yok).
- Çeviri için internet gerekir (çevrimdışı mod sınırlı).
- Windows OCR dil paketleri gerekir.
