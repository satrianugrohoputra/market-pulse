# patch_app.py - Run once to update app.py result rendering block
import re

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the spinner line and replace everything from it to end of report display
old_marker = "with st.spinner(f\"\U0001f50d Mencari ulasan relevan via RAG dari"
new_block = '''with st.spinner(f"\U0001f50d Memeriksa relevansi & mencari ulasan dari '{dataset_name}'..."):
                result = aic.run_ai_consultant(
                    df=df_for_rag,
                    query=ai_query,
                    api_key=api_key,
                    model_id=selected_model_id,
                    sentiment_filter=sentiment_filter,
                    dataset_name=dataset_name,
                )

            # \u2500\u2500 Cek: Apakah query diblokir Pre-flight Guardrail? \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
            if result.get("blocked"):
                st.markdown("---")
                st.error(result["block_reason"])
                st.info(
                    "\U0001f4a1 **Tip**: AI Consultant ini dirancang khusus untuk menganalisis data "
                    "ulasan e-commerce. Pastikan pertanyaan Anda berkaitan dengan ulasan produk, "
                    "rating, sentimen pelanggan, atau performa toko."
                )
            else:
                report = result["report"]
                retrieved_count = result["retrieved_count"]
                guard = result["guard_result"]
                grounding_score = guard["score"]
                used_dataset = result.get("dataset_name", "")

                # \u2500\u2500 Status Grounding Badge \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
                st.markdown("---")
                st.caption(f"\U0001f5c2\ufe0f Sumber data RAG: **{used_dataset}** | Filter: **{sentiment_filter}** | Model: `{selected_model_id}`")
                badge_col1, badge_col2, badge_col3 = st.columns(3)
                with badge_col1:
                    st.metric("\U0001f4c4 Ulasan Dianalisis (RAG)", f"{retrieved_count} ulasan")
                with badge_col2:
                    score_pct = f"{grounding_score * 100:.1f}%"
                    st.metric("\U0001f6e1\ufe0f Grounding Score", score_pct, help="Seberapa besar laporan ini bersumber dari data ulasan Anda.")
                with badge_col3:
                    if guard["grounded"]:
                        st.success("\u2705 **Grounded in Data**")
                    else:
                        st.warning("\u26a0\ufe0f **Jawaban Umum / Kurang Data**")

                # \u2500\u2500 Tampilkan Hallucination Warning Jika Perlu \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
                if not guard["grounded"] and guard["warning"]:
                    st.warning(guard["warning"])

                # \u2500\u2500 Tampilkan Laporan Gemini \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
                st.markdown("### \U0001f4cb Laporan AI Business Insight")
                st.markdown(report)
'''

# Regex pattern: match from 'with st.spinner' to end of 'st.markdown(report)'
pattern = r'with st\.spinner\(f"[^\n]+Mencari ulasan relevan via RAG.*?st\.markdown\(report\)'
match = re.search(pattern, content, flags=re.DOTALL)

if match:
    indent = '            '
    indented_new_block = '\n'.join(
        indent + line if line.strip() else line
        for line in new_block.splitlines()
    )
    content = content[:match.start()] + indented_new_block + content[match.end():]
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("SUCCESS: app.py updated.")
else:
    print("FAIL: Pattern not found. Searching for spinner line...")
    idx = content.find("Mencari ulasan relevan via RAG")
    if idx >= 0:
        print("Spinner found at char:", idx)
        print("Context:", content[idx-10:idx+200])
    else:
        print("Spinner line not found either.")
