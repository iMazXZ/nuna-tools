# pages/2_Subtitle_Translator.py
import streamlit as st
import io, time, math, srt, re
from datetime import timedelta
from typing import List, Tuple
try:
    from openai import OpenAI
except Exception as e:
    st.stop()

st.set_page_config(page_title="Subtitle Translator (DeepSeek/OpenAI)", layout="wide")
st.title("🎬 Subtitle Translator (DeepSeek / OpenAI-compatible)")

# === Utilities: mask/unmask tags ===
HTML_TAG_RE = re.compile(r'<[^>]+>')
ASS_TAG_RE  = re.compile(r'\{\\[^}]*\}')

def mask_tags(text: str) -> Tuple[str, List[str], List[str]]:
    html_tags, ass_tags = [], []
    def _mh(m): html_tags.append(m.group(0)); return f'[[HTML_TAG_{len(html_tags)-1}]]'
    def _ma(m): ass_tags.append(m.group(0));  return f'[[ASS_TAG_{len(ass_tags)-1}]]'
    text = HTML_TAG_RE.sub(_mh, text)
    text = ASS_TAG_RE.sub(_ma, text)
    return text, html_tags, ass_tags

def unmask_tags(text: str, html_tags: List[str], ass_tags: List[str]) -> str:
    for i, t in enumerate(html_tags): text = text.replace(f'[[HTML_TAG_{i}]]', t)
    for i, t in enumerate(ass_tags):  text = text.replace(f'[[ASS_TAG_{i}]]', t)
    return text

# === API helpers ===
def is_rate_limit(err: Exception) -> bool:
    s = str(err).lower()
    return "rate limit" in s or "429" in s

def chat_translate(client, model: str, system: str, user: str) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role":"system","content":system},{"role":"user","content":user}],
        temperature=0.0,
    )
    return resp.choices[0].message.content.strip()

def translate_block(client, model: str, lines: List[str], src: str, tgt: str, max_retries=6, backoff=2.0) -> List[str]:
    masked_lines, html_store, ass_store = [], [], []
    for line in lines:
        m, h, a = mask_tags(line)
        masked_lines.append(m); html_store.append(h); ass_store.append(a)

    # line-indexed prompt
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
                if not raw.startswith("<<LINE"): continue
                try:
                    head, content = raw.split(">>", 1)
                    idx = int(head.replace("<<LINE","").strip())
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

# === Sidebar settings ===
st.sidebar.header("API Settings")
api_key = st.sidebar.text_input("API Key", type="password", help="DeepSeek/OpenAI-compatible API key")
base_url = st.sidebar.text_input("Base URL", value="https://api.deepseek.com", help="e.g., https://api.deepseek.com or https://api.deepseek.com/v1")
model = st.sidebar.text_input("Model", value="deepseek-chat")

st.sidebar.header("Translate Settings")
src_lang = st.sidebar.text_input("Source language", value="en")
tgt_lang = st.sidebar.text_input("Target language", value="id")
delay = st.sidebar.slider("Delay per block (seconds)", min_value=0.0, max_value=2.0, value=0.2, step=0.1)
checkpoint_every = st.sidebar.number_input("Checkpoint every N blocks", min_value=1, value=25, step=1)
max_retries = st.sidebar.number_input("Max retries (rate limit)", min_value=0, value=6, step=1)
backoff = st.sidebar.number_input("Backoff base (seconds)", min_value=0.5, value=2.0, step=0.5)

st.sidebar.header("Mode")
mode = st.sidebar.radio("Granularity", options=["block","line"], index=0, help="block = 1 API call per subtitle block; line = per line")

st.sidebar.header("Upload / Resume")
uploaded = st.file_uploader("Upload .srt", type=["srt"])
resume_existing = st.sidebar.checkbox("Resume from previous output", value=False)
resume_file = st.sidebar.file_uploader("Upload previous output (optional)", type=["srt"], help="If provided and resume is on, already translated blocks will be reused")

# === Main area ===
if uploaded is not None and api_key:
    st.success("File uploaded. Ready to translate.")
    content = uploaded.read().decode("utf-8", errors="ignore")
    src_subs = list(srt.parse(content))
    total = len(src_subs)
    st.info(f"Parsed {total} blocks")

    # Optional resume
    existing_subs = None
    if resume_existing and resume_file is not None:
        try:
            existing_text = resume_file.read().decode("utf-8", errors="ignore")
            existing_subs = list(srt.parse(existing_text))
            if len(existing_subs) != total:
                st.warning("Resume file block count differs from input; resume will be ignored.")
                existing_subs = None
        except Exception as e:
            st.error(f"Failed to parse resume file: {e}")
            existing_subs = None

    # Translate button
    if st.button("🚀 Translate now"):
        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
        except Exception as e:
            st.error(f"Failed to init client: {e}")
            st.stop()

        progress = st.progress(0)
        status = st.empty()

        translated_blocks = []
        start_time = time.time()

        for idx, sub in enumerate(src_subs, start=1):
            # resume reuse
            if existing_subs:
                ex = existing_subs[idx-1]
                if ex.content.strip() and ex.content.strip() != sub.content.strip():
                    translated_blocks.append(ex)
                    pct = int(idx/total*100)
                    elapsed = time.time() - start_time
                    status.text(f"Resumed {idx}/{total} • elapsed {timedelta(seconds=int(elapsed))}")
                    progress.progress(pct)
                    continue

            lines = sub.content.split("\n")
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
                        # retries
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
                    out_lines = translate_block(client, model, lines, src_lang, tgt_lang, max_retries=max_retries, backoff=backoff)
            except Exception as e:
                # keep original on failure
                out_lines = lines
                st.warning(f"[{idx}] error: {e} — keeping original")

            translated_blocks.append(srt.Subtitle(index=sub.index, start=sub.start, end=sub.end, content="\n".join(out_lines)))

            # progress & checkpoint
            pct = int(idx/total*100)
            elapsed = time.time() - start_time
            eta = (elapsed/idx)*(total-idx) if idx>0 else 0
            status.text(f"{idx}/{total} • {pct}% • ETA {timedelta(seconds=int(eta))}")
            progress.progress(pct)

            if checkpoint_every and (idx % checkpoint_every == 0 or idx == total):
                partial = srt.compose(translated_blocks + src_subs[idx:])
                st.session_state["last_partial"] = partial  # keep in session

            time.sleep(delay)

        final_text = srt.compose(translated_blocks)
        st.success("Done translating!")
        st.download_button("⬇️ Download translated .srt", data=final_text.encode("utf-8"), file_name="translated.id.srt", mime="text/plain")
        if "last_partial" in st.session_state:
            with st.expander("Download last checkpoint (partial)"):
                st.download_button("⬇️ Download partial .srt", data=st.session_state["last_partial"].encode("utf-8"), file_name="partial.id.srt", mime="text/plain")
else:
    st.info("Upload .srt dan isi API Key untuk memulai.")
