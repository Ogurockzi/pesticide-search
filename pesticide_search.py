# pesticide_search.py — 1열 고정 (상표명→작물명→품목명→회사명), 엔터로 즉시 검색, 버튼 없음
import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="현별이 농약 검색기", layout="centered")

# ===== 스타일: 타이틀 = 라벨과 동일 크기, 여백/높이 최소화 =====
st.markdown("""
<style>
.main .block-container{padding-top:.35rem;padding-bottom:.6rem;max-width:860px}
.app-title{font-size:.90rem;font-weight:800;letter-spacing:-.01em;margin:.15rem 0 .45rem}
div[data-testid="stTextInput"] label{font-size:.90rem;margin-bottom:.12rem}
div[data-testid="stTextInput"] input{
  height:34px;padding:4px 8px;font-size:14px;border-radius:8px
}
.stDataFrame{margin-top:.45rem}
@media (max-width:480px){
  .app-title{font-size:.90rem}
  div[data-testid="stTextInput"] label{font-size:.90rem}
  div[data-testid="stTextInput"] input{height:32px;font-size:13.5px}
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="app-title">🌿 현별이 농약 검색기</div>', unsafe_allow_html=True)

API_URL = "https://psis.rda.go.kr/openApi/service.do"
API_KEY = st.secrets["PSIS_API_KEY"]  # Streamlit Cloud Secrets에 PSIS_API_KEY 넣어둔 값

# ===== 유틸 =====
def pick(d: dict, *keys, default="-"):
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return default

def flatten_item(xitem):
    row = {}
    for child in xitem:
        if list(child):
            for sub in child:
                row[sub.tag] = (sub.text or "").strip()
        else:
            row[child.tag] = (child.text or "").strip()
    return row

def svc02_detail(pesti_code: str, disease_use_seq: str) -> dict:
    params = {
        "apiKey": API_KEY, "serviceCode": "SVC02", "serviceType": "AA001",
        "pestiCode": pesti_code, "diseaseUseSeq": disease_use_seq,
    }
    try:
        r = requests.get(API_URL, params=params, timeout=10); r.raise_for_status()
        root = ET.fromstring(r.content); it = root.find(".//item")
        if it is None: return {"use_time": "-", "use_num": "-"}
        flat = flatten_item(it)
        use_time = pick(flat, "useSuittime", "useSeason", "safeUsePrid", "useLimit")
        use_num  = pick(flat, "useNum", "limitNum")
        return {"use_time": use_time or "-", "use_num": use_num or "-"}
    except Exception:
        return {"use_time": "-", "use_num": "-"}

def run_search(brand: str, crop: str, item: str, company: str):
    params = {
        "apiKey": API_KEY, "serviceType": "AA001", "serviceCode": "SVC01",
        "displayCount": "50", "startPoint": "1",
    }
    if brand:   params["pestiBrandName"] = brand
    if crop:    params["cropName"] = crop
    if item:    params["pestiKorName"] = item
    if company: params["compName"] = company

    r = requests.get(API_URL, params=params, timeout=15); r.raise_for_status()
    root = ET.fromstring(r.content)
    if root.findtext("errorCode"):
        st.warning(f"API 오류: {root.findtext('errorCode')} - {root.findtext('errorMsg') or ''}")
        return

    items = root.findall(".//item")
    if not items:
        st.warning("검색 결과가 없습니다."); return

    rows = []
    for it in items:
        flat = flatten_item(it)
        pesti_code = pick(flat, "pestiCode", "pestiCd", default="")
        disease_use_seq = pick(flat, "diseaseUseSeq", "diseaseSeq", default="")
        use_time = pick(flat, "useSuittime", "useSeason", "safeUsePrid", "useLimit")
        use_num  = pick(flat, "useNum", "limitNum")

        # 상세 조회로 보강
        if (use_time == "-" or use_num == "-") and pesti_code and disease_use_seq:
            detail = svc02_detail(pesti_code, disease_use_seq)
            if use_time == "-": use_time = detail["use_time"]
            if use_num  == "-": use_num  = detail["use_num"]

        rows.append({
            "상표명": pick(flat, "prdlstNm", "pestiBrandName"),
            "작물명": pick(flat, "cropNm", "cropName"),
            "안전사용기준(시기)": use_time or "-",
            "안전사용기준(횟수)": use_num or "-",
            "병해충명": pick(flat, "diseaseWeedNm","diseaseWeedName","diseaseUseNm","virusNm"),
            "품목명": pick(flat, "itemNm", "pestiKorName", "formulationNm"),
            "사용량": pick(flat, "useDilut", "dilutUnit"),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch")

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="검색결과")
    st.download_button(
        "📥 엑셀 다운로드",
        data=buf.getvalue(),
        file_name="농약검색결과.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# ===== 엔터로 즉시 검색 (버튼 없이) =====
def _trigger_search():
    st.session_state["do_search"] = True

# 입력 순서: 상표명 → 작물명 → 품목명 → 회사명 (항상 1열)
brand   = st.text_input("상표명",  key="brand",   on_change=_trigger_search).strip()
crop    = st.text_input("작물명",  key="crop",    on_change=_trigger_search).strip()
item    = st.text_input("품목명",  key="item",    on_change=_trigger_search).strip()
company = st.text_input("회사명",  key="company", on_change=_trigger_search).strip()

# 엔터 입력(on_change) 또는 이전 검색 결과 유지 후 재입력 시 자동 실행
if st.session_state.get("do_search"):
    st.session_state["do_search"] = False
    try:
        run_search(brand, crop, item, company)
    except requests.HTTPError as e:
        st.error(f"요청 실패: {e}")
    except Exception as e:
        st.error(f"오류: {e}")
