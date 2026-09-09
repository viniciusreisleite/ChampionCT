import os, sys, json, time, re
import requests
from playwright.sync_api import sync_playwright
import yt_dlp

TARGET = 12
USER = "championct_"
DATA_JSON = "data.json"
COOKIES = "cookies.txt"

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

def run():
    print(f"=== BAIXANDO EXCLUSIVAMENTE DO PERFIL @{USER} ===")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        page = context.new_page()

        url_perfil = f"https://www.instagram.com/{USER}/?hl=pt-br"
        print(f"Acessando: {url_perfil}")
        page.goto(url_perfil, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)
        
        # Coleta estritamente os links das publicações
        urls_limpas = []
        for _ in range(16):
            links = page.query_selector_all('article a[href*="/p/"], article a[href*="/reel/"], main a[href*="/p/"], main a[href*="/reel/"]')
            for l in links:
                h = l.get_attribute("href")
                if h:
                    m = re.search(r'/(p|reel)/([^/?#&]+)', h)
                    if m:
                        tipo_rota = m.group(1)
                        code = m.group(2)
                        # Força a URL oficial pelo perfil da academia
                        url_post = f"https://www.instagram.com/{USER}/{tipo_rota}/{code}/"
                        if url_post not in urls_limpas:
                            urls_limpas.append(url_post)
            if len(urls_limpas) >= 20:
                break
            page.evaluate("window.scrollBy(0, 1000)")
            page.wait_for_timeout(600)

        print(f"Total de posts encontrados no feed: {len(urls_limpas)}")

        dados_finais = []
        slot = 1

        for url in urls_limpas:
            if slot > TARGET:
                break

            print(f"\n[{slot}/{TARGET}] Processando: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)

            # Verifica autor exibido na pagina do post
            autor_header = page.query_selector("header")
            if autor_header:
                txt_header = autor_header.inner_text().lower()
                # Se o post pertencer explicitamente a outra conta pessoal, pula
                if "treinadorjhon" in txt_header and USER not in txt_header:
                    print("  -> Post exclusivo do perfil pessoal detectado. Pulando...")
                    continue

            caption = ""
            meta_tag = page.query_selector('meta[property="og:title"]')
            if meta_tag:
                caption = meta_tag.get_attribute("content") or ""

            sucesso = False
            arquivo_destino = None
            tipo = "image"

            # Tenta video se for reel ou tiver tag video
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

            # Se nao for video, baixa foto em HD
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
                    "id": url.split("/")[-2],
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

    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(dados_finais, f, indent=2, ensure_ascii=False)

    print(f"\nFinalizado! Total de {len(dados_finais)} posts exclusivos de @{USER} salvos.")

if __name__ == "__main__":
    run()
