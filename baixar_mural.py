import os, sys, json, time, re, shutil
import requests
from playwright.sync_api import sync_playwright
import yt_dlp

# --- CONFIGURAÇÃO DE CONTAS ---
ACCOUNTS = [
    {"username": "championct_", "badge": "CENTRO DE TREINAMENTO", "color": "#ff1744"}
]

# Posts fixados do topo para ignorar
SHORTCODES_FIXADOS = {"DalHQ6aRQor", "DVTXFY1jRa9", "DSqRcsEDsaY"}

TARGET_TOTAL = 12
POSTS_PER_ACCOUNT = 12
DATA_JSON = "data.json"
COOKIES_FILE = "cookies.txt"

def extrair_shortcode(url):
    m = re.search(r'/(?:p|reel|tv)/([^/?#&]+)', url)
    return m.group(1) if m else url

def carregar_cache():
    if os.path.exists(DATA_JSON):
        try:
            with open(DATA_JSON, "r", encoding="utf-8") as f:
                dados = json.load(f)
                cache = {}
                for item in dados:
                    url = item.get("url") or item.get("link", "")
                    sc = extrair_shortcode(url)
                    if sc and sc not in SHORTCODES_FIXADOS:
                        cache[sc] = item
                return cache
        except Exception:
            return {}
    return {}

def baixar_imagem_hd(url, destino):
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        if r.status_code == 200 and len(r.content) > 10000:
            with open(destino, "wb") as f:
                f.write(r.content)
            return True
    except Exception:
        pass
    return False

def processar_mural():
    cache_local = carregar_cache()
    posts_a_manter = []
    
    print("=== INICIANDO VERIFICAÇÃO RÁPIDA (SEM FIXADOS) ===")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = context.new_page()

        for acc in ACCOUNTS:
            usr = acc["username"]
            badge = acc.get("badge", "")
            cor = acc.get("color", "#ff1744")
            print(f"\nChecando feed de @{usr}...")
            
            page.goto(f"https://www.instagram.com/{usr}/", wait_until="domcontentloaded", timeout=60000)
            urls_encontradas = []
            
            for _ in range(16):
                anchors = page.query_selector_all('a[href*="/p/"], a[href*="/reel/"]')
                for a in anchors:
                    href = a.get_attribute("href")
                    if href:
                        sc_check = extrair_shortcode(href)
                        # IGNORA FIXADOS
                        if sc_check in SHORTCODES_FIXADOS:
                            continue
                        clean = href.split("?")[0].strip("/")
                        full = f"https://www.instagram.com/{clean}/"
                        if full not in urls_encontradas:
                            urls_encontradas.append(full)
                if len(urls_encontradas) >= POSTS_PER_ACCOUNT + 6:
                    break
                page.evaluate("window.scrollBy(0, 1000)")
                page.wait_for_timeout(500)

            candidatos = urls_encontradas[:POSTS_PER_ACCOUNT + 6]
            print(f"Posts no feed (sem fixados): {len(candidatos)} identificados.")

            for url in candidatos:
                if len(posts_a_manter) >= TARGET_TOTAL:
                    break

                sc = extrair_shortcode(url)
                if sc in SHORTCODES_FIXADOS:
                    continue
                
                # CHECAGEM DE CACHE
                if sc in cache_local:
                    item_cache = cache_local[sc]
                    arquivo_salvo = item_cache.get("media") or item_cache.get("arquivo")
                    if arquivo_salvo and os.path.exists(arquivo_salvo):
                        print(f"  [CACHE OK] {sc} ({arquivo_salvo})")
                        posts_a_manter.append(item_cache)
                        continue

                # Se nao esta no cache, baixa apenas o novo post
                print(f"  [NOVO POST] Baixando: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1200)

                caption = ""
                meta_tag = page.query_selector('meta[property="og:title"]')
                if meta_tag:
                    caption = meta_tag.get_attribute("content") or ""

                post_temp_id = f"temp_{sc}"
                tipo = "image"
                arquivo_final = f"{post_temp_id}.jpg"

                # Testa se eh video
                video_elem = page.query_selector("article video, main video")
                if video_elem or "/reel/" in url:
                    ydl_opts = {
                        'outtmpl': f'{post_temp_id}.%(ext)s',
                        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best',
                        'socket_timeout': 15,
                        'retries': 3,
                        'fragment_retries': 3,
                        'quiet': True,
                        'overwrites': True
                    }
                    if os.path.exists(COOKIES_FILE):
                        ydl_opts['cookiefile'] = COOKIES_FILE
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([url])
                        for ext in [".mp4", ".mkv", ".webm"]:
                            if os.path.exists(f"{post_temp_id}{ext}"):
                                arquivo_final = f"{post_temp_id}{ext}"
                                tipo = "video"
                                break
                    except Exception:
                        tipo = "image"

                if tipo != "video":
                    img_url = None
                    imgs = page.query_selector_all('article img[srcset], main img[srcset]')
                    for im in imgs:
                        srcset = im.get_attribute("srcset")
                        if srcset:
                            cand_img = [s.strip().split(" ")[0] for s in srcset.split(",")]
                            if cand_img:
                                img_url = cand_img[-1]
                                break
                    if not img_url:
                        meta_img = page.query_selector('meta[property="og:image"]')
                        if meta_img:
                            img_url = meta_img.get_attribute("content")

                    if img_url:
                        baixar_imagem_hd(img_url, arquivo_final)

                if os.path.exists(arquivo_final) and os.path.getsize(arquivo_final) > 5000:
                    # Chaves completas para compatibilidade total com qualquer index.html
                    posts_a_manter.append({
                        "id": sc,
                        "url": url,
                        "caption": caption,
                        "text": caption,
                        "type": tipo,
                        "tipo": tipo,
                        "media": arquivo_final,
                        "media_file": arquivo_final,
                        "video_file": arquivo_final,
                        "arquivo": arquivo_final,
                        "badge": badge,
                        "cor": cor,
                        "perfil": usr
                    })

        browser.close()

    # ORGANIZAÇÃO FINAL DOS TOP 12 SLOTS
    posts_finais = posts_a_manter[:TARGET_TOTAL]
    dados_json_novo = []

    print("\nOrganizando arquivos de 1 a 12...")
    arquivos_preservados = set()

    for idx, item in enumerate(posts_finais, start=1):
        ext = os.path.splitext(item["media"])[1]
        nome_slot = f"media_{idx}{ext}"
        
        origem = item["media"]
        if origem != nome_slot:
            if os.path.exists(nome_slot):
                os.remove(nome_slot)
            shutil.move(origem, nome_slot)
            
        item["media"] = nome_slot
        item["media_file"] = nome_slot
        item["video_file"] = nome_slot
        item["arquivo"] = nome_slot

        arquivos_preservados.add(nome_slot)
        dados_json_novo.append(item)

    # Limpeza de arquivos velhos
    for arq in os.listdir("."):
        if (arq.startswith("media_") or arq.startswith("temp_")) and (arq.endswith(".jpg") or arq.endswith(".mp4") or arq.endswith(".png")):
            if arq not in arquivos_preservados:
                try:
                    os.remove(arq)
                except Exception:
                    pass

    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(dados_json_novo, f, indent=2, ensure_ascii=False)

    print(f"Concluído! {len(dados_json_novo)} mídias prontas e sincronizadas.")

if __name__ == "__main__":
    processar_mural()
