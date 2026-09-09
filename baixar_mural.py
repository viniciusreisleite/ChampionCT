import os, sys, json, time, re
import requests
from playwright.sync_api import sync_playwright
import yt_dlp

TARGET = 12
USER = "championct_"
DATA_JSON = "data.json"
COOKIES = "cookies.txt"

# Shortcodes ou URLs explicitamente fixados para ignorar sumariamente
SHORTCODES_FIXADOS = {
    "DalHQ6aRQor",  # Vídeo "Há 3 anos escolhemos..."
    "DVTXFY1jRa9",  # Fixado institucional 2
    "DSqRcsEDsaY"   # Fixado institucional 3
}

def baixar_foto(url, destino):
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.content) > 3000:
            with open(destino, "wb") as f:
                f.write(r.content)
            return True
    except Exception:
        pass
    return False

def extrair_code(url):
    m = re.search(r'/(?:p|reel|tv)/([^/?#&]+)', url)
    return m.group(1) if m else ""

def run():
    print(f"=== BAIXANDO EXCLUSIVAMENTE RECENTES CRONOLÓGICOS DE @{USER} ===")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        page = context.new_page()

        # 1. Acessa o feed principal
        print(f"Acessando feed de @{USER}...")
        page.goto(f"https://www.instagram.com/{USER}/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)
        
        candidatos_urls = []
        for _ in range(40):
            links = page.query_selector_all('a[href*="/p/"], a[href*="/reel/"]')
            for l in links:
                h = l.get_attribute("href")
                if h:
                    code = extrair_code(h)
                    if code and code not in SHORTCODES_FIXADOS:
                        # Detecta visualmente se o elemento tem pino caso haja outro fixado novo
                        card_html = l.inner_html().lower()
                        if "pin" in card_html or "fixado" in card_html:
                            continue
                        
                        full_url = f"https://www.instagram.com/{USER}/reel/{code}/" if "/reel/" in h else f"https://www.instagram.com/{USER}/p/{code}/"
                        if full_url not in candidatos_urls:
                            candidatos_urls.append(full_url)

            if len(candidatos_urls) >= 30:
                break
            page.evaluate("window.scrollBy(0, 1200)")
            page.wait_for_timeout(600)

        print(f"Total de posts filtrados (sem fixados): {len(candidatos_urls)}")

        dados_finais = []
        slot = 1

        for url in candidatos_urls:
            if slot > TARGET:
                break

            code = extrair_code(url)
            print(f"\n[{slot}/{TARGET}] Processando: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)

            # Valida autor para não puxar feed pessoal
            autor_header = page.query_selector("header")
            if autor_header:
                txt = autor_header.inner_text().lower()
                if "treinadorjhon" in txt and USER not in txt:
                    print("  -> Post exclusivo do perfil pessoal detectado. Pulando...")
                    continue

            caption = ""
            meta_tag = page.query_selector('meta[property="og:title"]')
            if meta_tag:
                caption = meta_tag.get_attribute("content") or ""

            # Verificação extra de texto para evitar posts fixados institucionais
            if "há 3 anos" in caption.lower() or "be the 1%" in caption.lower() and "fase da champion" in caption.lower():
                print("  -> Post institucional/fixado detectado por legenda. Pulando...")
                continue

            sucesso = False
            arquivo_destino = None
            tipo = "image"

            # 1. Tenta como vídeo
            if "/reel/" in url or page.query_selector("article video"):
                nome_base = f"media_{slot}"
                ydl_opts = {
                    'outtmpl': f'{nome_base}.%(ext)s',
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    'socket_timeout': 15,
                    'retries': 2,
                    'quiet': True,
                    'overwrites': True
                }
                if os.path.exists(COOKIES):
                    ydl_opts['cookiefile'] = COOKIES
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    for ext in [".mp4", ".mkv", ".webm"]:
                        arq_check = f"{nome_base}{ext}"
                        if os.path.exists(arq_check) and os.path.getsize(arq_check) > 10000:
                            arquivo_destino = arq_check
                            tipo = "video"
                            sucesso = True
                            break
                except Exception:
                    sucesso = False

            # 2. Tenta como imagem HD
            if not sucesso:
                tipo = "image"
                arquivo_destino = f"media_{slot}.jpg"
                img_url = None

                imgs = page.query_selector_all('article img, main img')
                for im in imgs:
                    srcset = im.get_attribute("srcset")
                    if srcset:
                        cands = [s.strip().split(" ")[0] for s in srcset.split(",")]
                        if cands:
                            img_url = cands[-1]
                            break
                    src = im.get_attribute("src")
                    if src and "scontent" in src:
                        img_url = src
                        break

                if not img_url:
                    og_img = page.query_selector('meta[property="og:image"]')
                    if og_img:
                        img_url = og_img.get_attribute("content")

                if img_url and baixar_foto(img_url, arquivo_destino):
                    sucesso = True

            if sucesso and arquivo_destino and os.path.exists(arquivo_destino):
                print(f"  -> Salvo slot {slot}: {arquivo_destino} ({tipo})")
                dados_finais.append({
                    "id": code,
                    "url": url,
                    "caption": caption,
                    "tipo": tipo,
                    "arquivo": arquivo_destino,
                    "badge": "CHAMPION CT",
                    "cor": "#ff1744",
                    "perfil": USER
                })
                slot += 1

        browser.close()

    # Salva json
    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(dados_finais, f, indent=2, ensure_ascii=False)

    print(f"\nFinalizado! Total de {len(dados_finais)} posts novos salvos (zero posts fixados).")

if __name__ == "__main__":
    run()

