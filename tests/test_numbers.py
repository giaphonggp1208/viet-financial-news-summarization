from visum.numbers import extract_numbers, extra_numbers, missing_numbers, numbers_match


def test_extracts_vietnamese_finance_numbers_without_date_fragments():
    text = (
        "Ngày 12/03/2025, VN-Index tăng 8,14 điểm lên 1.248,33 điểm; "
        "thanh khoản đạt 18.500 tỷ đồng, cao hơn 12%."
    )

    numbers = extract_numbers(text)

    assert "12/03/2025" in numbers
    assert "8,14 điểm" in numbers
    assert "1.248,33 điểm" in numbers
    assert "18.500 tỷ đồng" in numbers
    assert "12%" in numbers
    assert "03" not in numbers


def test_number_match_detects_missing_and_extra_values():
    source = "Doanh thu đạt 3.200 tỷ đồng, tăng 18% trong quý I/2025."
    summary = "Doanh thu đạt 3.200 tỷ đồng, tăng 20%."

    assert not numbers_match(source, summary)
    assert "18%" in missing_numbers(source, summary)
    assert "quý i/2025" in missing_numbers(source, summary)
    assert "20%" in extra_numbers(source, summary)


def test_extracts_cafef_date_ranges_and_price_per_share():
    text = (
        "Lịch chốt quyền cổ tức 4-8/5, cao nhất 5.000 đồng/cp, "
        "ngày 18/5/2026 có 15,7 triệu cổ phiếu và 79 tỷ đồng."
    )

    numbers = extract_numbers(text)

    assert "4-8/5" in numbers
    assert "5.000 đồng/cp" in numbers
    assert "18/5/2026" in numbers
    assert "15,7 triệu cổ phiếu" in numbers
    assert "79 tỷ đồng" in numbers


def test_normalizes_ti_and_ty_currency_spelling():
    source = "Doanh thu đạt 1.324 tỉ đồng và lợi nhuận 75 tỉ đồng."
    summary = "Doanh thu đạt 1.324 tỷ đồng và lợi nhuận 75 tỷ đồng."

    assert numbers_match(source, summary)


def test_extracts_additional_cafef_units():
    text = "Giá vàng đạt 4.600 USD/ounce, cổ phiếu ở 214.000 đồng/cổ phiếu và sản lượng 133.765 tấn/năm."

    numbers = extract_numbers(text)

    assert "4.600 usd/ounce" in numbers
    assert "214.000 đồng/cổ phiếu" in numbers
    assert "133.765 tấn/năm" in numbers
