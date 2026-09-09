import os, sys, json, time, re, shutil
import requests
from playwright.sync_api import sync_playwright
import yt_dlp

TARGET = 12
USER = "championct_"
DATA_JSON = "data.json"
COOKIES_FILE = "cookies.txt"

SHORTCODES_FIXADOS = {"DalHQ6aRQor", "DVTXFY1jRa9", "DSqRcsEDsaY"}

def carregar_cookies_playwright(context):
    if not os.path.exists(COOKIES_FILE):
        return
    cookies_pw = []
    with open(COOKIES_FILE, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.strip().split("\t")
            if len(parts) >= 7:
                cookies_pw.append({
                    "domain": parts[0] if parts[0].startswith(".") else f".{parts[0]}",
                    "path": parts[2],
                    "secure": parts[3].lower() == "true",
                    "expires": int(parts[4]) if parts[4].isdigit() else int(time.time()) + 86400,
                    "name": parts[5],
                    "value": parts[6]
                })
    if cookies_pw:
        try:
            context.add_cookies(cookies_pw)
            print("  [AUTH] Cookies injetados com sucesso.")
        except Exception as e:
            print(f"  [AUTH AVISO] Erro ao carregar cookies: {e}")

def extrair_code(url):
    m = re.search(r'/(?:p|reel|tv)/([^/?#&]+)', url)
    return m.group(1) if m else ""

def baixar_foto_real(url, destino):
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        if r.status_code == 200 and len(r.content) > 25000: # Exige > 25KB para ser foto HD real
            with open(destino, "wb") as f:
                f.write(r.content)
            return True
    except Exception:
        pass
    return False

def run():
    print(f"=== BAIXANDO 12 POSTS REAIS E RECENTES DE @{USER} ===")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        carregar_cookies_playwright(context)
        page = context.new_page()

        print(f"Acessando perfil de @{USER}...")
        page.goto(f"https://www.instagram.com/{USER}/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        # Fecha popup de login se houver
        try:
            btn_close = page.query_selector('svg[aria-label="Fechar"], div[role="dialog"] button')
            if btn_close:
                btn_close.click()
        except:
            pass

        # Coleta URLs rolando com persistência
        candidatos = []
        for tentativa in range(25):
            links = page.query_selector_all('a[href*="/p/"], a[href*="/reel/"]')
            for l in links:
                h = l.get_attribute("href")
                if not h:
                    continue
                code = extrair_code(h)
                if code and code not in SHORTCODES_FIXADOS:
                    full = f"https://www.instagram.com/{USER}/reel/{code}/" if "/reel/" in h else f"https://www.instagram.com/{USER}/p/{code}/"
                    if full not in candidatos:
                        candidatos.append(full)
            if len(candidatos) >= 16:
                break
            page.evaluate("window.scrollBy(0, 1500)")
            page.wait_for_timeout(800)

        print(f"Posts cronológicos identificados: {len(candidatos)}")

        dados_finais = []
        slot = 1

        for url in candidatos:
            if slot > TARGET:
                break

            code = extrair_code(url)
            print(f"\n[{slot}/{TARGET}] Processando: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)

            # Valida autor
            autor_el = page.query_selector("header")
            if autor_el and "treinadorjhon" in autor_el.inner_text().lower() and USER not in autor_el.inner_text().lower():
                print("  -> Post exclusivo pessoal. Ignorando.")
                continue

            caption = ""
            meta_title = page.query_selector('meta[property="og:title"]')
            if meta_title:
                caption = meta_title.get_attribute("content") or ""

            sucesso = False
            nome_base = f"media_{slot}"
            arquivo_salvo = None
            tipo = "image"

            # 1. Tenta baixar como Vídeo com yt-dlp
            if "/reel/" in url or page.query_selector("article video"):
                ydl_opts = {
                    'outtmpl': f'{nome_base}.%(ext)s',
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    'socket_timeout': 15,
                    'retries': 2,
                    'quiet': True,
                    'overwrites': True
                }
                if os.path.exists(COOKIES_FILE):
                    ydl_opts['cookiefile'] = COOKIES_FILE
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    for ext in [".mp4", ".mkv", ".webm"]:
                        arq_c = f"{nome_base}{ext}"
                        if os.path.exists(arq_c) and os.path.getsize(arq_c) > 20000:
                            arquivo_salvo = arq_c
                            tipo = "video"
                            sucesso = True
                            break
                except Exception:
                    sucesso = False

            # 2. Se falhar ou for foto (/p/), extrai imagem em resolução real
            if not sucesso:
                tipo = "image"
                arquivo_salvo = f"{nome_base}.jpg"
                img_url = None

                # Pega a melhor imagem dentro do post
                imgs = page.query_selector_all('article img[srcset], main img[srcset]')
                for im in imgs:
                    ss = im.get_attribute("srcset")
                    if ss:
                        lista = [s.strip().split(" ")[0] for s in ss.split(",")]
                        if lista:
                            img_url = lista[-1] # Pega a última da lista (maior resolução)
                            break

                if not img_url:
                    meta_img = page.query_selector('meta[property="og:image"]')
                    if meta_img:
                        img_url = meta_img.get_attribute("content")

                if img_url and baixar_foto_real(img_url, arquivo_salvo):
                    sucesso = True
                else:
                    sucesso = False

            if sucesso and arquivo_salvo and os.path.exists(arquivo_salvo):
                tam_kb = os.path.getsize(arquivo_salvo) / 1024
                print(f"  -> Sucesso: {arquivo_salvo} ({tipo} - {tam_kb:.1f} KB)")
                dados_finais.append({
                    "id": code,
                    "url": url,
                    "caption": caption,
                    "tipo": tipo,
                    "arquivo": arquivo_salvo,
                    "badge": "CHAMPION CT",
                    "cor": "#ff1744",
                    "perfil": USER
                })
                slot += 1
            else:
                print(f"  -> Falha na captura do post {code}. Indo para o próximo...")

        browser.close()

    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(dados_finais, f, indent=2, ensure_ascii=False)

    print(f"\nConcluído! Total de {len(dados_finais)} mídias salvas com sucesso.")

if __name__ == "__main__":
    run()
