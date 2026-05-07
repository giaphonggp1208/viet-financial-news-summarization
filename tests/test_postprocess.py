from visum.numbers import numbers_match
from visum.postprocess import drop_extra_number_sentences, repair_extra_numbers_by_source


def test_drop_extra_number_sentences_removes_hallucinated_numbers():
    source = "Doanh thu đạt 100 tỷ đồng. Lợi nhuận đạt 20 tỷ đồng."
    summary = "Doanh thu đạt 100 tỷ đồng. Lợi nhuận đạt 999 tỷ đồng."

    cleaned = drop_extra_number_sentences(source, summary)

    assert "100 tỷ đồng" in cleaned
    assert "999 tỷ đồng" not in cleaned
    assert numbers_match(source, cleaned, mode="summary_subset")


def test_repair_extra_numbers_by_source_restores_missing_units():
    source = "Mục tiêu lợi nhuận đạt 6.200 tỷ đồng và dư nợ đạt 240.000 tỷ đồng."
    summary = "Mục tiêu lợi nhuận đạt 6.200 đồng và dư nợ đạt 240.000 tỷ đồng."

    repaired = repair_extra_numbers_by_source(source, summary)

    assert "6.200 tỷ đồng" in repaired
    assert numbers_match(source, repaired, mode="summary_subset")
