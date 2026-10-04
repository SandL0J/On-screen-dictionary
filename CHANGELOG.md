# Değişiklik Günlüğü (Changelog)

Bu projedeki tüm önemli değişiklikler bu dosyada belgelenmektedir.
Biçim [Keep a Changelog](https://keepachangelog.com/tr/1.0.0/) standardına dayanmaktadır.

## [0.9.0-rc1] - 2026-10-04

### Güvenlik ve Gizlilik (Security & Privacy)
- **Windows DPAPI Şifreleme:** Gemini API anahtarları `CryptProtectData` ile şifreli (`dpapi:...`) olarak saklanır; loglarda ve hata çıktılarında asla açık metin gösterilmez.
- **REST Başlık Yetkilendirmesi:** Gemini API anahtarları URL query parametresi yerine güvenli `x-goog-api-key` HTTP başlığında taşınır.
- **Kapsamlı Hassas Veri Filtresi:** API anahtarları, JWT, token, etiketli/çok satırlı parolalar, Luhn algoritmalı kredi kartları ve harf büyüklüğünden bağımsız/gruplu IBAN tespiti devrededir. Filtre hem arka plan pano dinleyicisine hem de manuel ekran kırpma (`lookup_text`) ve fare hover (`_inspect_hover_area`) tetikleyicilerine entegre edilmiştir.

### Eşzamanlılık ve Yaşam Döngüsü (Concurrency & Lifecycle)
- **Sınırlı İş Parçacığı Havuzu:** Başıboş daemon thread'ler yerine en fazla 4 iş parçacıklı `WorkerThreadPool` (`DaemonThreadPoolExecutor`) devreye alındı.
- **Daemon Thread Güvencesi:** Tüm havuz iş parçacıkları `daemon=True` olarak yapılandırıldı; yavaş veya asılı ağ istekleri uygulama kapanışını engellemez.
- **Yarış Durumu Koruması (Generation ID):** `_lookup_generation` ile eski/gecikmiş ağ aramalarının yeni arama sonuçlarını ezmesi engellendi.
- **Tekil Uygulama Örneği (Single Instance Mutex):** Windows `CreateMutexW` API'si ile aynı anda birden fazla uygulama örneğinin açılması engellendi; ikinci kopya açıldığında mevcut pencere öne getirilir.
- **Tkinter Zamanlayıcı İzolasyonu:** `root.after` çağrıları kayıt altına alındı; `stop()` esnasında tüm zamanlayıcılar eksiksiz iptal edilir, Tcl `invalid command name` konsol uyarıları sıfırlandı.

### Veri Bütünlüğü ve Depolama (Data Integrity)
- **Atomik SQLite Göçü:** `migrate_legacy_data` yerel `sqlite3.Connection.backup()` ile salt-okunur modda çalışır; geçici benzersiz dosya (`.tmp`) üzerinden `PRAGMA integrity_check` doğrulaması ve atomik kurulum yapılır.
- **Atomik Ayar Kaydı:** `save_config` ayarları geçici dosyaya yazıp `os.replace` + `fsync` ile hedefe taşır.

### Test ve Dayanıklılık (QA & Resilience)
- **238 Test (%100 Başarı):** Dış ağdan tamamen yalıtılmış deterministik ortamda 238 birim, entegrasyon, güvenlik ve stres testi başarıyla çalışmaktadır.
- **Stres Testleri:** 50 ardışık arama, hızla peş peşe 20 arama (rapid-fire), 10 kez art arda kur/durdur yaşam döngüsü ve işlem ortasında ani kapanış (in-flight abort) testleri doğrulandı.

## [0.9.0] - 2026-10-03

### Yenilikler ve İyileştirmeler
- SM-2 aralıklı tekrar sistemi (1 gün → 6 gün → aralık × ease factor, ease alt sınırı 1.3)
- Flashcard arayüzü: kart çevrilince 4 dereceli puanlama (Yeniden/Zor/İyi/Kolay), vadesi gelenler kuyruğu, "Tüm Kelimeler" modu
- Canlı sayaçlar: Toplam / Bugün Tekrar / Öğrenilen
- Hover modu kapalıyken fare yan tuşları (Mouse 4/5) tarayıcıya serbest bırakılır
- Hover kartına kapatma çarpısı (✕) ve ayarlanabilir otomatik kapanma süresi (Ayarlar'dan 0–60 sn)
- Kullanıcı verisi (config.json, ekran_sozlugu.db, hata logu) %APPDATA%\EkranSozlugu altına taşındı; eski dosyalar ilk açılışta oraya KOPYALANIR, kod klasöründeki orijinaller silinmez
- Test paketi: 231 testin tamamı dış ağ sızıntısı olmadan izole ortamda başarıyla geçti (0 hata, 0 atlama, süre: ~9.8 saniye)
- CI/CD ve Test Otomasyonu: GitHub Actions üzerinde Windows Server runner ve Python 3.10/3.11/3.12 matrisi (`ci.yml`) ile etiket tetiklemeli otomatik paketleme ve release pipeline'ı (`release.yml`) kuruldu
- Windows Dağıtımı ve Installer: PyInstaller onedir spesifikasyonu (`ekran_sozlugu.spec`), per-user Inno Setup scripti (`setup.iss`) ve çoklu çözünürlüklü uygulama ikonu (`app_icon.ico`) oluşturuldu

### İşletim Sistemi ve Dağıtım Notları
- **İşletim Sistemi Desteği:** Birincil hedef Windows 11 (64-bit). Windows 10 (Sürüm 1809+) en iyi çaba (best-effort) esasıyla desteklenmektedir (Microsoft resmi Windows 10 Home/Pro desteği 14 Ekim 2025 itibarıyla sona ermiştir).
- **Kurulum:** Bağımsız Windows yükleyicisi (`EkranSozlugu-Setup-v0.9.0.exe`) veya Python 3.10+ kaynak koddan çalıştırma desteklenir.
- **SmartScreen Uyarısı:** Kurulum paketi açık kaynaklı ve imzasız (self-signed / unsigned) olduğundan ilk çalıştırmada Windows Defender SmartScreen "Bilinmeyen Yayımcı" uyarısı verebilir ("Ek Bilgi" -> "Yine de Çalıştır").
- **OCR Gereksinimi:** Windows Media OCR için sistemde Almanca dil paketinin kurulu olması önerilir.
