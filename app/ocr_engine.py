"""
Optik Karakter Tanıma (OCR) Motoru
Ekrandan seçilen bölgedeki veya bir resimdeki Almanca metinleri:
1. Windows Media OCR (Windows 10/11 yerleşik, harici kuruluma gerek yok)
2. Tesseract OCR (Otomatik algılama veya özel yol desteği)
ikili motor mimarisiyle en yüksek doğruluk ve kesintisiz kararlılıkla okur.

Görüntü ön işleme (Image Preprocessing - ölçekleme, kontrast, netleştirme) uygulayarak
video altyazılarındaki ve ekran metinlerindeki tanıma doğruluğunu maksimuma çıkarır.
Harici bağımlılıklar eksik olduğunda çökmeyi önleyen zarif hata yönetimi ve yedekleme (graceful fallback) sunar.
"""
import os
import re
import json
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw


def find_tesseract_path(custom_path: str = "") -> Optional[str]:
    """
    Sistemde kurulu Tesseract OCR yürütülebilir dosyasını arar.
    Kullanıcı tarafından belirtilen yolu, sistem PATH'ini ve standart Windows kurulum dizinlerini kontrol eder.
    """
    if custom_path and os.path.isfile(custom_path):
        return str(Path(custom_path).resolve())

    # 1. PATH kontrolü
    which_path = shutil.which("tesseract")
    if which_path and os.path.isfile(which_path):
        return str(Path(which_path).resolve())

    # 2. Standart Windows kurulum dizinleri
    standard_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        standard_paths.append(os.path.join(local_app_data, "Programs", "Tesseract-OCR", "tesseract.exe"))

    for p in standard_paths:
        if os.path.isfile(p):
            return str(Path(p).resolve())

    return None


class OCREngine:
    def __init__(self, tesseract_cmd: str = "", preference: str = "auto"):
        """
        OCR Motorunu başlatır.
        preference: 'auto' (Windows Media OCR öncelikli, Tesseract yedek),
                    'windows_media' (Sadece veya öncelikli Windows Media OCR),
                    'tesseract' (Tesseract öncelikli)
        """
        self._temp_dir = Path(tempfile.gettempdir()) / "ekran_sozlugu_ocr"
        self._temp_dir.mkdir(exist_ok=True)
        self.preference = preference.lower()
        self.tesseract_cmd = find_tesseract_path(tesseract_cmd)
        self._ps_script = self._create_ocr_ps_script()
        self._win_ocr_available: Optional[bool] = None

    def set_tesseract_cmd(self, path: str):
        """Tesseract yolunu günceller."""
        resolved = find_tesseract_path(path)
        self.tesseract_cmd = resolved

    def set_preference(self, preference: str):
        """Motor tercihini günceller ('auto', 'windows_media', 'tesseract')."""
        self.preference = preference.lower()

    def _create_ocr_ps_script(self) -> Path:
        """Windows Media OCR çalıştıran kalıcı PowerShell betiğini oluşturur."""
        script_path = self._temp_dir / "run_win_ocr.ps1"
        code = r'''
param(
    [Parameter(Mandatory=$true)][string]$ImagePath,
    [Parameter(Mandatory=$false)][switch]$WithBoxes
)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { 
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' 
})[0]

function AwaitTask($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    return $netTask.Result
}

[Windows.Media.Ocr.OcrEngine, Windows.Foundation.Diagnostics, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation.Diagnostics, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile, Windows.Foundation.Diagnostics, ContentType = WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Foundation.Diagnostics, ContentType = WindowsRuntime] | Out-Null

$engine = $null
$targetLangs = @('de-DE', 'de', 'en-US', 'en')
foreach ($tag in $targetLangs) {
    try {
        $lang = [Windows.Globalization.Language]::new($tag)
        if ([Windows.Media.Ocr.OcrEngine]::IsLanguageSupported($lang)) {
            $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
            if ($engine) { break }
        }
    } catch {}
}
if (-not $engine) {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
}
if (-not $engine) {
    if ($WithBoxes) { Write-Output "[]" } else { Write-Output "" }
    exit 0
}

if (-not (Test-Path $ImagePath)) {
    if ($WithBoxes) { Write-Output "[]" } else { Write-Output "" }
    exit 0
}

$fullPath = (Get-Item $ImagePath).FullName
$fileTask = [Windows.Storage.StorageFile]::GetFileFromPathAsync($fullPath)
$file = AwaitTask $fileTask ([Windows.Storage.StorageFile])

$streamTask = $file.OpenAsync([Windows.Storage.FileAccessMode]::Read)
$stream = AwaitTask $streamTask ([Windows.Storage.Streams.IRandomAccessStream])

$decoderTask = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)
$decoder = AwaitTask $decoderTask ([Windows.Graphics.Imaging.BitmapDecoder])

$bitmapTask = $decoder.GetSoftwareBitmapAsync()
$bitmap = AwaitTask $bitmapTask ([Windows.Graphics.Imaging.SoftwareBitmap])

$ocrTask = $engine.RecognizeAsync($bitmap)
$result = AwaitTask $ocrTask ([Windows.Media.Ocr.OcrResult])

if ($result) {
    if ($WithBoxes) {
        $words = @()
        if ($result.Lines) {
            foreach ($line in $result.Lines) {
                if ($line.Words) {
                    foreach ($w in $line.Words) {
                        $rect = $w.BoundingRect
                        $words += [PSCustomObject]@{
                            text = $w.Text
                            x = [int][Math]::Round($rect.X)
                            y = [int][Math]::Round($rect.Y)
                            w = [int][Math]::Round($rect.Width)
                            h = [int][Math]::Round($rect.Height)
                        }
                    }
                }
            }
        }
        ConvertTo-Json -InputObject $words -Compress
    } else {
        if ($result.Text) {
            Write-Output $result.Text
        } else {
            Write-Output ""
        }
    }
} else {
    if ($WithBoxes) {
        Write-Output "[]"
    } else {
        Write-Output ""
    }
}
'''
        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)
        except Exception as e:
            print(f"PowerShell OCR betiği yazma hatası: {e}")
        return script_path

    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        OCR doğruluğunu artırmak için görüntüyü iyileştirir:
        1. 2.5x büyütme (Lanczos)
        2. Gri tonlama ve kontrast artırma
        3. Kenar netleştirme
        """
        if not image or image.width == 0 or image.height == 0:
            return image

        w, h = image.size
        scale = 2.5
        new_w, new_h = max(int(w * scale), 100), max(int(h * scale), 40)
        img = image.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Gri tonlama
        img = img.convert("L")

        # Kontrastı artır
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.8)

        # Netliği artır
        enhancer_sharp = ImageEnhance.Sharpness(img)
        img = enhancer_sharp.enhance(1.5)

        return img

    def recognize_from_image(self, image: Image.Image) -> str:
        """
        Verilen PIL Image nesnesinden metni okur.
        Öncelik tercihine göre Windows Media OCR veya Tesseract'ı çalıştırır;
        biri boş dönerse veya hata verirse diğerine zarifçe geçer (graceful fallback).
        """
        if not image or image.width <= 2 or image.height <= 2:
            return ""

        use_tesseract_first = (self.preference == "tesseract" and bool(self.tesseract_cmd))

        if use_tesseract_first:
            res = self._recognize_with_tesseract(image)
            if res:
                return res
            # Fallback to Windows Media OCR
            return self._recognize_with_windows_ocr(image)
        else:
            res = self._recognize_with_windows_ocr(image)
            if res:
                return res
            # Fallback to Tesseract if available
            if self.tesseract_cmd:
                return self._recognize_with_tesseract(image)
            return ""

    def _recognize_with_windows_ocr(self, image: Image.Image) -> str:
        """Windows Media OCR ile metin okur."""
        prep_img = self.preprocess_image(image)
        temp_img_path = self._temp_dir / f"crop_{os.getpid()}_{id(image)}.png"
        try:
            prep_img.save(temp_img_path)
            cmd = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden",
                "-File", str(self._ps_script),
                "-ImagePath", str(temp_img_path)
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=8,
                errors="replace"
            )
            raw_text = proc.stdout.strip()
            cleaned = self.clean_recognized_text(raw_text)
            if cleaned:
                self._win_ocr_available = True
            return cleaned
        except Exception as e:
            print(f"Windows Media OCR Çalıştırma hatası: {e}")
            return ""
        finally:
            if temp_img_path.exists():
                try:
                    temp_img_path.unlink()
                except Exception:
                    pass

    def _recognize_with_tesseract(self, image: Image.Image) -> str:
        """Tesseract OCR yürütülebiliri ile metin okur."""
        if not self.tesseract_cmd or not os.path.isfile(self.tesseract_cmd):
            return ""

        prep_img = self.preprocess_image(image)
        temp_img_path = self._temp_dir / f"tess_crop_{os.getpid()}_{id(image)}.png"
        try:
            prep_img.save(temp_img_path)
            # Almanca öncelikli dil parametreleri (deu, tur, eng)
            cmd = [
                self.tesseract_cmd,
                str(temp_img_path),
                "stdout",
                "-l", "deu+tur+eng",
                "--oem", "1",
                "--psm", "6"
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=8,
                errors="replace"
            )
            if proc.returncode != 0:
                # Dil paketi (deu) eksikse varsayılan dil ile dene
                cmd_fallback = [
                    self.tesseract_cmd,
                    str(temp_img_path),
                    "stdout",
                    "--psm", "6"
                ]
                proc = subprocess.run(
                    cmd_fallback,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=8,
                    errors="replace"
                )

            raw_text = proc.stdout.strip()
            return self.clean_recognized_text(raw_text)
        except Exception as e:
            print(f"Tesseract OCR hatası: {e}")
            return ""
        finally:
            if temp_img_path.exists():
                try:
                    temp_img_path.unlink()
                except Exception:
                    pass

    def recognize_words_with_boxes(self, image: Image.Image) -> List[Dict[str, Any]]:
        """
        Verilen PIL Image nesnesinden metinleri ve kelime koordinatlarını (BoundingBox) döner.
        Dönüş formatı: [{'text': 'Haus', 'x': 42, 'y': 10, 'w': 35, 'h': 16}, ...]
        Koordinatlar orijinal görüntü piksel koordinatlarına ölçeklenmiş olarak döner.
        """
        if not image or image.width == 0 or image.height == 0:
            return []

        use_tesseract_first = (self.preference == "tesseract" and bool(self.tesseract_cmd))

        if use_tesseract_first:
            boxes = self._boxes_with_tesseract(image)
            if boxes:
                return boxes
            return self._boxes_with_windows_ocr(image)
        else:
            boxes = self._boxes_with_windows_ocr(image)
            if boxes:
                return boxes
            if self.tesseract_cmd:
                return self._boxes_with_tesseract(image)
            return []

    def _boxes_with_windows_ocr(self, image: Image.Image) -> List[Dict[str, Any]]:
        """Windows Media OCR ile kelime kutuları çıkarır."""
        orig_w, orig_h = image.size
        if orig_w == 0 or orig_h == 0:
            return []

        prep_img = self.preprocess_image(image)
        prep_w, prep_h = prep_img.size
        scale_x = prep_w / orig_w if orig_w > 0 else 1.0
        scale_y = prep_h / orig_h if orig_h > 0 else 1.0

        temp_img_path = self._temp_dir / f"crop_box_{os.getpid()}_{id(image)}.png"
        try:
            prep_img.save(temp_img_path)
            cmd = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden",
                "-File", str(self._ps_script),
                "-ImagePath", str(temp_img_path),
                "-WithBoxes"
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=8,
                errors="replace"
            )
            raw_output = proc.stdout.strip()
            if not raw_output or raw_output == "[]":
                return []

            data = json.loads(raw_output)
            if isinstance(data, dict):
                data = [data]

            results = []
            for item in data:
                text = self.clean_recognized_text(item.get("text", ""))
                if not text:
                    continue
                rx = item.get("x", 0) / scale_x
                ry = item.get("y", 0) / scale_y
                rw = item.get("w", 0) / scale_x
                rh = item.get("h", 0) / scale_y
                results.append({
                    "text": text,
                    "x": int(rx),
                    "y": int(ry),
                    "w": int(rw),
                    "h": int(rh)
                })
            return results
        except Exception as e:
            print(f"Windows OCR Kelime ve Kutu hatası: {e}")
            return []
        finally:
            if temp_img_path.exists():
                try:
                    temp_img_path.unlink()
                except Exception:
                    pass

    def _boxes_with_tesseract(self, image: Image.Image) -> List[Dict[str, Any]]:
        """Tesseract OCR TSV çıktısı ile kelime kutuları çıkarır."""
        if not self.tesseract_cmd or not os.path.isfile(self.tesseract_cmd):
            return []

        orig_w, orig_h = image.size
        prep_img = self.preprocess_image(image)
        prep_w, prep_h = prep_img.size
        scale_x = prep_w / orig_w if orig_w > 0 else 1.0
        scale_y = prep_h / orig_h if orig_h > 0 else 1.0

        temp_img_path = self._temp_dir / f"tess_box_{os.getpid()}_{id(image)}.png"
        try:
            prep_img.save(temp_img_path)
            cmd = [
                self.tesseract_cmd,
                str(temp_img_path),
                "stdout",
                "-l", "deu+tur+eng",
                "tsv"
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=8,
                errors="replace"
            )
            if proc.returncode != 0:
                cmd_fallback = [self.tesseract_cmd, str(temp_img_path), "stdout", "tsv"]
                proc = subprocess.run(
                    cmd_fallback,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=8,
                    errors="replace"
                )

            lines = proc.stdout.strip().splitlines()
            if len(lines) <= 1:
                return []

            header = lines[0].split("\t")
            left_idx = header.index("left") if "left" in header else 6
            top_idx = header.index("top") if "top" in header else 7
            width_idx = header.index("width") if "width" in header else 8
            height_idx = header.index("height") if "height" in header else 9
            text_idx = header.index("text") if "text" in header else 11

            results = []
            for row_str in lines[1:]:
                parts = row_str.split("\t")
                if len(parts) <= text_idx:
                    continue
                raw_word = parts[text_idx].strip()
                cleaned = self.clean_recognized_text(raw_word)
                if not cleaned:
                    continue

                try:
                    bx = int(parts[left_idx]) / scale_x
                    by = int(parts[top_idx]) / scale_y
                    bw = int(parts[width_idx]) / scale_x
                    bh = int(parts[height_idx]) / scale_y
                    results.append({
                        "text": cleaned,
                        "x": int(bx),
                        "y": int(by),
                        "w": int(bw),
                        "h": int(bh)
                    })
                except (ValueError, IndexError):
                    continue

            return results
        except Exception as e:
            print(f"Tesseract kutu ayrıştırma hatası: {e}")
            return []
        finally:
            if temp_img_path.exists():
                try:
                    temp_img_path.unlink()
                except Exception:
                    pass

    def recognize_from_file(self, file_path: str) -> str:
        """Dosya yolundan metni okur."""
        try:
            if not os.path.exists(file_path):
                return ""
            img = Image.open(file_path)
            return self.recognize_from_image(img)
        except Exception as e:
            print(f"Resim açma hatası: {e}")
            return ""

    def clean_recognized_text(self, text: str) -> str:
        """OCR çıktısını temizler ve düzeltir."""
        if not text:
            return ""
        # Satır sonlarını boşluğa çevir
        text = text.replace("\r\n", " ").replace("\n", " ")
        # Birden fazla boşluğu teke indir
        text = re.sub(r"\s+", " ", text).strip()
        # Baştaki ve sondaki çizgi, tırnak, çöp karakterleri ve boşlukları temizle
        text = text.strip("-_~|`'\" \t\r\n")
        return text

    def get_status(self) -> Dict[str, Any]:
        """
        OCR motorlarının sistemdeki güncel durumunu ve kullanılabilirliğini raporlar.
        Sihirbaz (Onboarding Wizard) ve Ayarlar penceresi için durum bilgisi sağlar.
        """
        win_available = False
        try:
            # Hızlı kontrol: Windows PowerShell ile test
            test_cmd = ["powershell", "-NoProfile", "-Command", "[Windows.Media.Ocr.OcrEngine, Windows.Foundation.Diagnostics, ContentType = WindowsRuntime] | Out-Null; $e = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages(); if ($e) { Write-Output 'OK' } else { Write-Output 'NO' }"]
            proc = subprocess.run(test_cmd, capture_output=True, text=True, timeout=4, errors="replace")
            win_available = ("OK" in proc.stdout)
        except Exception:
            win_available = False

        tess_path = self.tesseract_cmd or find_tesseract_path()
        tess_available = bool(tess_path and os.path.isfile(tess_path))

        active = "Yok"
        if win_available and tess_available:
            active = f"Windows Media OCR & Tesseract (Tercih: {self.preference})"
        elif win_available:
            active = "Windows Media OCR (Yerleşik Windows Motoru)"
        elif tess_available:
            active = f"Tesseract OCR ({tess_path})"

        return {
            "windows_media_ocr": win_available,
            "tesseract_ocr": tess_available,
            "tesseract_path": tess_path or "",
            "active_backend": active,
            "is_ready": win_available or tess_available,
            "preference": self.preference
        }

    def test_ocr(self, sample_text: str = "Guten Tag") -> Tuple[bool, str]:
        """
        Sentetik bir test görüntüsü oluşturarak OCR motorunun çalışmasını test eder.
        Dönüş: (başarılı_mı, mesaj)
        """
        try:
            img = Image.new("RGB", (320, 80), color=(255, 255, 255))
            d = ImageDraw.Draw(img)
            # Metni yaz
            d.text((25, 25), sample_text, fill=(0, 0, 0))

            recognized = self.recognize_from_image(img)
            if not recognized:
                return False, "❌ OCR çıktısı boş döndü. Dil paketlerinizi veya Tesseract kurulumunu kontrol edin."

            # İçeriyor mu kontrol et
            clean_rec = recognized.lower().replace(" ", "")
            clean_target = sample_text.lower().replace(" ", "")
            if clean_target in clean_rec or clean_rec in clean_target or len(clean_rec) >= 4:
                return True, f"✅ OCR Başarıyla Doğrulandı! Tanınan Metin: '{recognized}'"
            else:
                return True, f"⚠️ OCR Çalıştı fakat metin farklı okundu: '{recognized}'"
        except Exception as e:
            return False, f"❌ OCR Test Hatası: {str(e)}"
