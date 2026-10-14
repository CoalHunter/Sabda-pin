import os
import re
import sys
import json
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai

# ==========================================
# 1. KONFIGURASI
# ==========================================
PINTEREST_TOKEN = os.getenv("PINTEREST_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ISSUE_TEXT = os.getenv("ISSUE_TEXT", "")

CATEGORY_BOARDS = {
    "fashion": os.getenv("BOARD_FASHION", os.getenv("BOARD_DEFAULT")),
    "dekorasi": os.getenv("BOARD_DEKO", os.getenv("BOARD_DEFAULT")),
    "gadget": os.getenv("BOARD_GADGET", os.getenv("BOARD_DEFAULT")),
    "kecantikan": os.getenv("BOARD_BEAUTY", os.getenv("BOARD_DEFAULT")),
    "rumah": os.getenv("BOARD_RUMAH", os.getenv("BOARD_DEFAULT")),
    "lainnya": os.getenv("BOARD_DEFAULT"),
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Accept-Language": "id-ID,id;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

# ==========================================
# 2. FUNGSI BANTU
# ==========================================
def log(msg):
    print(msg, flush=True)

def save_output(key, value):
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as f:
            f.write(f"{key}<<EOF\n{value}\nEOF\n")

def extract_url(text):
    match = re.search(r'https?://\S+', text or "")
    if match:
        return match.group(0).rstrip('.,)>\'\"')
    return None

def parse_html_for_metadata(html):
    soup = BeautifulSoup(html, "html.parser")
    
    def get_meta(prop):
        tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        return tag.get("content", "").strip() if tag else ""
    
    title = get_meta("og:title")
    image = get_meta("og:image")
    desc = get_meta("og:description")
    
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()
    
    if not image:
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if "shopee" in src.lower() or "cf.shopee" in src:
                image = src
                break
    
    return title, image, desc

def fetch_direct(url):
    try:
        response = requests.get(url, headers=HEADERS, allow_redirects=True, timeout=20)
        response.raise_for_status()
        title, image, desc = parse_html_for_metadata(response.text)
        if title and image:
            return response.url, title, image, desc
    except Exception as e:
        log(f"⚠️ Akses langsung gagal: {e}")
    return url, None, None, None

def fetch_via_jina(url):
    try:
        jina_url = f"https://r.jina.ai/{url}"
        jina_headers = {
            "Accept": "text/html",
            "X-Return-Format": "html"
        }
        response = requests.get(jina_url, headers=jina_headers, timeout=30)
        response.raise_for_status()
        title, image, desc = parse_html_for_metadata(response.text)
        return title, image, desc
    except Exception as e:
        log(f"⚠️ Jina Reader gagal: {e}")
        return None, None, None

def validate_image_strict(image_url):
    if not image_url or not image_url.startswith('http'):
        return False, "URL gambar kosong atau tidak valid."
    
    try:
        response = requests.head(image_url, headers=HEADERS, allow_redirects=True, timeout=15)
        
        if response.status_code != 200:
            return False, f"Server gambar status: {response.status_code}"
        
        content_type = response.headers.get('Content-Type', '').lower()
        if not content_type.startswith('image/'):
            return False, f"Bukan gambar (Content-Type: {content_type})"
        
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) < 5000:
            return False, f"File terlalu kecil ({content_length} bytes)."
        
        return True, "OK"
    except Exception as e:
        return False, f"Error: {str(e)}"

def generate_ai_content_fallback(title, desc):
    """Generate konten dengan AI + fallback jika JSON gagal."""
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = f"""
Buat konten Pinterest untuk produk ini (pasar Indonesia):

Nama: "{title}"
Deskripsi: "{desc[:200] if desc else ''}"

Aturan:
- Judul maks 90 karakter, menarik, pakai emoji
- Deskripsi maks 400 karakter, sebut manfaat, akhiri "Klik link buat checkout ya!"
- Tambahkan 4 hashtag (#RacunShopee #ShopeeFinds dll)
- Tentukan kategori: fashion/dekorasi/gadget/kecantikan/rumah/lainnya

BALAS HANYA JSON, tanpa teks lain:
{{"title":"...","description":"...","hashtags":"...","category":"..."}}
"""
        response = model.generate_content(prompt)
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        
        # Coba parse JSON
        try:
            return json.loads(clean_text)
        except json.JSONDecodeError:
            log("⚠️ JSON parsing gagal, pakai fallback manual")
            # Fallback: buat konten manual dari judul
            return {
                "title": f"Racun Shopee: {title[:70]}",
                "description": f"Produk menarik: {title}. Kualitas bagus dan harga bersahabat. Klik link buat checkout ya!",
                "hashtags": "#RacunShopee #ShopeeFinds #RekomendasiProduk #BelanjaOnline",
                "category": "lainnya"
            }
    except Exception as e:
        log(f"️ AI error: {e}")
        # Fallback total jika AI gagal
        return {
            "title": f"Rekomendasi: {title[:70]}",
            "description": f"Produk menarik dari Shopee: {title}. Klik link untuk detail dan pembelian!",
            "hashtags": "#RacunShopee #ShopeeFinds #Rekomendasi",
            "category": "lainnya"
        }

def post_to_pinterest(board_id, title, description, link, image_url):
    url = "https://api.pinterest.com/v5/pins"
    headers = {
        "Authorization": f"Bearer {PINTEREST_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "board_id": board_id,
        "title": title[:100],
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
# 3. ALUR UTAMA
# ==========================================
def main():
    log("🚀 Memulai Sabda Pinterest Bot...")
    
    # Cek API key
    if not GEMINI_API_KEY:
        log(" FATAL: GEMINI_API_KEY tidak ada di Secrets!")
        save_output("RESULT", "❌ **Proses Dibatalkan**\n\nAlasan: `GEMINI_API_KEY` kosong di GitHub Secrets. Tambahkan di Settings > Secrets.")
        sys.exit(1)
    
    if not PINTEREST_TOKEN:
        log("❌ FATAL: PINTEREST_TOKEN tidak ada!")
        save_output("RESULT", "❌ **Proses Dibatalkan**\n\nAlasan: `PINTEREST_TOKEN` kosong di GitHub Secrets.")
        sys.exit(1)
    
    # Langkah 1: Ekstrak Link
    link = extract_url(ISSUE_TEXT)
    if not link:
        log("❌ FATAL: Tidak ada link di Issue.")
        save_output("RESULT", "❌ **Proses Dibatalkan**\n\nAlasan: Tidak ada link Shopee yang valid di Issue.")
        sys.exit(1)
    
    log(f"🔗 Link: {link}")
    
    # Langkah 2: Ambil Metadata
    final_url, title, image_url, desc = fetch_direct(link)
    
    if not title or not image_url:
        log("⚠️ Coba Jina Reader...")
        jina_title, jina_image, jina_desc = fetch_via_jina(link)
        title = title or jina_title
        image_url = image_url or jina_image
        desc = desc or jina_desc
    
    if not title:
        log("❌ FATAL: Gagal ambil judul.")
        save_output("RESULT", "❌ **Proses Dibatalkan**\n\nAlasan: Tidak bisa ambil judul produk.")
        sys.exit(1)
    
    if not image_url:
        log("❌ FATAL: Gagal ambil gambar.")
        save_output("RESULT", "❌ **Proses Dibatalkan**\n\nAlasan: Tidak bisa ambil gambar produk.")
        sys.exit(1)
    
    log(f" Judul: {title[:60]}...")
    log(f"🖼️ Gambar: {image_url[:60]}...")
    
    # Langkah 3: Validasi Gambar
    is_valid, reason = validate_image_strict(image_url)
    if not is_valid:
        log(f"❌ Validasi gambar gagal: {reason}")
        save_output("RESULT", f"❌ **Proses Dibatalkan**\n\n**Alasan:** Gambar tidak valid.\n**Detail:** `{reason}`")
        sys.exit(1)
    
    log("✅ Validasi gambar BERHASIL!")
    
    # Langkah 4: Generate AI (dengan fallback)
    log("🧠 Generate konten...")
    ai_content = generate_ai_content_fallback(title, desc)
    
    category = str(ai_content.get("category", "lainnya")).lower().strip()
    board_id = CATEGORY_BOARDS.get(category, CATEGORY_BOARDS["lainnya"])
    
    if not board_id:
        log("❌ FATAL: BOARD_DEFAULT kosong.")
        save_output("RESULT", "❌ **Proses Dibatalkan**\n\nAlasan: `BOARD_DEFAULT` kosong di Secrets.")
        sys.exit(1)
    
    log(f"️ Kategori: {category} | Board: {board_id}")
    
    full_description = f"{ai_content['description']}\n\n{ai_content.get('hashtags', '')}\n\n🛒 **Link:** {link}"
    
    # Langkah 5: Posting
    log("📌 Posting ke Pinterest...")
    success, info = post_to_pinterest(board_id, ai_content["title"], full_description, link, image_url)
    
    if success:
        log("✅ BERHASIL!")
        save_output("RESULT", 
            f"✅ **Berhasil Tayang di Pinterest!**\n\n"
            f"**{ai_content['title']}**\n"
            f"_Kategori: {category.capitalize()}_\n\n"
            f"🔎 [Lihat Pin](https://pinterest.com/pin/{info})")
    else:
        log(f"❌ Pinterest menolak: {info}")
        save_output("RESULT", 
            f"❌ **Proses Dibatalkan**\n\n"
            f"**Alasan:** Pinterest API menolak.\n"
            f"**Detail:**\n```\n{info[:500]}\n```")
        sys.exit(1)

if __name__ == "__main__":
    main()
