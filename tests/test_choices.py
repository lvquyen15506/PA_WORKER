from apps.core import choices


def test_bon_bo_trang_thai_dung_gia_tri():
    assert [c.value for c in choices.VerificationStatus] == [
        "DRAFT",
        "PENDING",
        "NEEDS_INFO",
        "VERIFIED",
        "REJECTED",
        "ARCHIVED",
    ]
    assert [c.value for c in choices.WorkStatus] == [
        "AWAITING",
        "PROBATION",
        "ACTIVE",
        "SUSPENDED",
        "RESIGNED",
    ]
    assert [c.value for c in choices.RecruitmentStatus] == [
        "NEW",
        "SCREENING",
        "INTERVIEW",
        "PASSED",
        "FAILED",
        "DECLINED",
    ]
    assert [c.value for c in choices.DocumentVerificationStatus] == [
        "UNVERIFIED",
        "MATCHED",
        "INVALID",
    ]


def test_nhan_tieng_viet():
    assert choices.VerificationStatus.NEEDS_INFO.label == "Cần bổ sung"
    assert choices.WorkStatus.AWAITING.label == "Chờ nhận việc"
    assert choices.Gender.values == ["MALE", "FEMALE"]


def test_khong_co_trang_thai_cho_huy():
    assert "PENDING_DESTROY" not in choices.VerificationStatus.values
    assert len(choices.AuditAction) == 21
    assert len(choices.RetentionBasis) == 6
