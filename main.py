import os
import re
import sys
import json
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

# ==========================================
# 1. KONFIGURASI & ENVIRONMENT VARIABLES
# ==========================================
PINTEREST_TOKEN = os.getenv("PINTEREST_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ISSUE_TEXT = os.getenv("ISSUE_TEXT", "")

# Peta Kategori ke Board ID Pinterest (Fallback ke BOARD_DEFAULT jika kosong)
CATEGORY_BOARDS = {
    "fashion": os.getenv("BOARD_FASHION", os.getenv("BOARD_DEFAULT")),
    "dekorasi": os.getenv("BOARD_DEKO", os.getenv("BOARD_DEFAULT")),
    "gadget": os.getenv("BOARD_GADGET", os.getenv("BOARD_DEFAULT")),
    "kecantikan": os.getenv("BOARD_BEAUTY", os.getenv("BOARD_DEFAULT")),
    "rumah": os.getenv("BOARD_RUMAH", os.getenv("BOARD_DEFAULT")),
    "lainnya": os.getenv("BOARD_DEFAULT"),
}

# User-Agent agar tidak langsung diblokir sebagai bot oleh Shopee
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

# ==========================================
# 2. FUNGSI BANTU (HELPERS)
# ==========================================
def log(msg):
    """Mencetak pesan ke console GitHub Actions."""
    print(msg, flush=True)

def save_output(key, value):
    """Menyimpan output untuk digunakan oleh step selanjutnya di GitHub Actions."""
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"{key}<<EOF\n{value}\nEOF\n")

def extract_url(text):
    """Mengekstrak URL pertama yang ditemukan dalam teks."""
    match = re.search(r'https?://\S+', text or "")
    if match:
        # Bersihkan karakter tanda baca di akhir URL
        return match.group(0).rstrip('.,)>\'\"')
    return None

def fetch_shopee_metadata(url):
    """Mengambil judul, gambar, dan deskripsi dari halaman Shopee."""
    try:
        response = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Ambil dari Open Graph meta tags (standar terbaik)
        def get_meta(prop):
            tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
            return tag.get("content", "").strip() if tag else ""
        
        title = get_meta("og:title")
        image = get_meta("og:image")
        desc = get_meta("og:description")
        
        # Fallback jika og:title kosong
        if not title and soup.title and soup.title.string:
            title = soup.title.string.strip()
            
        return title, image, desc
    except Exception as e:
        log(f"⚠️ Gagal mengambil metadata langsung: {e}")
        return None, None, None

def validate_image_strict(image_url):
    """
    VALIDASI KETAT: Memastikan URL gambar benar-benar valid dan dapat diakses.
    Jika gagal, proses HARUS dibatalkan.
    """
    if not image_url or not image_url.startswith('http'):
        return False, "URL gambar kosong atau tidak valid formatnya."
    
    try:
        # Gunakan HEAD request untuk cek header tanpa mendownload seluruh gambar (hemat resource)
        response = requests.head(image_url, headers=HEADERS, allow_redirects=True, timeout=15)
        
        if response.status_code != 200:
            return False, f"Server gambar mengembalikan status error: {response.status_code}"
        
        content_type = response.headers.get('Content-Type', '').lower()
        if not content_type.startswith('image/'):
            return False, f"File bukan gambar (Content-Type: {content_type})"
        
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) < 5000:
            return False, f"Ukuran file terlalu kecil ({content_length} bytes), kemungkinan gambar rusak/kosong."
        
        return True, "OK"
    except requests.exceptions.Timeout:
        return False, "Timeout: Server gambar tidak merespons dalam waktu 15 detik."
    except requests.exceptions.ConnectionError:
        return False, "Connection Error: Tidak dapat terhubung ke server gambar."
    except Exception as e:
        return False, f"Error tidak terduga saat validasi gambar: {str(e)}"

def generate_ai_content(title, desc):
    """Menggunakan Google Gemini untuk membuat konten Pinterest yang menarik."""
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    prompt = f"""
Kamu adalah ahli copywriter dan spesialis SEO untuk Pinterest, menargetkan pasar Indonesia.
Tugasmu adalah membuat konten promosi untuk produk berikut agar orang ingin segera checkout.

Nama Produk: "{title}"
Deskripsi Tambahan: "{desc[:300] if desc else 'Tidak ada'}"

Aturan Konten:
1. Gaya bahasa: Kasual, hangat, seperti rekomendasi teman dekat. Gunakan emoji secukupnya (maksimal 3).
2. JANGAN sebut harga spesifik atau klaim berlebihan (misal: "terbaik di dunia").
3. Deskripsi harus menyebutkan 1-2 manfaat nyata produk.
4. Akhiri deskripsi dengan Call-to-Action (CTA) yang jelas, misal: "Klik link buat checkout ya!"
5. Sertakan 4-5 hashtag relevan (contoh: #RacunShopee #ShopeeFinds #RekomendasiProduk).

Kembalikan HASIL SAJA dalam format JSON yang valid. JANGAN gunakan markdown (```json), JANGAN ada teks lain di luar JSON.
Format JSON yang diminta:
{{
  "title": "Judul menarik, maks 90 karakter",
  "description": "Deskripsi persuasif, maks 400 karakter",
  "hashtags": "#Hashtag1 #Hashtag2 #Hashtag3",
  "category": "pilih SATU: fashion, dekorasi, gadget, kecantikan, rumah, lainnya"
}}
"""
    try:
        response = model.generate_content(prompt)
        # Bersihkan output dari kemungkinan markdown block
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
    except Exception as e:
        raise Exception(f"Gagal generate konten AI: {str(e)}")

def post_to_pinterest(board_id, title, description, link, image_url):
    """Mengirim data Pin ke Pinterest API v5."""
    url = "https://api.pinterest.com/v5/pins"
    headers = {
        "Authorization": f"Bearer {PINTEREST_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "board_id": board_id,
        "title": title[:100],  # Pinterest membatasi judul maks 100 karakter
        "description": description,
        "link": link,
        "media_source": {
            "source_type": "image_url",
            "url": image_url
        }
    }
    
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    
    if response.status_code == 201:
        pin_id = response.json().get("id", "unknown")
        return True, pin_id
    else:
        return False, response.text

# ==========================================
# 3. ALUR UTAMA (MAIN EXECUTION)
# ==========================================
def main():
    log("🚀 Memulai Sabda Pinterest Bot...")
    
    # Langkah 1: Ekstrak Link
    link = extract_url(ISSUE_TEXT)
    if not link:
        log("❌ FATAL: Tidak ada link URL yang ditemukan di Issue.")
        save_output("RESULT", "❌ **Proses Dibatalkan**\n\nAlasan: Tidak ada link Shopee yang valid di dalam Issue. Pastikan Anda menyalin link dengan benar.")
        sys.exit(1)
    
    log(f"🔗 Link Produk: {link}")
    
    # Langkah 2: Ambil Metadata
    title, image_url, desc = fetch_shopee_metadata(link)
    
    if not title:
        log("❌ FATAL: Gagal mengambil judul produk dari link.")
        save_output("RESULT", "❌ **Proses Dibatalkan**\n\nAlasan: Link tidak mengarah ke halaman produk Shopee yang valid, atau halaman tersebut diblokir.")
        sys.exit(1)
        
    log(f"📦 Judul Ditemukan: {title[:60]}...")
    
    # Langkah 3: VALIDASI GAMBAR KETAT (Sesuai Permintaan)
    if not image_url:
        log("❌ FATAL: URL gambar tidak ditemukan di metadata halaman.")
        save_output("RESULT", "❌ **Proses Dibatalkan**\n\nAlasan: Tidak dapat menemukan URL gambar produk. Shopee mungkin mengubah struktur halamannya.")
        sys.exit(1)
        
    log(f"🖼️  URL Gambar Ditemukan: {image_url[:60]}...")
    
    is_valid, reason = validate_image_strict(image_url)
    if not is_valid:
        log(f"❌ FATAL: Validasi gambar gagal - {reason}")
        save_output("RESULT", 
            f"❌ **Proses Dibatalkan**\n\n"
            f"**Alasan:** URL gambar ditemukan, tetapi gagal divalidasi.\n"
            f"**Detail:** `{reason}`\n"
            f"**URL Gambar:** `{image_url}`\n\n"
            f"**Solusi:**\n"
            f"1. Shopee mungkin memblokir akses dari server cloud GitHub.\n"
            f"2. Coba gunakan link produk Shopee yang berbeda.\n"
            f"3. Atau, balas Issue ini dengan menempelkan URL gambar langsung.")
        sys.exit(1)
        
    log("✅ Validasi gambar BERHASIL!")
    
    # Langkah 4: Generate Konten AI
    log("🧠 Meminta AI membuat konten...")
    try:
        ai_content = generate_ai_content(title, desc)
    except Exception as e:
        log(f"❌ FATAL: Error AI - {str(e)}")
        save_output("RESULT", f"❌ **Proses Dibatalkan**\n\nAlasan: Gagal menghubungi AI (Gemini).\nDetail: `{str(e)[:200]}`")
        sys.exit(1)
        
    category = str(ai_content.get("category", "lainnya")).lower().strip()
    board_id = CATEGORY_BOARDS.get(category, CATEGORY_BOARDS["lainnya"])
    
    if not board_id:
        log("❌ FATAL: BOARD_DEFAULT tidak diatur di GitHub Secrets.")
        save_output("RESULT", "❌ **Proses Dibatalkan**\n\nAlasan: Konfigurasi `BOARD_DEFAULT` kosong di GitHub Secrets. Hubungi admin.")
        sys.exit(1)
        
    log(f"🏷️  Kategori: {category} | Board ID: {board_id}")
    
    full_description = f"{ai_content['description']}\n\n{ai_content.get('hashtags', '')}\n\n🛒 **Link Pembelian:** {link}"
    
    # Langkah 5: Posting ke Pinterest
    log("📌 Mengirim ke Pinterest API...")
    success, info = post_to_pinterest(board_id, ai_content["title"], full_description, link, image_url)
    
    if success:
        log("✅ BERHASIL DIPROSES!")
        save_output("RESULT", 
            f"✅ **Berhasil Tayang di Pinterest!**\n\n"
            f"**{ai_content['title']}**\n"
            f"_Kategori: {category.capitalize()}_\n\n"
            f"🔎 [Lihat Pin di Pinterest](https://pinterest.com/pin/{info})")
    else:
        log(f"❌ FATAL: Pinterest API Menolak - {info}")
        save_output("RESULT", 
            f"❌ **Proses Dibatalkan**\n\n"
            f"**Alasan:** Pinterest API menolak permintaan.\n"
            f"**Detail:**\n```\n{info[:500]}\n```\n\n"
            f"**Kemungkinan Penyebab:**\n"
            f"1. `PINTEREST_TOKEN` sudah kedaluwarsa (buat ulang di Pinterest Developers).\n"
            f"2. `BOARD_ID` salah atau Anda tidak punya akses ke board tersebut.\n"
            f"3. Pinterest memblokir URL gambar tersebut.")
        sys.exit(1)

if __name__ == "__main__":
    main()