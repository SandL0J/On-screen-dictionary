"""
Kelime Defteri Kaydetme / Favori Yardımcısı (Wordbook Save Helper)
HUD (ResultHUD) ve Fare Üzerine Gelme (HoverTooltip) bileşenlerinin
kelime defterine ekleme/çıkarma (toggle) işlemlerini merkezileştirir (DRY prensibi).
"""

from typing import Dict, Any, Tuple, Optional


def toggle_save_word_from_result(
    db: Any,
    data: Optional[Dict[str, Any]],
    source_label: str = "Kelime",
    always_include_label: bool = False
) -> Tuple[bool, str]:
    """
    Verilen çeviri/kelime verisini kelime defterine ekler veya zaten kayıtlıysa çıkarır (toggle).

    Args:
        db: Database örneği
        data: Çeviri/analiz sonuç sözlüğü (HUD veya HoverTooltip verisi)
        source_label: Notlarda kullanılacak kaynak etiketi ("Kelime", "Hover OCR" vb.)
        always_include_label: True ise etiket her zaman eklenir (örn: 'Hover OCR'),
                              False ise yalnızca surface != lemma durumunda eklenir.

    Returns:
        (is_saved: bool, saved_word: str)
        - is_saved: True ise kelime yeni eklendi, False ise kelime silindi veya işlem yapılamadı.
        - saved_word: İşlem yapılan Almanca kelime / deyim metni.
    """
    if not db or not data or not isinstance(data, dict):
        return False, ""

    colloc = data.get("collocation")
    if colloc and colloc.get("phrase"):
        german = colloc["phrase"].strip()
        turkish = (colloc.get("meaning_tr") or data.get("turkish", "")).strip()
        pos = "Kalıp / Deyim"
    else:
        german = (
            data.get("lemma") or
            data.get("german") or
            data.get("original") or
            data.get("text") or ""
        ).strip()
        turkish = (
            data.get("turkish") or
            data.get("translation") or ""
        ).strip()
        pos = data.get("pos", "").strip()

    if not german:
        return False, ""

    analysis = data.get("analysis", {}) if isinstance(data.get("analysis"), dict) else {}
    article = (data.get("article") or analysis.get("article") or "").strip()
    plural = (data.get("plural") or analysis.get("plural") or "").strip()
    ex_de = (data.get("context_sentence") or data.get("example_de") or "").strip()
    ex_tr = (data.get("example_tr") or "").strip()
    surface = (data.get("surface_form") or "").strip()

    extra_kwargs = {}
    if surface:
        extra_kwargs["surface_form"] = surface

    # Toggle işlemi: Eğer zaten kayıtlıysa sil
    if db.is_word_saved(german):
        db.delete_word_by_german(german)
        return False, german

    # Kayıtlı değilse: Fiil triad bilgisi ve notları hazırla, ardından ekle
    verb_info = data.get("verb_info")
    triad_note = ""
    if verb_info and isinstance(verb_info, dict):
        triad_note = verb_info.get("triad") or f"Mastar: {verb_info.get('infinitive', '')} • Prät: {verb_info.get('praeteritum', '')} • Perf: {verb_info.get('perfekt', '')}"

    note_parts = []
    if always_include_label:
        if surface and surface.lower() != german.lower():
            note_parts.append(f"{source_label} ({surface})")
        else:
            note_parts.append(source_label)
    else:
        if surface and surface.lower() != german.lower():
            note_parts.append(f"{source_label} ({surface})")

    if triad_note:
        note_parts.append(triad_note)

    note_text = " | ".join(note_parts)

    db.add_word(
        german=german,
        turkish=turkish,
        article=article,
        plural=plural,
        part_of_speech=pos,
        example_de=ex_de,
        example_tr=ex_tr,
        notes=note_text,
        status="learning",
        **extra_kwargs
    )
    return True, german
