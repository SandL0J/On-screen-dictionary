"""
Fare Yan Tuşları (Mouse 4/5) ve İmleç OCR Test Aracı
Bu betik, farenizin yan tuşlarının Windows tarafından nasıl algılandığını
ve imlecinizin altındaki kelimenin başarıyla okunup okunmadığını test eder.
"""
import time
import ctypes
from ctypes import wintypes
from app.hover_tracker import is_key_down, get_current_cursor_pos, capture_screen_rect_gdi, VK_XBUTTON1, VK_XBUTTON2, VK_MBUTTON
from app.ocr_engine import OCREngine

print("=" * 60)
print("  EKRAN SOZLUGU - FARE VE OCR TEST ARACI")
print("=" * 60)
print("Lutfen farenizi bir Almanca kelimenin uzerine getirin")
print("ve farenizin YAN TUSUNA (Mouse 4 veya Mouse 5) veya ORTA TUSUNA basin.")
print("(Cikmak icin Ctrl+C yapabilirsiniz)")
print("=" * 60)

ocr = OCREngine()
last_x1 = False
last_x2 = False
last_mb = False

try:
    while True:
        time.sleep(0.02)
        x1 = is_key_down(VK_XBUTTON1)
        x2 = is_key_down(VK_XBUTTON2)
        mb = is_key_down(VK_MBUTTON)

        btn_pressed = None
        if x1 and not last_x1:
            btn_pressed = "Fare Yan Tus 1 (Mouse 4 / XBUTTON1 / Geri)"
        elif x2 and not last_x2:
            btn_pressed = "Fare Yan Tus 2 (Mouse 5 / XBUTTON2 / Ileri)"
        elif mb and not last_mb:
            btn_pressed = "Fare Orta Tus (Mouse 3 / Tekerlek Tiklamasi)"

        last_x1 = x1
        last_x2 = x2
        last_mb = mb

        if btn_pressed:
            cx, cy = get_current_cursor_pos()
            print(f"\n[BASILDI] -> {btn_pressed}")
            print(f" • Fare Koordinati: X={cx}, Y={cy}")
            print(" • Ekran bolgesi kirpiliyor ve Windows OCR ile okunuyor...")

            img = capture_screen_rect_gdi(cx - 220, cy - 60, 440, 120)
            if not img:
                print(" [HATA] Ekran yakalanamadi!")
                continue

            t0 = time.time()
            boxes = ocr.recognize_words_with_boxes(img)
            t1 = time.time()
            print(f" • OCR Tamamlandi ({t1 - t0:.2f} saniye). Tespit edilen kelimeler: {len(boxes)}")

            for b in boxes:
                print(f"    - '{b['text']}' (x={b['x']}, y={b['y']}, w={b['w']}, h={b['h']})")

            if not boxes:
                print(" • UYARI: Fare etrafinda hic metin tespit edilemedi. Lutfen bir kelimenin tam uzerinde deneyin.")
            else:
                print(" • TEBRIKLER! Farenizin tusu ve ekran okuma 100% calisiyor.")

except KeyboardInterrupt:
    print("\nTest sonlandirildi.")
