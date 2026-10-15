import os
import sys
import time
import asyncio
import edge_tts
import google.generativeai as genai

# ==========================================
# 1. KONFIGURASI
# ==========================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ISSUE_TEXT = os.getenv("ISSUE_TEXT", "Fenomena Sosial Umum")

# Setup library standar
genai.configure(api_key=GEMINI_API_KEY)

# MODEL INI 100% GRATIS DAN TERSEDIA UNTUK SEMUA AKUN
MODEL_NAME = "gemini-1.5-flash"

def log(msg):
    print(msg, flush=True)

def save_output(key, value):
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"{key}<<EOF\n{value}\nEOF\n")

# ==========================================
# 2. FUNGSI GENERATE NASKAH
# ==========================================
def generate_script_section(topic, section_prompt):
    prompt = f"""
Kamu adalah penulis naskah dokumenter YouTube profesional.
Topik: "{topic}"
Tugas: Tulis bagian ini dengan gaya bercerita menarik, kritis, bahasa Indonesia luwes. Target 600-800 kata.
Bagian: {section_prompt}
ATURAN: Jangan pakai kata pembuka "Halo penonton". Langsung ke inti. Gunakan analogi nyata di Indonesia. Output HANYA teks naskah, tanpa judul, tanpa markdown.
"""
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)
        text = response.text.strip()
        return text if len(text) > 100 else None
    except Exception as e:
        log(f"❌ Error: {str(e)[:100]}")
        return None

def generate_full_script(topic):
    log(f"📝 Menulis naskah (Model: {MODEL_NAME})...")
    
    sections = [
        "HOOK & INTRO: Fakta mengejutkan atau pertanyaan provokatif tentang topik ini.",
        "BAB 1: AKAR MASALAH. Pemicu sosial, ekonomi, atau psikologis di baliknya.",
        "BAB 2: DAMPAK NYATA. 2-3 contoh skenario nyata bagaimana ini mengubah kehidupan sehari-hari.",
        "BAB 3: SUDUT PANDANG KRITIS. Ironi atau sisi gelap yang sering diabaikan.",
        "KESIMPULAN & OUTRO: Refleksi mendalam dan pertanyaan penutup untuk kolom komentar."
    ]
    
    full_script = []
    for i, section in enumerate(sections):
        log(f"  Bagian {i+1}/5...")
        text = generate_script_section(topic, section)
        if text:
            full_script.append(text)
            log(f"  ✅ Selesai ({len(text)} karakter)")
        time.sleep(3) # Jeda aman agar tidak kena rate limit
        
    return "\n\n".join(full_script)

def generate_metadata(topic):
    log("🏷️ Membuat Metadata SEO...")
    prompt = f"""
Buat metadata SEO untuk video "{topic}" dalam format JSON valid:
{{
  "title": "Judul clickbait relevan, maks 70 karakter",
  "description": "Deskripsi 2 paragraf, akhiri ajakan subscribe",
  "tags": "tag1, tag2, tag3, tag4, tag5"
}}
Balas HANYA JSON, tanpa markdown.
"""
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)
        import json
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
    except:
        return {"title": topic, "description": "Dokumenter fenomena sosial.", "tags": "fenomena, sosial"}

# ==========================================
# 3. FUNGSI TEXT-TO-SPEECH
# ==========================================
async def generate_audio(text, output_file):
    log("🎙️ Membuat audio (Suara: id-ID-ArdiNeural)...")
    tts = edge_tts.Communicate(text, "id-ID-ArdiNeural")
    await tts.save(output_file)
    log("✅ Audio berhasil!")

# ==========================================
# 4. ALUR UTAMA
# ==========================================
def main():
    log("🚀 Memulai Sabda YouTube Bot...")
    
    if not GEMINI_API_KEY:
        save_output("RESULT", "❌ GEMINI_API_KEY tidak ada di Secrets!")
        sys.exit(1)
        
    topic = ISSUE_TEXT.strip()
    
    # 1. Naskah
    full_script = generate_full_script(topic)
    if not full_script or len(full_script) < 500:
        save_output("RESULT", "❌ Gagal membuat naskah (terlalu pendek).")
        sys.exit(1)
        
    with open("naskah.txt", "w", encoding="utf-8") as f:
        f.write(full_script)
        
    # 2. Metadata
    metadata = generate_metadata(topic)
    with open("metadata.txt", "w", encoding="utf-8") as f:
        f.write(f"JUDUL: {metadata['title']}\n\nDESKRIPSI:\n{metadata['description']}\n\nTAGS:\n{metadata['tags']}")
        
    # 3. Audio
    try:
        asyncio.run(generate_audio(full_script, "audio.mp3"))
    except Exception as e:
        save_output("RESULT", f"❌ Gagal audio: {e}")
        sys.exit(1)
        
    log("🎉 SELESAI!")
    save_output("RESULT", "✅ **Berhasil!**\nFile siap download:\n- `naskah.txt`\n- `audio.mp3`\n- `metadata.txt`")

if __name__ == "__main__":
    main()
