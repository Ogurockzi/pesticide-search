# pesticide_search.py — iOS Safari에서도 무조건 2x2, HTML 폼 + URL 파라미터 방식
import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from io import BytesIO
import streamlit.components.v1 as components

st.set_page_config(page_title="현별이 농약 검색기", layout="centered")

# ---------- 스타일: 여백 최소 + 2x2 고정 ----------
st.markdown("""
<style>
.main .block-container{padding-top:.25rem;padding-bottom:.5rem;max-width:860px}
.app-title{font-weight:800;font-size:1.06rem;letter-spacing:-.02em;margin:.05rem 0 .4rem}
.form-card{border:1px solid #eee;border-radius:10px;padding:.5rem .55rem;background:#fff}

/* 순수 HTML 2x2 그리드 — 브라우저/플랫폼과 무관하게 항상 2열 */
#mini-form{
  display:grid;
  grid-template-columns:repeat(2, minmax(0,1fr));
  grid-auto-rows:auto;
  gap:.42rem .56rem;
}
.mini-field{display:flex;flex-direction:column}
.mini-label{font-size:.86rem;font-weight:600;margin:0 0 .18rem 2px;letter-spacing:-.01em}
.mini-input{
  height:34px; padding:4px 8px; font-size:14px; border:1px solid #dcdcdc;
  border-radius:8px; outline:none; background:#fff;
}
.mini-input:focus{border-color:#9aa8ff; box-shadow:0 0 0 2px rgba(90,90,255,.12)}
#go-btn{
  grid-column:1 / span 1; height:34px; padding:4px 10px; font-size:.86rem;
  border-radius:9px; border:1px solid #ddd; background:#f7f7f7; cursor:pointer;
}
#go-btn:active{transform:translateY(1px)}
@media (max-width:360px){
  .app-title{font-size:.98rem}
  .mini-input{height:32px; font-size:13.5px}
  #go-btn{height:32px; font-size:.84rem}
}
.stDataFrame{margin-top:.4rem}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="app-title">🌿 현별이 농약 검색기</div>', unsafe_allow_html=True)

API_URL = "https://psis.rda.go.kr/openApi/service.do"
API_KEY = st.secrets["PSIS_API_KEY"]  # Streamlit Cloud Secrets에 PSIS_API_KEY 등록돼 있어야 함

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
    st.dataframe(df, use_container_width=True)

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="검색결과")
    st.download_button(
        "📥 엑셀 다운로드",
        data=buf.getvalue(),
        file_name="농약검색결과.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# ---------- URL 쿼리 읽기(버전별 호환) ----------
brand_q = crop_q = item_q = comp_q = ""
submitted = False
try:
    qp = st.query_params  # 신버전
    brand_q = qp.get("brand", "")
    crop_q  = qp.get("crop", "")
    item_q  = qp.get("item", "")
    comp_q  = qp.get("company", "")
    submitted = qp.get("go", "") == "1"
except Exception:
    qp = st.experimental_get_query_params()  # 구버전
    brand_q = qp.get("brand", [""])[0] if qp.get("brand") else ""
    crop_q  = qp.get("crop",  [""])[0] if qp.get("crop")  else ""
    item_q  = qp.get("item",  [""])[0] if qp.get("item")  else ""
    comp_q  = qp.get("company", [""])[0] if qp.get("company") else ""
    submitted = (qp.get("go", [""])[0] == "1") if qp.get("go") else False

# ---------- 순수 HTML 2×2 폼(값 채우기는 JS가 URL에서 읽어서 넣음) ----------
components.html("""
<div class="form-card">
  <div id="mini-form">
    <div class="mini-field">
      <span class="mini-label">상표명</span>
      <input class="mini-input" id="brand" inputmode="text" />
    </div>
    <div class="mini-field">
      <span class="mini-label">작물명</span>
      <input class="mini-input" id="crop" inputmode="text" />
    </div>
    <div class="mini-field">
      <span class="mini-label">품목명</span>
      <input class="mini-input" id="item" inputmode="text" />
    </div>
    <div class="mini-field">
      <span class="mini-label">회사명</span>
      <input class="mini-input" id="company" inputmode="text" />
    </div>
    <button id="go-btn">🔎 검색</button>
  </div>
</div>
<script>
  function getParam(name){
    const params = new URLSearchParams(window.parent.location.search);
    return params.get(name) || "";
  }
  // URL 값 → 입력창 채우기
  document.getElementById('brand').value   = getParam('brand');
  document.getElementById('crop').value    = getParam('crop');
  document.getElementById('item').value    = getParam('item');
  document.getElementById('company').value = getParam('company');

  function submitForm(){
    const b = encodeURIComponent(document.getElementById('brand').value.trim());
    const c = encodeURIComponent(document.getElementById('crop').value.trim());
    const i = encodeURIComponent(document.getElementById('item').value.trim());
    const m = encodeURIComponent(document.getElementById('company').value.trim());
    const base = window.parent.location.origin + window.parent.location.pathname;
    const qs = "?brand=" + b + "&crop=" + c + "&item=" + i + "&company=" + m + "&go=1";
    window.parent.location.href = base + qs; // 새로고침 + 파라미터 반영
  }
  document.getElementById('go-btn').addEventListener('click', function(e){ e.preventDefault(); submitForm(); });
  document.querySelectorAll('#mini-form input').forEach(function(el){
    el.addEventListener('keydown', function(ev){
      if(ev.key === 'Enter'){ ev.preventDefault(); submitForm(); }
    });
  });
</script>
""", height=230, scrolling=False)

# ---------- 제출되었으면 검색 실행 ----------
if submitted or any([brand_q, crop_q, item_q, comp_q]):
    try:
        run_search(brand_q.strip(), crop_q.strip(), item_q.strip(), comp_q.strip())
    except requests.HTTPError as e:
        st.error(f"요청 실패: {e}")
    except Exception as e:
        st.error(f"오류: {e}")
