# SM-2 Adım 1 Doğrulama ve Düzeltme Raporu

**Zaman Damgası:** 2026-10-02 02:51:30 (UTC+3)

---

## 1. Bulgular

### a) `app/` Altında `status` Alanının Kullanımı
`app/` dizini altındaki tüm Python dosyalarında `status` alanının kullanımı araştırıldı:
- **`app/database.py`**:
  - `wordbook` tablosu şeması: `status TEXT DEFAULT 'learning'`
  - `add_word()`: varsayılan `status="learning"` argümanı
  - `seed_starter_words()`: başlangıç kelimelerine `status='learning'` ataması
  - `get_words(..., status_filter="")`: opsiyonel `WHERE status = ?` parametresi
  - `update_word_status(word_id, new_status)`: durum güncelleme metodu
  - `export_to_anki_csv()`: Anki dışa aktarımında 4. sütun olarak `w['status']`
- **`app/gui/hover_tooltip.py`**:
  - `_toggle_save()`: `db.add_word(..., status="learning")`
- **`app/gui/result_hud.py`**:
  - `_toggle_save_word()`: `db.add_word(..., status="learning")`
- **`app/gui/wordbook_window.py`**:
  - Treeview tablosunda `"status"` sütun başlığı ("Durum") ve satırda `w["status"]` gösterimi.

**Sonuç ve Karar:**
Uygulama kod tabanında `'learning'` veya `'learned'` gibi değerlere göre **dallanan (if/else branching)** veya arayüz filtrelemesi yapan hiçbir kod bulunmamaktadır. Dolayısıyla, `update_sm2_review()` içindeki `status = 'reviewed'` ataması herhangi bir mantıksal kırılmaya yol açmamaktadır. Kural gereğince mevcut hali (`status = 'reviewed'`) korunmuştur.

---

### b) `add_word()` Metodunun Tekrarlanan Kelimelerdeki Davranışı
- **Önceki Durum:**
  `add_word()` metodu aynı kelime (`LOWER(german)`) zaten veritabanında varsa `UPDATE wordbook SET ... status = ?` çalıştırıyor ve kelimenin `status` değerini zorla `'learning'`e sıfırlıyordu. Ayrıca SM-2 alanları henüz tabloda mevcut değildi.
- **Düzeltme & Yeni Davranış:**
  1. **Yeni Kelimeler:** Kelime ilk defa ekleniyorsa `next_review_date = datetime.now().strftime("%Y-%m-%d")` (yani bugün), `ease_factor = 2.5`, `interval_days = 0`, `repetitions = 0`, `last_reviewed_at = None` olarak eklenir.
  2. **Var Olan Kelimeler:** Aynı kelime tekrar eklendiğinde yalnızca anlam ve dilbilgisi bilgileri (`article`, `plural`, `turkish`, `part_of_speech`, `example_de`, `example_tr`, `notes`) güncellenir. SM-2 alanları (`ease_factor`, `interval_days`, `repetitions`, `last_reviewed_at`, `next_review_date`) ve `status` değerine **asla dokunulmaz, öğrenme ilerlemesi korunur**.

---

## 2. Yapılan Değişiklikler

1. **`app/database.py`**:
   - `wordbook` tablosuna `ease_factor REAL DEFAULT 2.5`, `interval_days INTEGER DEFAULT 0`, `repetitions INTEGER DEFAULT 0`, `last_reviewed_at TIMESTAMP DEFAULT NULL`, `next_review_date TEXT DEFAULT NULL` eklendi.
   - Mevcut veritabanı dosyaları için `_init_db()` içine `PRAGMA table_info` ile geriye dönük otomatik sütun göçü (migration) eklendi.
   - `add_word()` metodu SM-2 alanlarını kabul edecek, yeni kelimelere `next_review_date = bugün` atayacak ve tekrarlanan eklemelerde SM-2 verisini koruyacak şekilde güncellendi.
   - `update_sm2_review(word_id, quality, review_date=None)` metodu eklendi:
     - `quality < 3` ise `repetitions = 0`, `interval = 1`, `ease_factor` değişmez.
     - `quality >= 3` ise `repetitions += 1`, aralık formüle göre büyütülür (1 -> 6 -> interval * EF), EF formüle göre güncellenir (min 1.3).
     - `status = 'reviewed'` atanır.
   - `get_word_by_id(word_id)` ve `get_due_words(target_date=None)` sorgu metotları eklendi.
2. **`tests/test_sm2.py`**:
   - İstenen tüm testler eklendi ve tamamı doğrulandı:
     - `test_quality_3_ease_factor_reduction`: quality=3 iken EF 2.5 → 2.36 doğrulaması.
     - `test_quality_1_resets_repetitions_interval_ease_unchanged`: repetitions=3 iken quality=1 verilince repetitions=0, interval=1, EF değişmez doğrulaması.
     - `test_add_word_assigns_today_as_next_review_date`: add_word yeni kelimeye next_review_date = bugün atar doğrulaması.
     - `test_same_word_readded_preserves_sm2_fields`: Aynı kelime tekrar eklenince SM-2 alanlarının sıfırlanmadığı doğrulaması.
     - `test_sm2_minimum_ease_factor_boundary`: EF alt sınır 1.3 testi.
     - `test_get_due_words`: Vadesi gelen kelimeleri filtreleme testi.
     - `test_update_sm2_review_sets_status_reviewed`: Durumun 'reviewed' yapılması testi.

---

## 3. Gerçek Test Çıktısı

### `python -m unittest discover -s tests -v`
```text
test_compound_noun_article_inheritance (test_bug_fixes.TestBugFixesAndNewFeatures.test_compound_noun_article_inheritance) ... ok
test_conjunction_vs_adverb_disambiguation (test_bug_fixes.TestBugFixesAndNewFeatures.test_conjunction_vs_adverb_disambiguation) ... ok
test_database_delete_by_german (test_bug_fixes.TestBugFixesAndNewFeatures.test_database_delete_by_german) ... ok
test_empty_string_safety (test_bug_fixes.TestBugFixesAndNewFeatures.test_empty_string_safety) ... ok
test_extract_base_word_indefinite_articles (test_bug_fixes.TestBugFixesAndNewFeatures.test_extract_base_word_indefinite_articles) ... ok
test_modal_verbs_ihr_conjugation (test_bug_fixes.TestBugFixesAndNewFeatures.test_modal_verbs_ihr_conjugation) ... ok
test_plural_offline_lookup (test_bug_fixes.TestBugFixesAndNewFeatures.test_plural_offline_lookup) ... ok
test_punctuation_stripping (test_bug_fixes.TestBugFixesAndNewFeatures.test_punctuation_stripping) ... ok
test_separable_verb_false_positives_eliminated (test_bug_fixes.TestBugFixesAndNewFeatures.test_separable_verb_false_positives_eliminated) ... ok
test_separable_verb_true_positive (test_bug_fixes.TestBugFixesAndNewFeatures.test_separable_verb_true_positive) ... ok
test_anki_export (test_database.TestDatabase.test_anki_export) ... ok
test_cache_set_and_get (test_database.TestDatabase.test_cache_set_and_get) ... ok
test_wordbook_crud (test_database.TestDatabase.test_wordbook_crud) ... ok
test_clipboard_filter_edge_cases (test_edge_cases.TestEdgeCases.test_clipboard_filter_edge_cases) ... ok
test_extreme_sentence_grammar_edge_cases (test_edge_cases.TestEdgeCases.test_extreme_sentence_grammar_edge_cases) ... ok
test_german_umlauts_and_sz (test_edge_cases.TestEdgeCases.test_german_umlauts_and_sz) ... ok
test_sql_injection_defense (test_edge_cases.TestEdgeCases.test_sql_injection_defense) ... ok
test_weird_punctuation (test_edge_cases.TestEdgeCases.test_weird_punctuation) ... ok
test_configuration (test_gemini_service.TestGeminiService.test_configuration) ... ok
test_empty_key_connection_test (test_gemini_service.TestGeminiService.test_empty_key_connection_test) ... ok
test_invalid_key_connection (test_gemini_service.TestGeminiService.test_invalid_key_connection) ... ok
test_model_selection (test_gemini_service.TestGeminiService.test_model_selection) ... ok
test_network_error (test_gemini_service.TestGeminiService.test_network_error) ... ok
test_successful_connection (test_gemini_service.TestGeminiService.test_successful_connection) ... ok
test_translate_and_analyze_success (test_gemini_service.TestGeminiService.test_translate_and_analyze_success) ... ok
test_translate_and_analyze_unconfigured (test_gemini_service.TestGeminiService.test_translate_and_analyze_unconfigured) ... ok
test_analyze_sentence_grammar (test_german_analyzer.TestGermanAnalyzer.test_analyze_sentence_grammar) ... ok
test_clean_text (test_german_analyzer.TestGermanAnalyzer.test_clean_text) ... ok
test_extract_base_word (test_german_analyzer.TestGermanAnalyzer.test_extract_base_word) ... ok
test_is_single_word (test_german_analyzer.TestGermanAnalyzer.test_is_single_word) ... ok
test_offline_analysis (test_german_analyzer.TestGermanAnalyzer.test_offline_analysis) ... ok
test_offline_reverse_analysis (test_german_analyzer.TestGermanAnalyzer.test_offline_reverse_analysis) ... ok
test_predict_gender_by_rules (test_german_analyzer.TestGermanAnalyzer.test_predict_gender_by_rules) ... ok
test_default_config_hotkeys (test_hotkey_manager.TestConfigAndSettingsIntegration.test_default_config_hotkeys) ... ok
test_load_config_supplies_default_hotkeys (test_hotkey_manager.TestConfigAndSettingsIntegration.test_load_config_supplies_default_hotkeys) ... ok
test_settings_window_hotkey_editing (test_hotkey_manager.TestConfigAndSettingsIntegration.test_settings_window_hotkey_editing) ... ok
test_settings_window_invalid_hotkey_validation (test_hotkey_manager.TestConfigAndSettingsIntegration.test_settings_window_invalid_hotkey_validation) ... ok
test_legacy_register_backward_compatibility (test_hotkey_manager.TestHotkeyManagerLogic.test_legacy_register_backward_compatibility) ... ok
test_modifier_isolation_alt_tab_safety (test_hotkey_manager.TestHotkeyManagerLogic.test_modifier_isolation_alt_tab_safety) ... ok
test_multiple_registered_hotkeys (test_hotkey_manager.TestHotkeyManagerLogic.test_multiple_registered_hotkeys) ... ok
test_normal_typing_not_swallowed (test_hotkey_manager.TestHotkeyManagerLogic.test_normal_typing_not_swallowed) ... ok
test_space_then_tab_order_independence (test_hotkey_manager.TestHotkeyManagerLogic.test_space_then_tab_order_independence) ... ok
test_tab_space_trigger_sequence (test_hotkey_manager.TestHotkeyManagerLogic.test_tab_space_trigger_sequence) ... ok
test_unregister_and_clear (test_hotkey_manager.TestHotkeyManagerLogic.test_unregister_and_clear) ... ok
test_format_hotkey (test_hotkey_parser_and_validation.TestHotkeyParserAndValidation.test_format_hotkey) ... ok
test_parse_alt_x_and_alt_h (test_hotkey_manager.TestHotkeyParserAndValidation.test_parse_alt_x_and_alt_h) ... ok
test_parse_ctrl_combinations (test_hotkey_manager.TestHotkeyParserAndValidation.test_parse_ctrl_combinations) ... ok
test_parse_empty_or_invalid_raises_error (test_hotkey_manager.TestHotkeyParserAndValidation.test_parse_empty_or_invalid_raises_error) ... ok
test_parse_function_keys (test_hotkey_manager.TestHotkeyParserAndValidation.test_parse_function_keys) ... ok
test_parse_tab_space (test_hotkey_manager.TestHotkeyParserAndValidation.test_parse_tab_space) ... ok
test_parse_three_key_combination (test_hotkey_manager.TestHotkeyParserAndValidation.test_parse_three_key_combination) ... ok
test_parse_turkish_aliases (test_hotkey_manager.TestHotkeyParserAndValidation.test_parse_turkish_aliases) ... ok
test_parse_with_whitespace_and_case (test_hotkey_manager.TestHotkeyParserAndValidation.test_parse_with_whitespace_and_case) ... ok
test_validate_hotkey_string (test_hotkey_manager.TestHotkeyParserAndValidation.test_validate_hotkey_string) ... ok
test_main_overlay_initializes_hotkeys_and_snip_label (test_hotkey_manager.TestMainOverlayHotkeyIntegration.test_main_overlay_initializes_hotkeys_and_snip_label) ... ok
test_trigger_ocr_hotkey_unminimizes_and_opens_snipper (test_hotkey_manager.TestMainOverlayHotkeyIntegration.test_trigger_ocr_hotkey_unminimizes_and_opens_snipper) ... ok
test_config_hover_defaults (test_hover_feature.TestHoverFeature.test_config_hover_defaults) ... ok
test_hover_tooltip_lifecycle (test_hover_feature.TestHoverFeature.test_hover_tooltip_lifecycle) ... ok
test_hover_tooltip_loading_and_message (test_hover_feature.TestHoverFeature.test_hover_tooltip_loading_and_message) ... ok
test_hover_tracker_init_and_toggle (test_hover_feature.TestHoverFeature.test_hover_tracker_init_and_toggle) ... ok
test_hover_tracker_trigger_conditions (test_hover_feature.TestHoverFeature.test_hover_tracker_trigger_conditions) ... ok
test_hover_tracker_unconditional_xbutton (test_hover_feature.TestHoverFeature.test_hover_tracker_unconditional_xbutton) ... ok
test_hover_tracker_xbutton_hook_callback (test_hover_feature.TestHoverFeature.test_hover_tracker_xbutton_hook_callback) ... ok
test_main_overlay_hover_integration (test_hover_feature.TestHoverFeature.test_main_overlay_hover_integration) ... ok
test_ocr_recognize_words_with_boxes (test_hover_feature.TestHoverFeature.test_ocr_recognize_words_with_boxes) ... ok
test_config_sound_enabled_removed (test_no_tts.TestTTSFeatureRemoval.test_config_sound_enabled_removed) ... ok
test_german_tts_engine_is_noop (test_no_tts.TestTTSFeatureRemoval.test_german_tts_engine_is_noop) ... ok
test_load_config_sanitizes_sound_enabled (test_no_tts.TestTTSFeatureRemoval.test_load_config_sanitizes_sound_enabled) ... ok
test_main_overlay_without_tts (test_no_tts.TestTTSFeatureRemoval.test_main_overlay_without_tts) ... ok
test_result_hud_no_sound_button (test_no_tts.TestTTSFeatureRemoval.test_result_hud_no_sound_button) ... ok
test_result_hud_signature_backward_compatibility (test_no_tts.TestTTSFeatureRemoval.test_result_hud_signature_backward_compatibility) ... ok
test_result_hud_update_data_no_audio (test_no_tts.TestTTSFeatureRemoval.test_result_hud_update_data_no_audio) ... ok
test_result_hud_without_db_safe (test_no_tts.TestTTSFeatureRemoval.test_result_hud_without_db_safe) ... ok
test_settings_window_no_sound_option (test_no_tts.TestTTSFeatureRemoval.test_settings_window_no_sound_option) ... ok
test_wordbook_flashcard_no_sound_button (test_no_tts.TestTTSFeatureRemoval.test_wordbook_flashcard_no_sound_button) ... ok
test_image_preprocessing (test_ocr_engine.TestOCREngine.test_image_preprocessing) ... ok
test_synthetic_image_recognition (test_ocr_engine.TestOCREngine.test_synthetic_image_recognition) ... ok
test_text_cleaning (test_ocr_engine.TestOCREngine.test_text_cleaning) ... ok
test_add_word_assigns_today_as_next_review_date (test_sm2.TestSM2SpacedRepetition.test_add_word_assigns_today_as_next_review_date) ... ok
test_get_due_words (test_sm2.TestSM2SpacedRepetition.test_get_due_words) ... ok
test_quality_1_resets_repetitions_interval_ease_unchanged (test_sm2.TestSM2SpacedRepetition.test_quality_1_resets_repetitions_interval_ease_unchanged) ... ok
test_quality_3_ease_factor_reduction (test_sm2.TestSM2SpacedRepetition.test_quality_3_ease_factor_reduction) ... ok
test_same_word_readded_preserves_sm2_fields (test_sm2.TestSM2SpacedRepetition.test_same_word_readded_preserves_sm2_fields) ... ok
test_sm2_minimum_ease_factor_boundary (test_sm2.TestSM2SpacedRepetition.test_sm2_minimum_ease_factor_boundary) ... ok
test_update_sm2_review_sets_status_reviewed (test_sm2.TestSM2SpacedRepetition.test_update_sm2_review_sets_status_reviewed) ... ok
test_hover_tooltip_timer_cancel_safety (test_stability_and_onboarding.TestGUIStabilityAndOnboarding.test_hover_tooltip_timer_cancel_safety) ... ok
test_hover_tooltip_toggle_save_without_crash (test_stability_and_onboarding.TestGUIStabilityAndOnboarding.test_hover_tooltip_toggle_save_without_crash) ... ok
test_main_overlay_corrupt_hotkey_resilience (test_stability_and_onboarding.TestGUIStabilityAndOnboarding.test_main_overlay_corrupt_hotkey_resilience) ... ok
test_onboarding_wizard_step_flow_and_completion (test_stability_and_onboarding.TestGUIStabilityAndOnboarding.test_onboarding_wizard_step_flow_and_completion) ... ok
test_onboarding_wizard_wm_delete_window (test_stability_and_onboarding.TestGUIStabilityAndOnboarding.test_onboarding_wizard_wm_delete_window) ... ok
test_result_hud_render_note_missing_text_key (test_stability_and_onboarding.TestGUIStabilityAndOnboarding.test_result_hud_render_note_missing_text_key) ... ok
test_result_hud_renders_error_cleanly (test_stability_and_onboarding.TestGUIStabilityAndOnboarding.test_result_hud_renders_error_cleanly) ... ok
test_wordbook_empty_flashcard_state (test_stability_and_onboarding.TestGUIStabilityAndOnboarding.test_wordbook_empty_flashcard_state) ... ok
test_capture_screen_rect_gdi_handles_and_coords (test_stability_and_onboarding.TestStabilityAndDegradation.test_capture_screen_rect_gdi_handles_and_coords) ... ok
test_config_first_run_defaults (test_stability_and_onboarding.TestStabilityAndDegradation.test_config_first_run_defaults) ... ok
test_database_add_word_empty_string_rejected (test_stability_and_onboarding.TestStabilityAndDegradation.test_database_add_word_empty_string_rejected) ... ok
test_database_add_word_resilient_to_extra_kwargs (test_stability_and_onboarding.TestStabilityAndDegradation.test_database_add_word_resilient_to_extra_kwargs) ... ok
test_database_seed_starter_words (test_stability_and_onboarding.TestStabilityAndDegradation.test_database_seed_starter_words) ... ok
test_find_tesseract_path (test_stability_and_onboarding.TestStabilityAndDegradation.test_find_tesseract_path) ... ok
test_gemini_format_grammar_notes_dual_keys (test_stability_and_onboarding.TestStabilityAndDegradation.test_gemini_format_grammar_notes_dual_keys) ... ok
test_gemini_test_connection_empty_key (test_stability_and_onboarding.TestStabilityAndDegradation.test_gemini_test_connection_empty_key) ... ok
test_ocr_engine_empty_or_zero_size_images (test_stability_and_onboarding.TestStabilityAndDegradation.test_ocr_engine_empty_or_zero_size_images) ... ok
test_ocr_engine_status_and_test (test_stability_and_onboarding.TestStabilityAndDegradation.test_ocr_engine_status_and_test) ... ok
test_translate_sentence_offline_graceful (test_stability_and_onboarding.TestStabilityAndDegradation.test_translate_sentence_offline_graceful) ... ok
test_empty_input (test_translator.TestTranslator.test_empty_input) ... ok
test_translate_direct_gemini_fallback (test_translator.TestTranslator.test_translate_direct_gemini_fallback) ... ok
test_translate_direct_gemini_mode (test_translator.TestTranslator.test_translate_direct_gemini_mode) ... ok
test_translate_german_sentence_to_turkish (test_translator.TestTranslator.test_translate_german_sentence_to_turkish) ... ok
test_translate_german_verb (test_translator.TestTranslator.test_translate_german_verb) ... ok
test_translate_offline_word (test_translator.TestTranslator.test_translate_offline_word) ... ok
test_translate_online_word_with_caching (test_translator.TestTranslator.test_translate_online_word_with_caching) ... ok
test_translate_sentence (test_translator.TestTranslator.test_translate_sentence) ... ok
test_audio_download_disabled (test_tts_engine.TestTTSEngine.test_audio_download_disabled) ... ok
test_play_non_blocking_noop (test_tts_engine.TestTTSEngine.test_play_non_blocking_noop) ... ok

----------------------------------------------------------------------
Ran 114 tests in 10.012s

OK
```

### Pytest Durumu
`python -m pytest` çalıştırıldığında:
`No module named pytest` (Ortamda pytest kurulu değil, standart `unittest` paketi kullanıldı).

---

## 4. Başarısız Testler
**Yok.** 114 testin tamamı başarılı oldu.

---

## 5. Yarım Kalan İşler
**Yok.** SM-2 Adım 1 gereksinimlerinin tamamı (veritabanı alanları, göç desteği, add_word koruması, update_sm2_review formülleri ve test paketi) eksiksiz uygulandı ve doğrulandı.

---

## 6. Git Bilgisi

### Commit Hash
`8956bda` (`8956bda feat(sm2): SM-2 Adim 1 dogrulama, aralikli tekrar algoritmasi ve testleri`)

### `git status`
```text
On branch main
Your branch is ahead of 'origin/main' by 1 commit.
  (use "git push" to publish your local commits)

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	EkranSozlugu-GitHub.zip
	FEEDBACK.md.gdoc
	MIMARI_VE_GELISDIRME_PLANI.md
	SPRINT_LOG.md.gdoc
	github_repo/
	run.bat

nothing added to commit but untracked files present (use "git add" to track)
```

### `git log -3 --oneline`
```text
8956bda feat(sm2): SM-2 Adim 1 dogrulama, aralikli tekrar algoritmasi ve testleri
25df992 feat: stabilite iyilestirmeleri, sifir kurulum sihirbazi, baslat.bat venv destegi ve docs guncellemesi
737f521 docs: guncel repo linki, dogal aciklamalar ve onizleme gorseli eklendi
```
