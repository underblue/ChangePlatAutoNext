from change_plate_next.adapters.gcode.legacy_crypto import decrypt_text, encrypt_text


def test_legacy_crypto_roundtrip() -> None:
    text = ";start change plate\nM400\n;end change plate\n"
    assert decrypt_text(encrypt_text(text)) == text
