# pages/2_Subtitle_Translator.py
import io
import time
import math
import re
from datetime import timedelta
from typing import List, Tuple

import streamlit as st
import srt
import pandas as pd

# Try import OpenAI client
try:
    from openai import OpenAI
except Exception as e:
    st.error("Paket `openai` belum terpasang. Tambahkan ke requirements.txt lalu redeploy.")
    st.stop()

# ───────────────────────────────────────────────────────────────────────────────
# Page config
st.set_page_config(page_title="Subtitle Translator", layout="wide")
st.title("🎬 Subtitle Translator (DeepSeek / OpenAI-compatible)")

# ───────────────────────────────────────────────────────────────────────────────
# Helpers: mask/unmask HTML & ASS tags, rate limit detection
HTML_TAG_RE = re.compile(r"<[^>]+>")
ASS_TAG_RE = re.compile(r"\{\\[^}]*\}")

def mask_tags(text: str) -> Tuple[str, List[str], List[str]]:
    html_tags, ass_tags = [], []

    def _mh(m):
        html_tags.append(m.group(0))
        return f"[[HTML_TAG_{len(html_tags)-1}]]"

    def _ma(m):
        ass_tags.append(m.group(0))
        return f"[[ASS_TAG_{len(ass_tags)-1}]]"

    text = HTML_TAG_RE.sub(_mh, text)
    text = ASS_TAG_RE.sub(_ma, text)
    return text, html_tags, ass_tags

def unmask_tags(text: str, html_tags: List[str], ass_tags: List[str]) -> str:
    for i, t in enumerate(html_tags):
        text = text.replace(f"[[HTML_TAG_{i}]]", t)
    for i, t in enumerate(ass_tags):
        text = text.replace(f"[[ASS_TAG_{i}]]", t)
    return text

def is_rate_limit(err: Exception) -> bool:
    s = str(err).lower()
    return "rate limit" in s or "429" in s

# ───────────────────────────────────────────────────────────────────────────────
# OpenAI-compatible call
def chat_translate(client, model: str, system: str, user: str) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.0,
    )
    return resp.choices[0].message.content.strip()

def translate_block(
    client,
    model: str,
    lines: List[str],
    src: str,
    tgt: str,
    max_retries=6,
    backoff=2.0,
) -> List[str]:
    """1 request per subtitle block; jaga jumlah & urutan baris."""
    masked_lines, html_store, ass_store = [], [], []
    for line in lines:
        m, h, a = mask_tags(line)
        masked_lines.append(m)
        html_store.append(h)
        ass_store.append(a)

    parts = [f"<<LINE {i}>> {masked_lines[i]}" for i in range(len(masked_lines))]
    prompt = "\n".join(parts)

    system = (
        "You are a professional subtitle translator.\n"
        "Translate exactly from the source language to the target language.\n"
        "Keep ALL placeholders like [[HTML_TAG_#]] and [[ASS_TAG_#]] unchanged.\n"
        "DO NOT reorder or merge lines. Return the same number of lines, each starting with '<<LINE i>> ' prefix unchanged.\n"
    )
    user = f"Source language: {src}\nTarget language: {tgt}\n\n{prompt}"

    attempt = 0
    while True:
        try:
            out = chat_translate(client, model, system, user)
            # parse back
            out_lines = [""] * len(lines)
            for raw in out.splitlines():
                raw = raw.strip()
                if not raw.startswith("<<LINE"):
                    continue
                try:
                    head, content = raw.split(">>", 1)
                    idx = int(head.replace("<<LINE", "").strip())
                    out_lines[idx] = content.lstrip()
                except Exception:
                    continue
            # unmask
            final = []
            for i, content in enumerate(out_lines):
                final.append(unmask_tags(content, html_store[i], ass_store[i]))
            return final
        except Exception as e:
            attempt += 1
            if attempt > max_retries or not is_rate_limit(e):
                raise
            time.sleep(backoff * (2 ** (attempt - 1)))

# ───────────────────────────────────────────────────────────────────────────────
# Sidebar: API Settings (pakai secrets bila tersedia)
st.sidebar.header("API Settings")

# Ambil dari secrets jika ada
secret_key = st.secrets.get("DEEPSEEK_API_KEY", "")
secret_base = st.secrets.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

use_secrets = st.sidebar.checkbox(
    "Use API key from Secrets",
    value=bool(secret_key),
    help="Jika dicentang dan secret tersedia, field API Key tidak perlu diisi manual."
)

api_key_input = st.sidebar.text_input(
    "API Key",
    value="" if use_secrets and secret_key else "",
    type="password",
    help="Kosongkan jika menggunakan Secrets."
)
base_url = st.sidebar.text_input(
    "Base URL",
    value=secret_base if (use_secrets and secret_base) else "https://api.deepseek.com",
    help="Contoh: https://api.deepseek.com atau https://api.deepseek.com/v1",
)
model = st.sidebar.text_input("Model", value="deepseek-chat")

effective_api_key = secret_key if (use_secrets and secret_key) else api_key_input

# Translate Settings
st.sidebar.header("Translate Settings")
src_lang = st.sidebar.text_input("Source language", value="en")
tgt_lang = st.sidebar.text_input("Target language", value="id")
delay = st.sidebar.slider("Delay per block (seconds)", 0.0, 2.0, 0.2, 0.1)
checkpoint_every = st.sidebar.number_input("Checkpoint every N blocks", 1, 9999, 25, 1)
max_retries = st.sidebar.number_input("Max retries (rate limit)", 0, 20, 6, 1)
backoff = st.sidebar.number_input("Backoff base (seconds)", 0.5, 30.0, 2.0, 0.5)

st.sidebar.header("Mode")
mode = st.sidebar.radio("Granularity", ["block", "line"], index=0, help="block = 1 request per subtitle block; line = per baris")

st.sidebar.header("Upload / Resume")
uploaded = st.file_uploader("Upload .srt", type=["srt"])
resume_existing = st.sidebar.checkbox("Resume from previous output", value=False)
resume_file = st.sidebar.file_uploader(
    "Upload previous output (optional)",
    type=["srt"],
    help="Jika diberikan dan jumlah blok cocok, blok yang sudah diterjemahkan akan dipakai ulang."
)

# ───────────────────────────────────────────────────────────────────────────────
# Parsing + optional pre-translate preview
if uploaded is not None:
    raw = uploaded.read().decode("utf-8", errors="ignore")
    src_subs = list(srt.parse(raw))
    total = len(src_subs)
    st.info(f"Parsed **{total}** subtitle blocks.")

    if st.checkbox("Tampilkan tabel original (pra-terjemah)", value=False):
        pre_rows = []
        for i, s in enumerate(src_subs, start=1):
            pre_rows.append({
                "No.": i,
                "From": str(s.start),
                "To": str(s.end),
                "Original Text": s.content.replace("\n", " "),
                "Translated Text": ""
            })
        st.dataframe(pd.DataFrame(pre_rows), use_container_width=True, hide_index=True)

    # Resume parsing
    existing_subs = None
    if resume_existing and resume_file is not None:
        try:
            prev = resume_file.read().decode("utf-8", errors="ignore")
            existing_subs = list(srt.parse(prev))
            if len(existing_subs) != total:
                st.warning("Resume file block count berbeda—resume diabaikan.")
                existing_subs = None
        except Exception as e:
            st.warning(f"Gagal parse resume file: {e}")
            existing_subs = None

    # Translate button
    if st.button("🚀 Translate now", type="primary"):
        if not effective_api_key:
            st.error("API Key tidak tersedia. Isi di sidebar atau gunakan Secrets.")
            st.stop()

        try:
            client = OpenAI(api_key=effective_api_key, base_url=base_url)
        except Exception as e:
            st.error(f"Gagal inisialisasi client: {e}")
            st.stop()

        progress = st.progress(0)
        status = st.empty()
        translated_blocks = []
        start_time = time.time()

        for idx, sub in enumerate(src_subs, start=1):
            # resume reuse
            if existing_subs:
                ex = existing_subs[idx - 1]
                if ex.content.strip() and ex.content.strip() != sub.content.strip():
                    translated_blocks.append(ex)
                    pct = int(idx / total * 100)
                    elapsed = time.time() - start_time
                    status.text(f"[resume] {idx}/{total} • elapsed {timedelta(seconds=int(elapsed))}")
                    progress.progress(pct)
                    continue

            lines = sub.content.split("\n")
            # translate
            try:
                if mode == "line":
                    out_lines = []
                    for line in lines:
                        m, h, a = mask_tags(line)
                        system = (
                            "You are a professional subtitle translator. "
                            "Translate user-provided text exactly from the source language to the target language. "
                            "Do NOT add or remove lines. Do NOT merge or split content. "
                            "The text may contain placeholders like [[HTML_TAG_0]] or [[ASS_TAG_0]]. "
                            "Leave placeholders exactly unchanged. Return ONLY the translated text."
                        )
                        user = f"Source language: {src_lang}\nTarget language: {tgt_lang}\n\nText:\n{m}"
                        attempts = 0
                        while True:
                            try:
                                res = chat_translate(client, model, system, user)
                                out_lines.append(unmask_tags(res, h, a))
                                break
                            except Exception as e:
                                attempts += 1
                                if attempts > max_retries or not is_rate_limit(e):
                                    raise
                                time.sleep(backoff * (2 ** (attempts - 1)))
                else:
                    out_lines = translate_block(
                        client, model, lines, src_lang, tgt_lang,
                        max_retries=max_retries, backoff=backoff
                    )
            except Exception as e:
                st.warning(f"[{idx}] error: {e} — blok dipertahankan (original).")
                out_lines = lines

            translated_blocks.append(
                srt.Subtitle(index=sub.index, start=sub.start, end=sub.end, content="\n".join(out_lines))
            )

            # progress + checkpoint
            pct = int(idx / total * 100)
            elapsed = time.time() - start_time
            eta = (elapsed / idx) * (total - idx) if idx else 0
            status.text(f"{idx}/{total} • {pct}% • ETA {timedelta(seconds=int(eta))}")
            progress.progress(pct)

            if checkpoint_every and (idx % checkpoint_every == 0 or idx == total):
                partial = srt.compose(translated_blocks + src_subs[idx:])
                st.session_state["last_partial"] = partial

            time.sleep(delay)

        final_text = srt.compose(translated_blocks)

        # ── Side-by-side table preview & CSV download
        def _fmt_td(td):
            # td adalah datetime.timedelta
            total_ms = int(td.total_seconds() * 1000)
            h = total_ms // 3600000
            m = (total_ms % 3600000) // 60000
            s_ = (total_ms % 60000) // 1000
            ms_ = total_ms % 1000
            return f"{h:02d}:{m:02d}:{s_:02d},{ms_:03d}"

        rows = []
        for i, (src, dst) in enumerate(zip(src_subs, translated_blocks), start=1):
            rows.append({
                "No.": i,
                "From": _fmt_td(src.start),
                "To": _fmt_td(src.end),
                "Original Text": src.content.replace("\n", " "),
                "Translated Text": dst.content.replace("\n", " "),
            })

        st.success("Selesai diterjemahkan!")
        with st.expander("📋 Preview Tabel (Original vs Translated)", expanded=True):
            cfg = {
                "No.": st.column_config.NumberColumn(width="small"),
                "From": st.column_config.TextColumn(width=120),
                "To": st.column_config.TextColumn(width=120),
                "Original Text": st.column_config.TextColumn(width="medium"),
                "Translated Text": st.column_config.TextColumn(width="medium"),
            }
            height = st.slider("Tinggi tampilan (px)", 300, 1200, 420, 20)
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, column_config=cfg, height=height)

            st.download_button(
                "⬇️ Download CSV",
                data=pd.DataFrame(rows).to_csv(index=False).encode("utf-8"),
                file_name="subtitle_pair.csv",
                mime="text/csv"
            )

        # ── Final SRT download + checkpoint
        st.download_button(
            "⬇️ Download translated .srt",
            data=final_text.encode("utf-8"),
            file_name="translated.id.srt",
            mime="text/plain"
        )
        if "last_partial" in st.session_state:
            with st.expander("Download last checkpoint (partial)"):
                st.download_button(
                    "⬇️ Download partial .srt",
                    data=st.session_state["last_partial"].encode("utf-8"),
                    file_name="partial.id.srt",
                    mime="text/plain"
                )
else:
    st.info("Upload file .srt untuk mulai menerjemahkan.")
