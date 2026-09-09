import os, sys, json, time, re
import requests
from playwright.sync_api import sync_playwright
import yt_dlp

TARGET_TOTAL = 12
USER = "championct_"
DATA_JSON = "data.json"
COOKIES_FILE = "cookies.txt"

# Shortcodes dos posts fixados para descartar
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
    print(f"=== BAIXANDO OS 12 SLOTS COMPLETOS DE @{USER} ===")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = context.new_page()

        print(f"Acessando feed de @{USER}...")
        page.goto(f"https://www.instagram.com/{USER}/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)

        # Rola o feed para capturar uma lista ampla de candidatos
        candidatos = []
        for _ in range(25):
            anchors = page.query_selector_all('a[href*="/p/"], a[href*="/reel/"]')
            for a in anchors:
                href = a.get_attribute("href")
                if href:
                    sc = extrair_shortcode(href)
                    if sc in SHORTCODES_FIXADOS:
                        continue
                    clean = href.split("?")[0].strip("/")
                    full = f"https://www.instagram.com/{clean}/"
                    if full not in candidatos:
                        candidatos.append(full)
            if len(candidatos) >= 20:
                break
            page.evaluate("window.scrollBy(0, 1200)")
            page.wait_for_timeout(600)

        print(f"URLs candidatas encontradas (sem fixados): {len(candidatos)}")

        dados_finais = []
        slot_atual = 1

        for url in candidatos:
            if slot_atual > TARGET_TOTAL:
                break

            sc = extrair_shortcode(url)
            print(f"\n[{slot_atual}/{TARGET_TOTAL}] Processando: {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1200)

            caption = ""
            meta_tag = page.query_selector('meta[property="og:title"]')
            if meta_tag:
                caption = meta_tag.get_attribute("content") or ""

            sucesso = False
            tipo = "image"
            arquivo_final = None

            # 1. Tenta como vídeo (limite 720p)
            video_elem = page.query_selector("article video, main video")
            if video_elem or "/reel/" in url:
                nome_base = f"media_{slot_atual}"
                ydl_opts = {
                    'outtmpl': f'{nome_base}.%(ext)s',
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
                        chk = f"{nome_base}{ext}"
                        if os.path.exists(chk) and os.path.getsize(chk) > 10000:
                            arquivo_final = chk
                            tipo = "video"
                            sucesso = True
                            break
                except Exception:
                    sucesso = False

            # 2. Se não for vídeo ou falhar, baixa como imagem HD
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

            # Só avança para o próximo slot se o arquivo foi realmente salvo e validado no disco
            if sucesso and arquivo_final and os.path.exists(arquivo_final):
                tam_kb = os.path.getsize(arquivo_final) / 1024
                print(f"  -> Slot {slot_atual} salvo com sucesso: {arquivo_final} ({tipo} - {tam_kb:.1f} KB)")
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
            else:
                print(f"  -> Falha no download. Pulando para o próximo do feed sem avançar o slot...")

        browser.close()

    # Salva o data.json somente com os itens que existem fisicamente no disco
    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(dados_finais, f, indent=2, ensure_ascii=False)

    print(f"\nFinalizado! Total de {len(dados_finais)} mídias salvas em sequência contínua.")

if __name__ == "__main__":
    processar_mural()
