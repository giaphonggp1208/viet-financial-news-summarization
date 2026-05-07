from visum.metrics import audit_sample


def test_audit_checks_length_and_numbers():
    source = " ".join([f"từ{i}" for i in range(80)]) + " Doanh thu đạt 100 tỷ đồng."
    summary = " ".join([f"tóm{i}" for i in range(18)]) + " 100 tỷ đồng."

    audit = audit_sample(source, summary)

    assert audit.number_ok
    assert audit.length_ok
    assert 0.20 <= audit.compression_ratio <= 0.25

