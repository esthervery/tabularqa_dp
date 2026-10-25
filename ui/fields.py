"""데모 데이터셋 필드 스펙 — 질의 콘솔 필드 힌트의 단일 정본.

설계 원칙
    1) dtype 으로 종류를 추론하지 않는다. 066 의 Education/JobLevel/JobSatisfaction 과
       047 의 attrition_flag, 073 의 children 은 모두 uint8 이지만 범주형이다.
    2) 스펙에는 '값'을 적지 않는다. 컬럼명·표시명·종류만 갖는다.
       값 목록을 스펙에 넣는 순간 그 파일이 유출 경로가 된다.
    3) 힌트는 종류(kind)만 노출한다.
       범주형 → 값 몇 종인지 / 수치형 → 사분위 3개 / 이진 결과 → 2종.
       값 자체·최소·최대·건수·비율은 화면에 내보내지 않는다. (ε 미차감 정보이므로)

사용
    from demo.fields import SPECS, ENABLED
    from demo.hints import build_all, build
"""
from __future__ import annotations

# kind: "measure" | "categorical" | "filter" | "pattern"
SPECS: dict[str, dict] = {
    "073_Med_Cost": {
        "title": "Medical Cost",
        "enabled": True,
        "measure": {"col": "charges", "label": "의료비", "unit": "USD"},
        "cat": [
            {"col": "sex",      "label": "성별"},
            {"col": "children", "label": "부양 자녀 수", "ordered": True},
            {"col": "region",   "label": "거주 지역"},
        ],
        "fil": [
            {"col": "age", "label": "나이",       "unit": "세"},
            {"col": "bmi", "label": "체질량지수", "unit": "BMI"},
        ],
        "pat": [
            {"col": "smoker", "label": "흡연 여부"},
        ],
    },
    "021_Telco": {
        "title": "Telco Customer Churn",
        "enabled": True,
        "measure": {"col": "MonthlyCharges", "label": "월 청구액", "unit": "USD"},
        "cat": [
            {"col": "gender",           "label": "성별"},
            {"col": "InternetService",  "label": "인터넷 종류"},
            {"col": "OnlineBackup",     "label": "온라인 백업 가입"},
            {"col": "StreamingTV",      "label": "TV 스트리밍 가입"},
            {"col": "StreamingMovies",  "label": "영화 스트리밍 가입"},
            {"col": "Contract",         "label": "계약 형태", "ordered": True},
            {"col": "PaymentMethod",    "label": "결제 수단"},
        ],
        "fil": [
            {"col": "tenure", "label": "가입 개월 수", "unit": "개월"},
        ],
        "pat": [
            {"col": "Churn", "label": "이탈 여부"},
        ],
    },
    "066_IBM_HR": {
        "title": "IBM HR Attrition",
        "enabled": True,
        "measure": {"col": "MonthlyIncome", "label": "월급", "unit": "USD"},
        "cat": [
            {"col": "Education",       "label": "학력",       "ordered": True},
            {"col": "Gender",          "label": "성별"},
            {"col": "JobLevel",        "label": "직급",       "ordered": True},
            {"col": "JobRole",         "label": "직무"},
            {"col": "JobSatisfaction", "label": "직무 만족도", "ordered": True},
        ],
        "fil": [
            {"col": "Age",               "label": "나이",         "unit": "세"},
            {"col": "TotalWorkingYears", "label": "총 경력 연수",  "unit": "년"},
            {"col": "YearsAtCompany",    "label": "현 직장 근속",  "unit": "년"},
        ],
        "pat": [
            {"col": "OverTime", "label": "초과근무 여부"},
        ],
    },
    "047_Bank": {
        "title": "Bank Customers",
        "enabled": True,
        "measure": {"col": "credit_limit", "label": "신용한도", "unit": "USD"},
        "cat": [
            {"col": "gender",          "label": "성별"},
            {"col": "education_level", "label": "학력"},
            {"col": "income_category", "label": "소득 구간", "ordered": True},
        ],
        "fil": [
            {"col": "customer_age", "label": "고객 나이", "unit": "세"},
        ],
        "pat": [
            {"col": "attrition_flag", "label": "이탈 여부"},
        ],
    },
    # 024_Salary 는 216,726행이라 데모 UI 에서 제외 (스펙은 남겨 둔다)
    "024_Salary": {
        "title": "Salary Survey Spain 2018",
        "enabled": False,
        "measure": {"col": "RETRINOIN", "label": "연봉", "unit": "EUR"},
        "cat": [
            {"col": "ESTU",    "label": "학력",     "ordered": True},
            {"col": "SEXO",    "label": "성별"},
            {"col": "ANOS2",   "label": "연령대",   "ordered": True},
            {"col": "NUTS1",   "label": "지역"},
            {"col": "CONTROL", "label": "공공/민간"},
            {"col": "TIPOJOR", "label": "근무 형태"},
        ],
        "fil": [
            {"col": "ANOANTI", "label": "현 직장 근속 연수", "unit": "년"},
        ],
        "pat": [],
    },
}

ENABLED: list[str] = [k for k, v in SPECS.items() if v["enabled"]]


def kinds_of(spec: dict) -> dict:
    """데이터셋 하나의 노출 필드 수를 센다 — 화면 캡션·검증용."""
    return {
        "measure": 1,
        "categorical": len(spec["cat"]),
        "filter": len(spec["fil"]),
        "pattern": len(spec["pat"]),
        "exposed": len(spec["cat"]) + len(spec["fil"]) + len(spec["pat"]),
    }
