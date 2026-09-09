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
    print(f"=== BAIXANDO RECENTES (IGNORANDO FIXADOS) DE @{USER} ===")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        page = context.new_page()

        url_perfil = f"https://www.instagram.com/{USER}/?hl=pt-br"
        print(f"Acessando: {url_perfil}")
        page.goto(url_perfil, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)
        
        urls_limpas = []
        for _ in range(18):
            # Busca cards de links dentro do feed
            links = page.query_selector_all('article a[href*="/p/"], article a[href*="/reel/"], main a[href*="/p/"], main a[href*="/reel/"]')
            for l in links:
                h = l.get_attribute("href")
                if not h:
                    continue

                # DETECÇÃO DE POST FIXADO (PIN):
                # Verifica se dentro do link ou do elemento pai existe indicador de fixado
                is_pinned = False
                pinned_el = l.query_selector('svg[aria-label*="Fixado"], svg[aria-label*="Pinned"], title:text("Fixado"), title:text("Pinned")')
                if not pinned_el:
                    # Checa o nó ancestral próximo (container da miniatura)
                    parent = l.evaluate_handle("el => el.closest('div')")
                    if parent:
                        chk = parent.as_element().query_selector('svg[aria-label*="Fixado"], svg[aria-label*="Pinned"]')
                        if chk:
                            is_pinned = True
                else:
                    is_pinned = True

                if is_pinned:
                    continue

                m = re.search(r'/(p|reel)/([^/?#&]+)', h)
                if m:
                    tipo_rota = m.group(1)
                    code = m.group(2)
                    url_post = f"https://www.instagram.com/{USER}/{tipo_rota}/{code}/"
                    if url_post not in urls_limpas:
                        urls_limpas.append(url_post)

            if len(urls_limpas) >= 20:
                break
            page.evaluate("window.scrollBy(0, 1000)")
            page.wait_for_timeout(600)

        print(f"Total de posts recentes (sem fixados): {len(urls_limpas)}")

        dados_finais = []
        slot = 1

        for url in urls_limpas:
            if slot > TARGET:
                break

            print(f"\n[{slot}/{TARGET}] Processando recente: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)

            # Filtro para evitar perfil pessoal se for colab com autor externo exclusivo
            autor_header = page.query_selector("header")
            if autor_header:
                txt_header = autor_header.inner_text().lower()
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

            # 1. Vídeo
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

            # 2. Imagem HD
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

    print(f"\nFinalizado! Total de {len(dados_finais)} posts recentes sem fixados.")

if __name__ == "__main__":
    run()
