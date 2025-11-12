import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="현별이 농약 검색기", layout="centered")

st.markdown(
    """
    <style>
    h1 { font-size: 22px !important; text-align:center; margin-bottom:10px; }
    .stTextInput>div>div>input {height: 30px !important; font-size:14px;}
    div[data-testid="stForm"] {
        padding: 0.5rem 0.8rem;
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🌿 현별이 농약 검색기")

API_URL = "https://psis.rda.go.kr/openApi/service.do"
API_KEY = st.secrets["PSIS_API_KEY"]


def pick(d, *keys, default="-"):
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return default


def flatten(item):
    row = {}
    for child in item:
        if list(child):
            for sub in child:
                row[sub.tag] = (sub.text or "").strip()
        else:
            row[child.tag] = (child.text or "").strip()
    return row


def svc02_detail(pesti_code, disease_seq):
    params = {
        "apiKey": API_KEY,
        "serviceCode": "SVC02",
        "serviceType": "AA001",
        "pestiCode": pesti_code,
        "diseaseUseSeq": disease_seq,
    }
    try:
        r = requests.get(API_URL, params=params, timeout=10)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        item = root.find(".//item")
        if item is None:
            return {"use_time": "-", "use_num": "-"}
        flat = flatten(item)
        return {
            "use_time": pick(flat, "useSuittime", "useSeason", "safeUsePrid"),
            "use_num": pick(flat, "useNum", "limitNum"),
        }
    except Exception:
        return {"use_time": "-", "use_num": "-"}


def run_search(brand, crop, item, company):
    params = {
        "apiKey": API_KEY,
        "serviceCode": "SVC01",
        "serviceType": "AA001",
        "displayCount": "50",
        "startPoint": "1",
    }
    if brand:
        params["pestiBrandName"] = brand
    if crop:
        params["cropName"] = crop
    if item:
        params["pestiKorName"] = item
    if company:
        params["compName"] = company

    r = requests.get(API_URL, params=params, timeout=10)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    items = root.findall(".//item")

    if not items:
        st.warning("검색 결과가 없습니다.")
        return

    rows = []
    for it in items:
        flat = flatten(it)
        pesti_code = pick(flat, "pestiCode", "pestiCd", default="")
        disease_seq = pick(flat, "diseaseUseSeq", "diseaseSeq", default="")
        detail = svc02_detail(pesti_code, disease_seq)

        rows.append({
            "상표명": pick(flat, "prdlstNm", "pestiBrandName"),
            "작물명": pick(flat, "cropNm", "cropName"),
            "안전사용기준(시기)": detail["use_time"],
            "안전사용기준(횟수)": detail["use_num"],
            "병해충명": pick(flat, "diseaseWeedNm", "diseaseWeedName"),
            "품목명": pick(flat, "itemNm", "pestiKorName"),
            "사용량": pick(flat, "useDilut", "dilutUnit"),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    st.download_button("📥 엑셀 다운로드", buf.getvalue(), "농약검색결과.xlsx")


# 🔹 입력창 2x2 고정
with st.form(key="search_form"):
    col1, col2 = st.columns(2)
    with col1:
        brand = st.text_input("상표명")
        item = st.text_input("품목명")
    with col2:
        crop = st.text_input("작물명")
        company = st.text_input("회사명")

    submit = st.form_submit_button("🔍 검색")

if submit:
    run_search(brand.strip(), crop.strip(), item.strip(), company.strip())
