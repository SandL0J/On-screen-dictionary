"""
Optik Karakter Tanıma (OCR) Motoru
Ekrandan seçilen bölgedeki veya bir resimdeki Almanca metinleri Windows Media OCR ile okur.
Görüntü ön işleme (Image Preprocessing - ölçekleme, kontrast, netleştirme) uygulayarak
video altyazılarındaki ve ekran metinlerindeki tanıma doğruluğunu maksimuma çıkarır.
"""
import os
import re
import json
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


class OCREngine:
    def __init__(self):
        self._temp_dir = Path(tempfile.gettempdir()) / "ekran_sozlugu_ocr"
        self._temp_dir.mkdir(exist_ok=True)
        self._ps_script = self._create_ocr_ps_script()

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

$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
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
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)
        return script_path

    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        OCR doğruluğunu artırmak için görüntüyü iyileştirir:
        1. 2.5x büyütme (Lanczos)
        2. Gri tonlama ve kontrast artırma
        3. Kenar netleştirme
        """
        # Büyüt
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
        """Verilen PIL Image nesnesinden metni okur."""
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
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=8)
            raw_text = proc.stdout.strip()
            return self.clean_recognized_text(raw_text)
        except Exception as e:
            print(f"OCR Çalıştırma hatası: {e}")
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
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=8)
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
            print(f"OCR Kelime ve Kutu hatası: {e}")
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
