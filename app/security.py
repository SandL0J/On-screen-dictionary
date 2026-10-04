"""
Güvenlik ve Kriptografik Depolama Modülü (Security & DPAPI)
Hassas kullanıcı verilerini (Gemini API anahtarı vb.) Windows Data Protection API (DPAPI)
ile yerel Windows kullanıcı hesabına bağlı olarak şifreler ve çözer.
"""
import base64
import ctypes
from ctypes import wintypes
import os
import re
import sys
from typing import Optional, Tuple

DPAPI_PREFIX = "dpapi:"
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte))
        ]

    # Arka plan servislerinde veya GUI'sız durumlarda Windows'un UI dialog çıkarmasını engeller
    CRYPTPROTECT_UI_FORBIDDEN = 0x1


def protect_data(data: bytes, description: str = "EkranSozluguApiKey") -> bytes:
    """
    Verilen bayt dizisini Windows DPAPI (CryptProtectData) ile şifreler.
    Şifrelenen veri yalnızca bu Windows kullanıcısı tarafından çözülebilir.
    """
    if not IS_WINDOWS:
        raise OSError("Windows DPAPI yalnızca Windows işletim sisteminde desteklenir.")
    if not data:
        return b""

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_buf = ctypes.create_string_buffer(data)
    in_blob = DATA_BLOB(len(data), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()

    # CryptProtectData(pDataIn, szDataDescr, pOptionalEntropy, pvReserved, pPromptStruct, dwFlags, pDataOut)
    success = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        description,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob)
    )
    if not success:
        raise ctypes.WinError()

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)


def unprotect_data(cipher_bytes: bytes) -> bytes:
    """
    Windows DPAPI (CryptUnprotectData) ile şifrelenmiş bayt dizisini çözer.
    """
    if not IS_WINDOWS:
        raise OSError("Windows DPAPI yalnızca Windows işletim sisteminde desteklenir.")
    if not cipher_bytes:
        return b""

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    in_buf = ctypes.create_string_buffer(cipher_bytes)
    in_blob = DATA_BLOB(len(cipher_bytes), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_byte)))
    out_blob = DATA_BLOB()

    # CryptUnprotectData(pDataIn, ppszDataDescr, pOptionalEntropy, pvReserved, pPromptStruct, dwFlags, pDataOut)
    success = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob)
    )
    if not success:
        raise ctypes.WinError()

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        if out_blob.pbData:
            kernel32.LocalFree(out_blob.pbData)


def is_dpapi_protected(value: Optional[str]) -> bool:
    """Verilen dizgenin DPAPI ile şifrelenmiş formatta olup olmadığını döner."""
    return isinstance(value, str) and value.startswith(DPAPI_PREFIX) and len(value) > len(DPAPI_PREFIX)


def protect_key(plain_key: str) -> str:
    """
    Düz metin API anahtarını Windows DPAPI ile şifreler ve 'dpapi:<base64>' olarak döner.
    Boş değerler boş olarak döner. Zaten şifreli değerler yeniden şifrelenmez.
    """
    if not plain_key:
        return ""
    if is_dpapi_protected(plain_key):
        return plain_key

    raw_bytes = plain_key.encode("utf-8")
    encrypted_bytes = protect_data(raw_bytes)
    b64_str = base64.b64encode(encrypted_bytes).decode("ascii")
    return f"{DPAPI_PREFIX}{b64_str}"


def unprotect_key(protected_val: str) -> str:
    """
    'dpapi:<base64>' formatındaki şifreli anahtarı çözüp düz metin olarak döner.
    Şifreli formatta değilse (eski düz metin config) değeri olduğu gibi döner.
    """
    if not protected_val:
        return ""
    if not is_dpapi_protected(protected_val):
        return protected_val

    b64_payload = protected_val[len(DPAPI_PREFIX):]
    try:
        cipher_bytes = base64.b64decode(b64_payload.encode("ascii"))
    except Exception as e:
        raise ValueError(f"Geçersiz Base64 formatı: {e}") from e

    plain_bytes = unprotect_data(cipher_bytes)
    return plain_bytes.decode("utf-8")


def mask_api_key(key: Optional[str]) -> str:
    """
    Log ve hata çıktılarında hassas anahtarı maskeler.
    Gerçek anahtar karakterleri asla açığa çıkmaz.
    """
    if not key:
        return "[BOŞ]"
    if is_dpapi_protected(key):
        return "[DPAPI İLE KORUNUYOR]"
    if len(key) <= 8:
        return "[GİZLENDİ]"
    return f"{key[:4]}...{key[-4:]}"


# --- Hassas Pano ve Veri Filtresi (Sensitive Clipboard Filter) ---
_RE_AIZA_KEY = re.compile(r"\bAIza[0-9A-Za-z-_]{30,}\b")
_RE_SK_KEY = re.compile(r"\bsk-[A-Za-z0-9-_]{20,}\b")
_RE_GH_TOKEN = re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b")
_RE_AWS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_RE_SLACK_TOKEN = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")
_RE_JWT = re.compile(r"\bey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
_RE_PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")
_RE_UUID = re.compile(r"\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b")
_RE_CREDIT_CARD_BLOCKS = re.compile(r"\b(?:\d{4}[ -]){3}\d{4}\b")
_RE_CARD_LABEL = re.compile(
    r"(?i)\b(?:karten(?:nummer)?|card|credit\s*card|kredi\s*kart[ıi]|pan)\s*[:#]?\s*([0-9\s-]{13,23})"
)
_RE_IBAN_SEARCH = re.compile(
    r"(?i)\b(?:[a-z]{2}[0-9]{2}(?:[ \t-]+[0-9a-z]{2,4}){3,8}|[a-z]{2}[0-9]{2}[0-9a-z]{11,30})\b"
)
_RE_LABELED_SECRET = re.compile(
    r"\b(?:passwort|password|kennwort|parola|şifre|sifre|passcode|secret|api[_-]?key|access[_-]?token)\s*[:=\-]\s*(\S+)|\bbearer\s+([A-Za-z0-9_\-\.]{8,})|\bbearer\s*[:=\-]\s*(\S+)",
    flags=re.IGNORECASE
)
_RE_GERMAN_HYPHEN_WORD = re.compile(r"^[A-Za-zÄÖÜäöüß]+(?:-[A-Za-zÄÖÜäöüß]+)+$")


def luhn_checksum(candidate: str) -> bool:
    """
    Kredi kartı numarası için standart Luhn (Mod 10) algoritması doğrulaması yapar.
    13 ile 19 basamak arasındaki sayıları destekler.
    """
    digits = [int(c) for c in candidate if c.isdigit()]
    if not (13 <= len(digits) <= 19):
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _is_password_token(token: str) -> bool:
    """
    Tekil bir belirtecin (token) karmaşık parola veya rastgele şifre olup olmadığını kontrol eder.
    Almanca/İngilizce birleşik tireli isimleri (Baden-Württemberg, 40-Stunden-Woche, COVID-19 vb.)
    ve kesme işaretli doğal kelimeleri (bringt's, couldn't vb.) korur.
    Cümle içine gömülü 40+ karakterlik uzun belirteçleri ve kriptografik özetleri de güvenle algılar.
    """
    s = token.strip(" ,;:.()[]{}'\"")
    if len(s) < 8:
        return False

    # Doğal kesme işaretli kelimeler (bringt's, couldn't, l'apprentissage vb.)
    if re.match(r"^[A-Za-zÄÖÜäöüß]+(?:\'[A-Za-zÄÖÜäöüß]+)+$", s):
        return False

    # Doğal tireli birleşik kelimeler (Baden-Württemberg, 40-Stunden-Woche, COVID-19, Boeing-747 vb.)
    # Her bir parça ya tamamen harf ya da tamamen rakam olmalıdır (lisans anahtarları gibi karma parçalar hariç)
    parts = s.split("-")
    if len(parts) > 1 and all(p.isalpha() or p.isdigit() for p in parts) and any(p.isalpha() for p in parts):
        return False

    has_lower = bool(re.search(r"[a-zäöüß]", s))
    has_upper = bool(re.search(r"[A-ZÄÖÜ]", s))
    has_digit = bool(re.search(r"[0-9]", s))
    # Güçlü parola sembolleri (kesme işareti, tire, nokta doğal dilde sıkça yer aldığından hariç tutulur)
    has_strong_symbol = bool(re.search(r"[!@#$%^&*()_+={}\[\]|:;\"<>,?/~`\\]", s))

    # a) Güçlü Sembol + Rakam + Harf (standart karmaşık parola veya rastgele anahtar)
    if has_strong_symbol and has_digit and (has_lower or has_upper) and len(s) >= 8:
        return True

    # b) Harf (büyük+küçük) + Güçlü Sembol (rakamsız karmaşık parola, örn: P@ssword!, Geheim#Wort)
    if has_strong_symbol and has_lower and has_upper and len(s) >= 8:
        return True

    # c) Base64 veya yüksek yoğunluklu rastgele belirteç (örn: xK9mQ2vL8pT5rW1z)
    if (has_lower and has_upper and has_digit) and len(s) >= 16:
        # Tekil Almanca kelime başlangıcı değilse (örn: Grossbuchstabe)
        if not re.match(r"^[A-ZÄÖÜ][a-zäöüß]+$", s):
            return True

    # d) Cümle içi hex hash (MD5 32, SHA1 40, SHA256 64)
    if len(s) in (32, 40, 64) and re.match(r"^[a-fA-F0-9]+$", s) and any(c.isdigit() for c in s) and any(c.isalpha() for c in s):
        return True

    return False


def check_sensitive_clipboard(text: str) -> Tuple[bool, str]:
    """
    Panodan kopyalanan metnin parola, API anahtarı, erişim belirteci, IBAN,
    kredi kartı veya 40 karakterden uzun boşluksuz hassas veri içerip içermediğini denetler.

    Etiketli girdileri (örn. 'Meine IBAN: ...', 'Passwort: ...', 'Kartennummer ...'),
    çok satırlı panoları ve metin içi hassas belirteçleri algılar.

    Dönüş: (is_sensitive: bool, reason: str)
    """
    if not text:
        return False, ""
    s = text.strip()
    if not s:
        return False, ""

    # 1. 40 karakterden uzun ve boşluk içermeyen metinler (token, hash, şifre, base64)
    # NOT: Bilinen güvenlik/kullanılabilirlik ödünleşimi olarak, 40+ karakterlik
    # çok nadir Almanca hukuki birleşik sözcükler de bu kurala takılabilir.
    if len(s) > 40 and not any(c.isspace() for c in s):
        return True, "40 karakterden uzun boşluksuz veri/belirteç"

    # 2. Özel servis anahtarları ve belirteçler (API Keys, Tokens, JWT, DPAPI, SSH)
    if _RE_AIZA_KEY.search(s):
        return True, "Google API Anahtarı"
    if _RE_SK_KEY.search(s):
        return True, "API Gizli Anahtarı"
    if _RE_GH_TOKEN.search(s):
        return True, "GitHub Erişim Belirteci"
    if _RE_AWS_KEY.search(s):
        return True, "AWS Erişim Anahtarı"
    if _RE_SLACK_TOKEN.search(s):
        return True, "Slack Belirteci"
    if _RE_JWT.search(s):
        return True, "JSON Web Token (JWT)"
    if _RE_PRIVATE_KEY.search(s):
        return True, "Özel Anahtar (Private Key)"
    if "dpapi:" in s:
        return True, "DPAPI Şifreli Metin"

    # 3. Etiketli Parola / Anahtar / Belirteç (Passwort: ..., Password = ...)
    labeled_match = _RE_LABELED_SECRET.search(s)
    if labeled_match:
        val = (labeled_match.group(1) or labeled_match.group(2) or labeled_match.group(3) or "").strip()
        is_secret = True
        # Eğer eşleşme yalnızca 'bearer <kelime>' kalıbından geldiyse ve kelime sıradan bir sözlük sözcüğüyse
        # (örn. 'the bearer certificate', 'bearer shares', 'bearer bond') bunu hassas anahtar sayma
        if labeled_match.group(2) and not labeled_match.group(1) and not labeled_match.group(3):
            if val.isalpha() and (val.islower() or val.istitle()):
                is_secret = False
        if is_secret and len(val) >= 4:
            return True, "Etiketli Parola / Gizli Anahtar"

    # 4. Finansal Bilgiler: IBAN Numarası (harf büyüklüğünden bağımsız, metin içinde arama)
    for m in _RE_IBAN_SEARCH.finditer(s):
        compact_iban = re.sub(r"[\s-]", "", m.group()).upper()
        if (
            15 <= len(compact_iban) <= 34
            and re.match(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}$", compact_iban)
            and sum(c.isdigit() for c in compact_iban) >= 10
        ):
            return True, "IBAN Numarası"

    # 5. Finansal Bilgiler: Kredi Kartı Numarası (Luhn kontrolü, etiket ve blok kalıpları)
    card_label_m = _RE_CARD_LABEL.search(s)
    if card_label_m:
        digits_only = re.sub(r"[\s-]", "", card_label_m.group(1))
        if 13 <= len(digits_only) <= 19:
            return True, "Kredi Kartı Numarası (Etiketli)"

    for m in re.finditer(r"\b(?:\d[ -]?){13,19}\b", s):
        raw_digits = re.sub(r"[\s-]", "", m.group())
        if 13 <= len(raw_digits) <= 19 and luhn_checksum(raw_digits):
            return True, "Kredi Kartı Numarası (Luhn Doğrulandı)"

    if _RE_CREDIT_CARD_BLOCKS.search(s):
        return True, "Kredi Kartı Numarası"

    # 6. UUID ve Kriptografik Özetler (Hash)
    if _RE_UUID.search(s):
        return True, "UUID Belirteci"
    if not any(c.isspace() for c in s) and len(s) in (32, 40, 64) and re.match(r"^[a-fA-F0-9]+$", s):
        return True, "Kriptografik Özet (Hash)"

    # 7. Kelime / Belirteç bazında metin içi karmaşık parola taraması
    for token in re.split(r"[\s,;()]+", s):
        if _is_password_token(token):
            return True, "Karmaşık Parola / Şifre"

    return False, ""


def is_sensitive_clipboard_text(text: str) -> bool:
    """
    Panodan kopyalanan metnin hassas veri olup olmadığını boolean olarak döner.
    """
    is_sens, _ = check_sensitive_clipboard(text)
    return is_sens
