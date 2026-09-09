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

def extrair_imagem_completa(page):
    """Busca a foto real sem o crop 1:1 de preview do Instagram"""
    try:
        # 1. Busca todas as imagens dentro do artigo
        imgs = page.query_selector_all('article img[srcset], main img[srcset], div[role="dialog"] img[srcset]')
        melhor_url = None
        maior_largura = 0

        for im in imgs:
            srcset = im.get_attribute("srcset")
            if srcset:
                # Cada item é: 'https://... 1080w'
                entradas = srcset.split(",")
                for entrada in entradas:
                    partes = entrada.strip().split(" ")
                    url_candidata = partes[0]
                    largura = int(partes[1].replace("w", "")) if len(partes) > 1 and "w" in partes[1] else 0
                    
                    if largura > maior_largura:
                        maior_largura = largura
                        melhor_url = url_candidata

        if melhor_url:
            return melhor_url

        # 2. Fallback: pega a tag img visível do post
        single_img = page.query_selector('article div[role="button"] img, article ul li img, article img')
        if single_img:
            src = single_img.get_attribute("src")
            if src and "scontent" in src:
                return src
    except Exception:
        pass
    return None

def processar_mural():
    print(f"=== REPROCESSANDO POSTS COM FOTOS ORIGINAIS (SEM CROP) ===")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        page = context.new_page()

        candidatos = []

        # 1. Feed Principal
        print(f"Acessando feed de @{USER}...")
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

        # 2. Aba Reels para garantir 12 itens
        if len(candidatos) < TARGET_TOTAL + 4:
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

        dados_finais = []
        slot_atual = 1

        for url in candidatos:
            if slot_atual > TARGET_TOTAL:
                break

            sc = extrair_shortcode(url)
            arquivo_existente = None
            tipo_existente = "video"
            
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

            # Se for vídeo e já existir intacto no disco (slots 2 a 5, 7 a 9), mantém
            if arquivo_existente and tipo_existente == "video":
                print(f"  [SLOT {slot_atual} OK] {arquivo_existente}")
                dados_finais.append({
                    "id": sc, "url": url, "caption": caption, "text": caption,
                    "type": tipo_existente, "tipo": tipo_existente,
                    "media": arquivo_existente, "media_file": arquivo_existente,
                    "video_file": arquivo_existente, "arquivo": arquivo_existente,
                    "badge": "CENTRO DE TREINAMENTO", "cor": "#ff1744", "perfil": USER
                })
                slot_atual += 1
                continue

            # Baixa novo ou refaz foto em resolução original
            print(f"\n[{slot_atual}/{TARGET_TOTAL}] Baixando mídia completa: {url}")
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

            # Se for foto, usa o extrator de imagem completa (sem crop quadrado)
            if not sucesso:
                tipo = "image"
                arquivo_final = f"media_{slot_atual}.jpg"
                img_hd_url = extrair_imagem_completa(page)
                
                if img_hd_url and baixar_imagem_hd(img_hd_url, arquivo_final):
                    sucesso = True

            if sucesso and arquivo_final and os.path.exists(arquivo_final):
                tam_kb = os.path.getsize(arquivo_final) / 1024
                print(f"  -> Salvo slot {slot_atual}: {arquivo_final} ({tipo} - {tam_kb:.1f} KB)")
                dados_finais.append({
                    "id": sc, "url": url, "caption": caption, "text": caption,
                    "type": tipo, "tipo": tipo,
                    "media": arquivo_final, "media_file": arquivo_final,
                    "video_file": arquivo_final, "arquivo": arquivo_final,
                    "badge": "CENTRO DE TREINAMENTO", "cor": "#ff1744", "perfil": USER
                })
                slot_atual += 1

        browser.close()

    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(dados_finais, f, indent=2, ensure_ascii=False)

    print(f"\nFinalizado! Total de {len(dados_finais)} mídias salvas.")

if __name__ == "__main__":
    processar_mural()
