import os, sys, json, time, re
import requests
from playwright.sync_api import sync_playwright
import yt_dlp

TARGET_TOTAL = 12
USER = "championct_"
DATA_JSON = "data.json"
COOKIES_FILE = "cookies.txt"
SHORTCODES_FIXADOS = {"DalHQ6aRQor", "DVTXFY1jRa9", "DSqRcsEDsaY"}

def extrair_shortcode(url):
    m = re.search(r'/(?:p|reel|tv)/([^/?#&]+)', url)
    return m.group(1) if m else url

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
    print(f"=== COLETANDO FEED E REELS PARA COMPLETAR 12 SLOTS ===")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = context.new_page()

        candidatos = []

        # 1. Coleta do Feed Principal
        print(f"1. Acessando feed de @{USER}...")
        page.goto(f"https://www.instagram.com/{USER}/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

        for _ in range(12):
            for a in page.query_selector_all('a[href*="/p/"], a[href*="/reel/"]'):
                href = a.get_attribute("href")
                if href:
                    sc = extrair_shortcode(href)
                    if sc in SHORTCODES_FIXADOS:
                        continue
                    full = f"https://www.instagram.com/{href.split('?')[0].strip('/')}/"
                    if full not in candidatos:
                        candidatos.append(full)
            page.evaluate("window.scrollBy(0, 1000)")
            page.wait_for_timeout(400)

        # 2. Se não bateu candidatos suficientes, coleta da aba /reels/
        if len(candidatos) < TARGET_TOTAL + 4:
            print(f"2. Acessando aba /reels/ para buscar posts mais antigos...")
            page.goto(f"https://www.instagram.com/{USER}/reels/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
            for _ in range(15):
                for a in page.query_selector_all('a[href*="/reel/"]'):
                    href = a.get_attribute("href")
                    if href:
                        sc = extrair_shortcode(href)
                        if sc in SHORTCODES_FIXADOS:
                            continue
                        full = f"https://www.instagram.com/{href.split('?')[0].strip('/')}/"
                        if full not in candidatos:
                            candidatos.append(full)
                page.evaluate("window.scrollBy(0, 1200)")
                page.wait_for_timeout(400)

        print(f"Total de URLs candidatas disponíveis: {len(candidatos)}")

        dados_finais = []
        slot_atual = 1

        for url in candidatos:
            if slot_atual > TARGET_TOTAL:
                break

            sc = extrair_shortcode(url)
            arquivo_existente = None
            tipo_existente = "video"
            
            # Checa se este slot ja esta salvo no disco com integridade
            for ext, tp in [(".mp4", "video"), (".jpg", "image")]:
                teste = f"media_{slot_atual}{ext}"
                if os.path.exists(teste) and os.path.getsize(teste) > 10000:
                    arquivo_existente = teste
                    tipo_existente = tp
                    break

            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1000)

            caption = ""
            meta_tag = page.query_selector('meta[property="og:title"]')
            if meta_tag:
                caption = meta_tag.get_attribute("content") or ""

            # Se ja temos o arquivo local no slot 1 a 9, apenas confirma os dados
            if arquivo_existente and slot_atual <= 9:
                print(f"  [SLOT {slot_atual} JÁ EXISTE] {arquivo_existente}")
                dados_finais.append({
                    "id": sc,
                    "url": url,
                    "caption": caption,
                    "text": caption,
                    "type": tipo_existente,
                    "tipo": tipo_existente,
                    "media": arquivo_existente,
                    "media_file": arquivo_existente,
                    "video_file": arquivo_existente,
                    "arquivo": arquivo_existente,
                    "badge": "CENTRO DE TREINAMENTO",
                    "cor": "#ff1744",
                    "perfil": USER
                })
                slot_atual += 1
                continue

            # Baixa os novos slots (10, 11 e 12)
            print(f"\n[{slot_atual}/{TARGET_TOTAL}] Baixando novo: {url}")
            sucesso = False
            tipo = "image"
            arquivo_final = None

            video_elem = page.query_selector("article video, main video")
            if video_elem or "/reel/" in url:
                nome_base = f"media_{slot_atual}"
                ydl_opts = {
                    'outtmpl': f'{nome_base}.%(ext)s',
                    'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best',
                    'socket_timeout': 15,
                    'retries': 3,
                    'quiet': True,
                    'overwrites': True
                }
                if os.path.exists(COOKIES_FILE):
                    ydl_opts['cookiefile'] = COOKIES_FILE
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    for ext in [".mp4", ".mkv", ".webm"]:
                        chk = f"{nome_base}{ext}"
                        if os.path.exists(chk) and os.path.getsize(chk) > 10000:
                            arquivo_final = chk
                            tipo = "video"
                            sucesso = True
                            break
                except Exception:
                    sucesso = False

            if not sucesso:
                tipo = "image"
                arquivo_final = f"media_{slot_atual}.jpg"
                img_url = None
                imgs = page.query_selector_all('article img[srcset], main img[srcset]')
                for im in imgs:
                    srcset = im.get_attribute("srcset")
                    if srcset:
                        cand = [s.strip().split(" ")[0] for s in srcset.split(",")]
                        if cand:
                            img_url = cand[-1]
                            break
                if not img_url:
                    meta_img = page.query_selector('meta[property="og:image"]')
                    if meta_img:
                        img_url = meta_img.get_attribute("content")
                if img_url and baixar_imagem_hd(img_url, arquivo_final):
                    sucesso = True

            if sucesso and arquivo_final and os.path.exists(arquivo_final):
                print(f"  -> Salvo: {arquivo_final} ({tipo})")
                dados_finais.append({
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
                    "badge": "CENTRO DE TREINAMENTO",
                    "cor": "#ff1744",
                    "perfil": USER
                })
                slot_atual += 1

        browser.close()

    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(dados_finais, f, indent=2, ensure_ascii=False)

    print(f"\nFinalizado! Total de {len(dados_finais)} mídias salvas.")

if __name__ == "__main__":
    processar_mural()
