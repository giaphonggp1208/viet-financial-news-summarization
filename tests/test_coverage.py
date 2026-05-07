from visum.coverage import number_guided_summary
from visum.metrics import audit_sample


def test_number_guided_summary_pulls_numbers_from_later_sentences():
    source = (
        "Công ty A công bố kết quả kinh doanh mới. "
        "Ban lãnh đạo cho biết thị trường đầu năm còn nhiều biến động. "
        "Doanh thu quý đạt 1.400 tỷ đồng, tăng 3,1% so với cùng kỳ. "
        "Lợi nhuận sau thuế đạt 620 tỷ đồng, biên lợi nhuận đạt 2,4%. "
        "Dòng tiền kinh doanh đạt 270 tỷ đồng và tổng tài sản tăng 4,6%. "
        "Công ty đặt mục tiêu doanh thu năm tới 5.800 tỷ đồng, tăng 7%."
    )
    draft = "Công ty A công bố kết quả kinh doanh mới."

    summary = number_guided_summary(source, draft, min_ratio=0.20, max_ratio=0.60)

    assert "1.400 tỷ đồng" in summary
    assert "620 tỷ đồng" in summary
    assert "5.800 tỷ đồng" in summary
    assert audit_sample(source, summary, number_mode="summary_subset").number_ok
