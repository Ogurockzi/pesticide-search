import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="농약 검색기", layout="centered")
st.title("🌿 농약 검색기 (by 현별)")

API_URL = "https://psis.rda.go.kr/openApi/service.do"
# 🔐 키는 Streamlit Cloud의 Secrets에 PSIS_API_KEY로 넣어주세요.
API_KEY = st.secrets["PSIS_API_KEY"]

# ---------- 유틸 ----------
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
        "apiKey": API_KEY,
        "serviceCode": "SVC02",
        "serviceType": "AA001",
        "pestiCode": pesti_code,
        "diseaseUseSeq": disease_use_seq,
    }
    try:
        r = requests.get(API_URL, params=params, timeout=10)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        it = root.find(".//item")
        if it is None:
            return {"use_time": "-", "use_num": "-"}
        flat = flatten_item(it)
        use_time = pick(flat, "useSuittime", "useSeason", "safeUsePrid", "useLimit")
        use_num  = pick(flat, "useNum", "limitNum")
        return {"use_time": use_time or "-", "use_num": use_num or "-"}
    except Exception:
        return {"use_time": "-", "use_num": "-"}

def run_search(brand: str, crop: str, item: str, company: str):
    params = {
        "apiKey": API_KEY,
        "serviceType": "AA001",
        "serviceCode": "SVC01",
        "displayCount": "50",
        "startPoint": "1",
    }
    if brand:   params["pestiBrandName"] = brand
    if crop:    params["cropName"] = crop
    if item:    params["pestiKorName"] = item
    if company: params["compName"] = company

    r = requests.get(API_URL, params=params, timeout=15)
    r.raise_for_status()

    root = ET.fromstring(r.content)
    err = root.findtext("errorCode")
    if err:
        msg = root.findtext("errorMsg") or ""
        st.warning(f"API 오류: {err} - {msg}")
        return

    items = root.findall(".//item")
    if not items:
        st.warning("검색 결과가 없습니다.")
        return

    rows = []
    for it in items:
        flat = flatten_item(it)

        pesti_code = pick(flat, "pestiCode", "pestiCd", default="")
        disease_use_seq = pick(flat, "diseaseUseSeq", "diseaseSeq", default="")

        use_time = pick(flat, "useSuittime", "useSeason", "safeUsePrid", "useLimit")
        use_num  = pick(flat, "useNum", "limitNum")

        if (use_time == "-" or use_num == "-") and pesti_code and disease_use_seq:
            detail = svc02_detail(pesti_code, disease_use_seq)
            if use_time == "-":
                use_time = detail["use_time"]
            if use_num == "-":
                use_num = detail["use_num"]

        rows.append({
            "상표명":  pick(flat, "prdlstNm", "pestiBrandName"),
            "작물명":  pick(flat, "cropNm", "cropName"),
            "안전사용기준(시기)": use_time or "-",
            "안전사용기준(횟수)": use_num or "-",
            "병해충명": pick(flat, "diseaseWeedNm", "diseaseWeedName", "diseaseUseNm", "virusNm"),
            "품목명":  pick(flat, "itemNm", "pestiKorName", "formulationNm"),
            "사용량":  pick(flat, "useDilut", "dilutUnit"),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        st.warning("검색 결과가 없습니다.")
        return

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

# ---------- 폼 제출 (엔터 검색 & IME 중복 방지) ----------
with st.form(key="search_form", clear_on_submit=False):
    c1, c2, c3, c4 = st.columns(4)
    with c1: brand = st.text_input("상표명", key="brand").strip()
    with c2: crop = st.text_input("작물명", key="crop").strip()
    with c3: item = st.text_input("품목명", key="item").strip()
    with c4: company = st.text_input("회사명", key="company").strip()
    submit = st.form_submit_button("🔎 검색")

if submit:
    try:
        run_search(
            st.session_state.get("brand", "").strip(),
            st.session_state.get("crop", "").strip(),
            st.session_state.get("item", "").strip(),
            st.session_state.get("company", "").strip(),
        )
    except requests.HTTPError as e:
        st.error(f"요청 실패: {e}")
    except Exception as e:
        st.error(f"오류: {e}")

