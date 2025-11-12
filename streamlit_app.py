# streamlit_app.py
import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="Nuna Tools",
    page_icon="🎛️",
    layout="wide",
    menu_items={
        "Get Help": "https://docs.streamlit.io/",
        "Report a bug": "https://github.com/streamlit/streamlit/issues",
        "About": "Nuna Tools — small utilities that make your day easier."
    },
)

# ====== Tiny CSS for nicer cards ======
st.markdown(
    """
    <style>
    .hero {
        padding: 1.25rem 1.25rem 0.25rem 1.25rem;
        border-radius: 18px;
        background: linear-gradient(135deg, #111827, #1f2937);
        color: #f9fafb !important;
        box-shadow: 0 12px 30px rgba(2,6,23,.25);
    }
    .muted { color: #cbd5e1; }
    .card {
        border-radius: 16px;
        padding: 18px;
        border: 1px solid rgba(2,6,23,.08);
        background: #ffffff;
        transition: all .18s ease-in-out;
        box-shadow: 0 6px 16px rgba(2,6,23,.06);
    }
    .card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 28px rgba(2,6,23,.12);
        border-color: rgba(2,6,23,.18);
    }
    .pill {
        display: inline-block;
        padding: 6px 10px;
        font-size: 12px;
        border-radius: 999px;
        background: #eef2ff;
        color: #3730a3;
        border: 1px solid #c7d2fe;
        margin-right: 6px;
    }
    .small { font-size: 13px; color:#64748b; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ====== Hero ======
with st.container():
    st.markdown(
        """
        <div class="hero">
          <h1 style="margin:0 0 .25rem 0;">🎛️ Nuna Tools</h1>
          <p class="muted" style="margin:.25rem 0 0 0;">
            Toolkit ringan untuk kerja harianmu — generator link & penerjemah subtitle.
          </p>
          <div style="margin-top:.75rem;">
            <span class="pill">Streamlit</span>
            <span class="pill">Utilities</span>
            <span class="pill">Fast & Simple</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")

# ====== Cards / Navigation ======
c1, c2, c3 = st.columns([1, 1, 1])

with c1:
    st.markdown("### 🔗 Universal Link Generator")
    st.markdown(
        """
        <div class="card">
          <p style="margin:.25rem 0 1rem 0;">
            Buat HTML link download/streaming rapi per episode dengan opsi
            pemendek ouo.io dan pengaturan server & resolusi yang fleksibel.
          </p>
        """,
        unsafe_allow_html=True,
    )
    # page_link tersedia di Streamlit >= 1.30; fallback ke markdown link
    if hasattr(st, "page_link"):
        st.page_link("pages/1_Universal_Link_Generator.py", label="Buka Link Generator →", icon="➡️")
    else:
        st.markdown("[Buka Link Generator →](pages/1_Universal_Link_Generator.py)")
    st.markdown('<p class="small" style="margin-top:.5rem;">File: <code>pages/1_Universal_Link_Generator.py</code></p></div>', unsafe_allow_html=True)

with c2:
    st.markdown("### 🎬 Subtitle Translator")
    st.markdown(
        """
        <div class="card">
          <p style="margin:.25rem 0 1rem 0;">
            Terjemahkan file <code>.srt</code> via API kompatibel OpenAI/DeepSeek.
            Mendukung resume, checkpoint, delay, dan mode terjemah per blok/baris.
          </p>
        """,
        unsafe_allow_html=True,
    )
    if hasattr(st, "page_link"):
        st.page_link("pages/2_Subtitle_Translator.py", label="Buka Subtitle Translator →", icon="➡️")
    else:
        st.markdown("[Buka Subtitle Translator →](pages/2_Subtitle_Translator.py)")
    st.markdown('<p class="small" style="margin-top:.5rem;">File: <code>pages/2_Subtitle_Translator.py</code></p></div>', unsafe_allow_html=True)

with c3:
    st.markdown("### ⚙️ Status & Tips")
    st.markdown(
        f"""
        <div class="card">
          <ul style="margin:.25rem 0 0 1rem; color:#334155;">
            <li>Gunakan <b>Secrets</b> untuk API Key (Streamlit Cloud → Settings → Secrets).</li>
            <li>Jika rate limit, naikkan <i>delay</i> atau kecilkan <i>concurrency</i>.</li>
            <li>Multi-page: tambah file baru ke folder <code>pages/</code>.</li>
          </ul>
          <p class="small" style="margin-top:.75rem;">
            Server time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")
st.divider()

# ====== Footer ======
left, right = st.columns([3, 1])
with left:
    st.markdown(
        """
        <span class="small">
        © Nuna Tools — Built with Streamlit.  
        Jika tampilan tidak berubah setelah update, gunakan tombol "Rerun" di pojok kanan atas.
        </span>
        """,
        unsafe_allow_html=True,
    )
with right:
    st.markdown(
        '<div style="text-align:right;" class="small">v1.0</div>',
        unsafe_allow_html=True,
    )
