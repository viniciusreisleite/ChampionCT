import os, sys, json, time, re, shutil
from playwright.sync_api import sync_playwright
import yt_dlp

ACCOUNTS = [
    {"username": "championct_", "badge": "CENTRO DE TREINAMENTO", "color": "#ff1744"}
]

TARGET_TOTAL = 12
POSTS_PER_ACCOUNT = 12
DATA_JSON = "data.json"
COOKIES_FILE = "cookies.txt"

# Shortcodes dos fixados do topo para exclusão
SHORTCODES_FIXADOS = {"DalHQ6aRQor", "DVTXFY1jRa9", "DSqRcsEDsaY"}

def extrair_shortcode(url):
    m = re.search(r'/(?:p|reel|tv)/([^/?#&]+)', url)
    return m.group(1) if m else url

def carregar_cookies(context):
    if os.path.exists(COOKIES_FILE):
        cookies = []
        with open(COOKIES_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for l in f:
                if l.startswith("#") or not l.strip(): continue
                p = l.strip().split("\t")
                if len(p) >= 7:
                    cookies.append({
                        "domain": p[0] if p[0].startswith(".") else f".{p[0]}",
                        "path": p[2],
                        "secure": p[3].lower() == "true",
                        "expires": int(p[4]) if p[4].isdigit() else int(time.time()) + 86400,
                        "name": p[5],
                        "value": p[6]
                    })
        if cookies:
            try: context.add_cookies(cookies)
            except: pass

def salvar_imagem_pelo_browser(page, destino):
    """Pega a imagem direto do canvas/buffer do navegador para evitar 403 da CDN e sem crop"""
    try:
        # Tenta pegar elemento de imagem principal
        img_el = page.query_selector('article div[role="button"] img, article ul li img, article img[srcset], main img[srcset]')
        if not img_el:
            img_el = page.query_selector('article img')
        
        if img_el:
            # Captura a screenshot do elemento exato da imagem sem crop quadrado
            img_el.screenshot(path=destino, quality=95, type="jpeg")
            if os.path.exists(destino) and os.path.getsize(destino) > 15000:
                return True
    except Exception as e:
        print(f"    Erro screenshot browser: {e}")
    return False

def processar_mural():
    print("=== VARREDURA DOS 12 POSTS SEM FIXADOS (CHAMPION CT) ===")
    posts_coletados = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        carregar_cookies(context)
        page = context.new_page()

        for acc in ACCOUNTS:
            usr = acc["username"]
            badge = acc.get("badge", "")
            cor = acc.get("color", "#ff1744")
            
            print(f"\nAcessando perfil @{usr}...")
            page.goto(f"https://www.instagram.com/{usr}/", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)

            candidatos = []
            # Coleta na grade
            for _ in range(15):
                for a in page.query_selector_all('a[href*="/p/"], a[href*="/reel/"]'):
                    h = a.get_attribute("href")
                    if h:
                        sc = extrair_shortcode(h)
                        if sc in SHORTCODES_FIXADOS:
                            continue
                        clean = f"https://www.instagram.com/{h.split('?')[0].strip('/')}/"
                        if clean not in candidatos:
                            candidatos.append(clean)
                if len(candidatos) >= TARGET_TOTAL + 6:
                    break
                page.evaluate("window.scrollBy(0, 1000)")
                page.wait_for_timeout(400)

            # Se travar a rolagem abaixo de 12, complementa com a aba reels
            if len(candidatos) < TARGET_TOTAL:
                print("Complementando via aba /reels/...")
                page.goto(f"https://www.instagram.com/{usr}/reels/", wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2000)
                for _ in range(15):
                    for a in page.query_selector_all('a[href*="/reel/"]'):
                        h = a.get_attribute("href")
                        if h:
                            sc = extrair_shortcode(h)
                            if sc in SHORTCODES_FIXADOS:
                                continue
                            clean = f"https://www.instagram.com/{h.split('?')[0].strip('/')}/"
                            if clean not in candidatos:
                                candidatos.append(clean)
                    if len(candidatos) >= TARGET_TOTAL + 6:
                        break
                    page.evaluate("window.scrollBy(0, 1000)")
                    page.wait_for_timeout(400)

            print(f"Total de candidatos válidos encontrados: {len(candidatos)}")

            for url in candidatos:
                if len(posts_coletados) >= TARGET_TOTAL:
                    break

                sc = extrair_shortcode(url)
                print(f"\n[{len(posts_coletados)+1}/{TARGET_TOTAL}] Processando: {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1500)

                caption = ""
                meta_tag = page.query_selector('meta[property="og:title"]')
                if meta_tag:
                    caption = meta_tag.get_attribute("content") or ""

                post_temp_id = f"temp_{sc}"
                sucesso = False
                tipo = "image"
                arquivo_final = None

                # 1. Se for Reel ou vídeo explícito, baixa com yt-dlp 720p
                video_elem = page.query_selector("article video, main video")
                if video_elem or "/reel/" in url:
                    ydl_opts = {
                        'outtmpl': f'{post_temp_id}.%(ext)s',
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
                            chk = f"{post_temp_id}{ext}"
                            if os.path.exists(chk) and os.path.getsize(chk) > 10000:
                                arquivo_final = chk
                                tipo = "video"
                                sucesso = True
                                break
                    except Exception:
                        sucesso = False

                # 2. Se for foto (/p/) ou falhar vídeo, extrai imagem integral direto da tela
                if not sucesso:
                    tipo = "image"
                    arquivo_final = f"{post_temp_id}.jpg"
                    if salvar_imagem_pelo_browser(page, arquivo_final):
                        sucesso = True

                if sucesso and arquivo_final and os.path.exists(arquivo_final):
                    tam_kb = os.path.getsize(arquivo_final) / 1024
                    print(f"  -> Salvo com sucesso: {arquivo_final} ({tipo} - {tam_kb:.1f} KB)")
                    posts_coletados.append({
                        "id": sc,
                        "url": url,
                        "caption": caption,
                        "text": caption,
                        "type": tipo,
                        "tipo": tipo,
                        "media": arquivo_final,
                        "arquivo": arquivo_final,
                        "badge": badge,
                        "cor": cor,
                        "perfil": usr
                    })

        browser.close()

    # Organização de media_1 a media_12
    posts_finais = posts_coletados[:TARGET_TOTAL]
    dados_json_novo = []

    print("\nOrganizando slots media_1 a media_12...")
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

    # Limpeza de sobras temporárias
    for arq in os.listdir("."):
        if (arq.startswith("media_") or arq.startswith("temp_")) and (arq.endswith(".jpg") or arq.endswith(".mp4") or arq.endswith(".png")):
            if arq not in arquivos_preservados:
                try: os.remove(arq)
                except: pass

    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(dados_json_novo, f, indent=2, ensure_ascii=False)

    print(f"\nFinalizado! Total de {len(dados_json_novo)} mídias salvas com sucesso.")

if __name__ == "__main__":
    processar_mural()
