# pesticide_search.py — 안정판: 검색 100% + PC 2×2 / 모바일 초미니 1열
import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="현별이 농약 검색기", layout="centered")

# ---- 스타일(여백/높이 최소화) ----
st.markdown("""
<style>
.main .block-container{padding-top:.35rem;padding-bottom:.6rem;max-width:860px}
h1{font-size:1.05rem;margin:.2rem 0 .5rem;font-weight:800}
div[data-testid="stTextInput"] label{font-size:.9rem;margin-bottom:.12rem}
div[data-testid="stTextInput"] input{height:34px;padding:4px 8px;font-size:14px;border-radius:8px}
button[kind="primary"]{padding:6px 12px!important;font-size:.9rem!important;border-radius:9px!important}
.stDataFrame{margin-top:.45rem}
@media (max-width:480px){
  div[data-testid="stTextInput"] label{font-size:.88rem}
  div[data-testid="stTextInput"] input{height:32px;font-size:13.5px}
  button[kind="primary"]{padding:5px 10px!important;font-size:.86rem!important}
}
</style>
""", unsafe_allow_html=True)

st.title("🌿 현별이 농약 검색기")

API_URL = "https://psis.rda.go.kr/openApi/service.do"
API_KEY = st.secrets["PSIS_API_KEY"]  # Streamlit Cloud Secrets에 PSIS_API_KEY 등록돼 있어야 함

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

# ---- 폼 (PC 2×2 / 모바일 1열; 모바일은 높이 극소) ----
with st.form("search_form", clear_on_submit=False):
    c1, c2 = st.columns(2, gap="small")
    with c1:
        brand = st.text_input("상표명", key="brand").strip()
        item  = st.text_input("품목명", key="item").strip()
    with c2:
        crop    = st.text_input("작물명", key="crop").strip()
        company = st.text_input("회사명", key="company").strip()
    submit = st.form_submit_button("🔎 검색")

if submit:
    try:
        run_search(brand, crop, item, company)
    except requests.HTTPError as e:
        st.error(f"요청 실패: {e}")
    except Exception as e:
        st.error(f"오류: {e}")
