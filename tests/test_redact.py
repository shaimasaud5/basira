from app.redact import redact


def test_mobile_formats():
    for number in ["0501234567", "+966501234567", "00966501234567", "966 50 123 4567", "050-123-4567"]:
        clean, counts = redact(f"اتصل على {number} الآن")
        assert number not in clean and "[جوال]" in clean, number
        assert counts["mobile"] == 1


def test_arabic_indic_digits_mobile():
    clean, counts = redact("جوال ٠٥٠١٢٣٤٥٦٧")
    assert "[جوال]" in clean and counts["mobile"] == 1


def test_iban_with_and_without_spaces():
    for iban in ["SA0380000000608010167519", "SA03 8000 0000 6080 1016 7519"]:
        clean, counts = redact(f"الآيبان {iban} للتحويل")
        assert "[آيبان]" in clean and "8000" not in clean, iban
        assert counts["iban"] == 1 and counts["national_id"] == 0


def test_national_id_and_iqama():
    clean, counts = redact("هوية 1234567890 وإقامة 2345678901")
    assert clean.count("[هوية]") == 2 and counts["national_id"] == 2


def test_email():
    clean, counts = redact("راسلني على ahmed.k@example.com")
    assert "example.com" not in clean and counts["email"] == 1


def test_rent_amounts_and_normal_numbers_are_kept():
    text = "الإيجار السنوي 96000 ريال بزيادة 5% كل سنة، مدة العقد 24 شهر، المساحة 120 م2."
    clean, counts = redact(text)
    assert clean == text and sum(counts.values()) == 0


def test_eleven_digit_number_is_not_an_id():
    clean, _ = redact("رقم 12345678901")
    assert "[هوية]" not in clean


def test_multiple_types_in_one_text():
    clean, counts = redact("جوال 0501234567 وإيميل a@b.com وهوية 1012345678")
    assert counts == {"iban": 0, "email": 1, "mobile": 1, "national_id": 1}
    assert "0501234567" not in clean and "a@b.com" not in clean and "1012345678" not in clean


def test_empty_text():
    assert redact("") == ("", {"iban": 0, "email": 0, "mobile": 0, "national_id": 0})
