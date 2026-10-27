"""개인정보 처리방침 화면 (로그인 전).
"""
import streamlit as st

VIEW = "auth_view"          # auth.py 와 같은 키
EFFECTIVE = "2026. 10. 28"  # 시행일 — 실제 게시일로 바꾸세요
RETENTION = "회원 탈퇴 시까지 보관하며, 탈퇴하면 지체 없이 파기합니다."

ITEMS = [
    ("계정 정보",
     "아이디, 비밀번호, 가입 일시, 마지막 로그인 일시, 계정 권한(일반·관리자), 개인 사용 한도",
     "본인 확인과 로그인, 권한 확인, 사용 한도 관리"),
    ("질의 기록",
     "질문 내용, 질문한 데이터셋, 질문 일시, 응답 결과와 분석 코드, 처리 성공 여부, 사용한 프라이버시 예산(ε)",
     "채팅 기록 제공, 데이터셋별 남은 예산 계산, 예산 신청 심사"),
    ("예산 신청 기록",
     "신청 데이터셋, 현재 단계와 신청 단계, 신청 사유, 신청 일시, "
     "처리 결과(승인 단계, 처리 일시, 처리한 관리자, 관리자 메모)",
     "신청 심사와 결과 안내"),
    ("적용 중인 개인 정책",
     "승인된 Utility 단계, 승인 일시, 승인한 관리자, 메모",
     "승인된 단계를 질의에 적용"),
]


def _back() -> None:
    st.session_state[VIEW] = "login"


def _text_html() -> str:
    return (
        '<div class="pp-sec">'
        '<h3>1. 수집하는 개인정보와 이용 목적</h3>'
        '<p>DPilot은 회원가입과 서비스 이용에 꼭 필요한 정보만 저장합니다. '
        '이 정보는 서비스 이용 계약을 이행하기 위해 필요한 것이어서 별도 동의 없이 처리합니다 '
        '(개인정보 보호법 제15조 제1항 제4호).</p>'

        '<h4>계정 정보</h4>'
        '<p>아이디, 비밀번호, 가입 일시, 마지막 로그인 일시, 계정 권한(일반·관리자), 개인 사용 한도를 저장합니다. '
        '본인 확인과 로그인, 권한 확인, 사용 한도 관리에 이용합니다. '
        '비밀번호는 원래대로 되돌릴 수 없는 형태로 바꿔서 저장하므로, 운영자도 알 수 없습니다.</p>'

        '<h4>질의 기록</h4>'
        '<p>입력한 질문, 질문한 데이터셋과 일시, 응답 결과와 분석 코드, 처리 성공 여부, '
        '사용한 프라이버시 예산(ε)을 저장합니다. 채팅 기록을 보여 드리고, 데이터셋별로 남은 예산을 '
        '계산하는 데 이용합니다. 예산 상향을 신청하면 관리자가 심사할 때 이 기록을 확인합니다.</p>'

        '<h4>예산 신청 기록</h4>'
        '<p>신청한 데이터셋, 현재 단계와 신청 단계, 신청 사유, 신청 일시, 처리 결과'
        '(승인 단계, 처리 일시, 처리한 관리자, 관리자 메모)를 저장합니다. '
        '신청을 심사하고 결과를 알려 드리는 데 이용합니다.</p>'

        '<h4>적용 중인 개인 정책</h4>'
        '<p>승인된 Utility 단계, 승인 일시, 승인한 관리자, 메모를 저장합니다. '
        '승인된 단계를 질의에 적용하는 데 이용합니다.</p>'
        '</div>'
    )


def _table_html() -> str:
    rows = "".join(
        f'<tr><th scope="row">{k}</th><td>{items}</td><td>{purpose}</td></tr>'
        for k, items, purpose in ITEMS
    )
    return (
        '<div class="pp-sec">'
        '<h3>한눈에 보기</h3>'
        '<table class="pp-tbl">'
        '<thead><tr><th>구분</th><th>저장하는 항목</th><th>이용 목적</th></tr></thead>'
        f'<tbody>{rows}</tbody>'
        '</table>'
        '<p class="pp-foot">법적 근거: 서비스 이용 계약의 이행(개인정보 보호법 제15조 제1항 제4호)'
        f' · 보관 기간: {RETENTION}</p>'
        '<p class="pp-warn">※ 질문과 신청 사유에는 이름, 연락처 같은 개인정보를 입력하지 마세요.</p>'
        '</div>'
    )


def render() -> None:
    st.markdown("<div style='height:4vh'></div>", unsafe_allow_html=True)

    st.button("로그인/회원가입 화면으로 돌아가기", key="pp_back_top",
              type="tertiary", icon=":material/arrow_back:", on_click=_back)

    with st.container(border=True, key="pp_card"):
        st.html(
            '<div class="pp-head"><h2>개인정보 처리방침</h2>'
            f'<span>시행일 {EFFECTIVE}</span></div>'
        )
        st.html(_text_html())
        st.html(_table_html())

        with st.container(horizontal=True, horizontal_alignment="right", key="pp_bottom"):
            st.button("로그인/회원가입 화면으로 돌아가기", key="pp_back",
                      on_click=_back)

    st.markdown(
        '<div class="lfoot">© 2026 DPilot · AILS-NTUA / DataBench pipeline · demonstration build</div>',
        unsafe_allow_html=True,
    )