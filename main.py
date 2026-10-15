import os
import sys
import asyncio
import edge_tts

# ==========================================
# 1. KONFIGURASI
# ==========================================
ISSUE_TITLE = os.getenv("ISSUE_TITLE", "naskah")
ISSUE_BODY = os.getenv("ISSUE_BODY", "")

def log(msg):
    print(msg, flush=True)

def save_output(key, value):
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"{key}<<EOF\n{value}\nEOF\n")

# ==========================================
# 2. FUNGSI AUDIO GENERATOR
# ==========================================
async def generate_audio(text, output_file):
    log("🎙️ Mulai mengubah teks menjadi audio...")
    log(f"📝 Panjang teks: {len(text)} karakter")
    
    # Suara narator: Ardi (laki-laki) atau Gadis (perempuan)
    voice = "id-ID-ArdiNeural"
    
    # Bersihkan teks dari karakter aneh
    clean_text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    tts = edge_tts.Communicate(clean_text, voice)
    await tts.save(output_file)
    log("✅ Audio berhasil dibuat!")

# ==========================================
# 3. ALUR UTAMA
# ==========================================
def main():
    log("🚀 Memulai Sabda Audio Generator...")
    
    # Cek apakah ada naskah
    if not ISSUE_BODY or len(ISSUE_BODY.strip()) < 50:
        log("❌ FATAL: Isi Issue (Body) kosong atau terlalu pendek!")
        save_output("RESULT", "❌ **Gagal!**\n\nAlasan: Kamu tidak menempelkan naskah di kolom 'Write' (Body) Issue.\n\n**Cara pakai:**\n1. Title: nama file (contoh: Healing_Palsu)\n2. Body: paste seluruh naskah di sini\n3. Submit")
        sys.exit(1)
        
    # Nama file output berdasarkan Judul Issue
    safe_title = "".join(c for c in ISSUE_TITLE if c.isalnum() or c in (' ', '-', '_')).rstrip()
    output_filename = f"{safe_title}.mp3"
    
    log(f"📂 Nama file: {output_filename}")
    
    try:
        asyncio.run(generate_audio(ISSUE_BODY, output_filename))
    except Exception as e:
        log(f"❌ Gagal membuat audio: {e}")
        save_output("RESULT", f" **Gagal!**\n\nError: {e}")
        sys.exit(1)
        
    log("🎉 PROSES SELESAI!")
    save_output("RESULT", f"✅ **Berhasil!**\n\nFile audio `{output_filename}` siap didownload di tab Code.")

if __name__ == "__main__":
    main()
