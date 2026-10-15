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

# Setup Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Model terbaru yang STABIL dan GRATIS (2025)
MODEL_NAME = "gemini-2.0-flash"

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
Kamu adalah penulis naskah dokumenter YouTube profesional (gaya video essay mendalam).
Topik Video: "{topic}"

Tugasmu: Tulis bagian naskah berikut dengan gaya bercerita yang menarik, kritis, dan menggunakan bahasa Indonesia yang luwes (tidak kaku seperti robot).
Panjang target bagian ini: sekitar 600-800 kata.

Bagian yang harus ditulis:
{section_prompt}

ATURAN PENTING:
- Jangan gunakan kata pembuka seperti "Halo penonton" atau "Di video kali ini". Langsung masuk ke inti cerita.
- Gunakan analogi atau contoh nyata yang relate dengan kehidupan di Indonesia.
- Jangan tulis instruksi visual (seperti [cut to...]), tulis murni teks yang akan dibaca narator.
- Output HANYA teks naskah, tanpa judul bagian, tanpa markdown.
"""
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)
        text = response.text.strip()
        if len(text) < 100:
            log(f"⚠️ Respons terlalu pendek ({len(text)} char)")
            return None
        return text
    except Exception as e:
        log(f"❌ Error: {str(e)[:150]}")
        return None

def generate_full_script(topic):
    log(f"📝 Mulai menulis naskah dengan model: {MODEL_NAME}")
    log("⏳ Proses ini butuh waktu 2-3 menit...")
    
    sections = [
        "HOOK & INTRO: Mulai dengan pertanyaan provokatif atau fakta mengejutkan tentang topik ini. Bangun rasa penasaran penonton mengapa fenomena ini terjadi.",
        "BAB 1: AKAR MASALAH. Jelaskan bagaimana fenomena ini dimulai. Apa pemicu sosial, ekonomi, atau psikologis di baliknya?",
        "BAB 2: DAMPAK NYATA. Berikan 2-3 contoh atau skenario nyata bagaimana fenomena ini merusak atau mengubah kehidupan sehari-hari masyarakat.",
        "BAB 3: SUDUT PANDANG KRITIS. Bahas ironi atau sisi gelap yang sering diabaikan orang. Mengapa masyarakat membiarkan ini terjadi?",
        "KESIMPULAN & OUTRO: Berikan refleksi mendalam dan pertanyaan penutup yang membuat penonton berpikir lama setelah video selesai. Akhiri dengan ajakan berdiskusi di kolom komentar."
    ]
    
    full_script = []
    for i, section in enumerate(sections):
        log(f"  Menulis Bagian {i+1}/5...")
        text = generate_script_section(topic, section)
        if text:
            full_script.append(text)
            log(f"  ✅ Bagian {i+1} selesai ({len(text)} karakter)")
        else:
            log(f"  ❌ Bagian {i+1} gagal, coba lagi...")
            text = generate_script_section(topic, section)
            if text:
                full_script.append(text)
        time.sleep(2)
        
    return "\n\n".join(full_script)

def generate_metadata(topic, script_snippet):
    log("🏷️ Membuat Metadata SEO...")
    prompt = f"""
Berdasarkan naskah YouTube tentang "{topic}", buat metadata SEO dalam format JSON valid:
{{
  "title": "Judul video yang clickbait tapi relevan, maks 70 karakter",
  "description": "Deskripsi video 2 paragraf yang mengandung kata kunci, akhiri dengan ajakan subscribe.",
  "tags": "tag1, tag2, tag3, tag4, tag5"
}}
Balas HANYA JSON, tanpa markdown.
"""
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        response = model.generate_content(prompt)
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        import json
        return json.loads(clean_text)
    except Exception as e:
        log(f"⚠️ Metadata gagal: {e}, pakai default")
        return {
            "title": f"Mengupas Tuntas: {topic}",
            "description": "Video dokumenter mendalam tentang fenomena sosial.",
            "tags": "fenomena sosial, dokumenter, fakta unik"
        }

# ==========================================
# 3. FUNGSI TEXT-TO-SPEECH (EDGE-TTS)
# ==========================================
async def generate_audio(text, output_file):
    log("🎙️ Mengubah naskah menjadi audio (Suara Narator)...")
    voice = "id-ID-ArdiNeural" 
    tts = edge_tts.Communicate(text, voice)
    await tts.save(output_file)
    log("✅ Audio berhasil dibuat!")

# ==========================================
# 4. ALUR UTAMA
# ==========================================
def main():
    log("🚀 Memulai Sabda YouTube Bot...")
    
    if not GEMINI_API_KEY:
        save_output("RESULT", " GEMINI_API_KEY tidak ditemukan di Secrets!")
        sys.exit(1)
        
    topic = ISSUE_TEXT.strip()
    log(f"🎯 Topik: {topic}")
    
    # 1. Generate Naskah
    full_script = generate_full_script(topic)
    
    if len(full_script) < 500:
        save_output("RESULT", f"❌ Naskah terlalu pendek ({len(full_script)} karakter). API mungkin bermasalah.")
        sys.exit(1)
        
    # Simpan Naskah
    with open("naskah.txt", "w", encoding="utf-8") as f:
        f.write(full_script)
    log(f"💾 Naskah disimpan ({len(full_script)} karakter)")
    
    # 2. Generate Metadata
    metadata = generate_metadata(topic, full_script[:500])
    metadata_text = f"JUDUL: {metadata['title']}\n\nDESKRIPSI:\n{metadata['description']}\n\nTAGS:\n{metadata['tags']}"
    with open("metadata.txt", "w", encoding="utf-8") as f:
        f.write(metadata_text)
    log("💾 Metadata disimpan")
    
    # 3. Generate Audio
    try:
        asyncio.run(generate_audio(full_script, "audio.mp3"))
    except Exception as e:
        log(f"❌ Gagal membuat audio: {e}")
        save_output("RESULT", f"❌ Gagal membuat audio: {e}")
        sys.exit(1)
        
    log("🎉 PROSES SELESAI!")
    save_output("RESULT", "✅ **Berhasil!**\n\nFile siap download:\n- `naskah.txt`\n- `audio.mp3`\n- `metadata.txt`")

if __name__ == "__main__":
    main()
