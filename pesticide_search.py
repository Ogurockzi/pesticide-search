# pesticide_search.py — 2x2 고정(모바일 포함), 초미니 UI
import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from io import BytesIO
import streamlit.components.v1 as components

st.set_page_config(page_title="농약 검색기", layout="centered")

# ========== CSS: 2x2 고정 + 초미니 입력/버튼 ==========
st.markdown("""
<style>
/* 전체 여백 최소화 */
.main .block-container{padding-top:.25rem;padding-bottom:.4rem;max-width:860px}

/* 제목 작게 */
.app-title{font-weight:800;font-size:1.06rem;letter-spacing:-.02em;margin:.05rem 0 .35rem}

/* 폼 카드 */
.form-card{border:1px solid #eee;border-radius:10px;padding:.38rem .45rem;background:#fff}

/* 2x2 고정 컨테이너: Streamlit의 모바일 스택 규칙을 무력화 */
.fixed-two-col [data-testid="stHorizontalBlock"]{
  display:flex !important;
  flex-wrap:wrap !important;
  gap:.35rem .45rem !important;
}
.fixed-two-col [data-testid="column"]{
  flex:0 0 calc(50% - .45rem) !important;
  width:calc(50% - .45rem) !important;
  min-width:0 !important;
}

/* 라벨/인풋 초미니화 */
div[data-testid="stTextInput"] label{font-size:.86rem;margin-bottom:.15rem}
div[data-testid="stTextInput"] input{
  height:32px;padding:4px 8px;font-size:14px;border-radius:8px;
}
div[data-testid="stTextInput"]{margin:0!important}

/* 버튼 초소형 */
button[kind="primary"]{
  padding:4px 10px!important;font-size:.84rem!important;
  line-height:1!important;border-radius:9px!important;
}

/* 표 간격 축소 */
.stDataFrame{margin-top:.35rem}

/* 아주 작은 화면에서도 2열 유지 */
@media (max-width:360px){
  .app-title{font-size:.98rem}
  .fixed-two-col [data-testid="column"]{
    flex:0 0 50% !important; width:50% !important;
  }
}
</style>
""", unsafe_allow_html=True)

# ========== 헤더 ==========
st.markdown('<div class="app-title">🌿 현별이 농약 검색기</div>', unsafe_allow_html=True)

API_URL = "https://psis.rda.go.kr/openApi/service.do"
API_KEY = st.secrets["PSIS_API_KEY"]  # Streamlit Secrets에 PSIS_API_KEY 등록

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
        "📥 엑셀 다운로드", data=buf.getvalue(),
        file_name="농약검색결과.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# ========== 폼: 2×2 고정 ==========
with st.form(key="search_form", clear_on_submit=False):
    st.markdown('<div class="form-card fixed-two-col">', unsafe_allow_html=True)

    # 1행: 상표명 | 작물명  (st.columns 사용, CSS로 2열 강제)
    c1, c2 = st.columns(2, gap="small")
    with c1: brand = st.text_input("상표명", key="brand").strip()
    with c2: crop  = st.text_input("작물명", key="crop").strip()

    # 2행: 품목명 | 회사명
    c3, c4 = st.columns(2, gap="small")
    with c3: item    = st.text_input("품목명", key="item").strip()
    with c4: company = st.text_input("회사명", key="company").strip()

    # 버튼
    left, _ = st.columns([1,3])
    with left: submit = st.form_submit_button("🔎 검색")

    st.markdown("</div>", unsafe_allow_html=True)

if submit:
    # 제출 후 키보드 내리고 상단으로 이동
    components.html("""
      <script>
        setTimeout(function(){
          if (document.activeElement) { document.activeElement.blur(); }
          window.scrollTo({top: 0, behavior: 'smooth'});
        }, 40);
      </script>
    """, height=0)
    try:
        run_search(
            st.session_state.get("brand","").strip(),
            st.session_state.get("crop","").strip(),
            st.session_state.get("item","").strip(),
            st.session_state.get("company","").strip(),
        )
    except requests.HTTPError as e:
        st.error(f"요청 실패: {e}")
    except Exception as e:
        st.error(f"오류: {e}")
