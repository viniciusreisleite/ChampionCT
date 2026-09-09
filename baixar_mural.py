import os, sys, json, time, re, shutil
import requests
from playwright.sync_api import sync_playwright
import yt_dlp

ACCOUNTS = [
    {"username": "championct_", "badge": "", "color": "#ff1744"}
]

TARGET_TOTAL = 12
DATA_JSON = "data.json"
COOKIES_FILE = "cookies.txt"

def extrair_shortcode(url):
    m = re.search(r'/(?:p|reel|tv)/([^/?#&]+)', url)
    return m.group(1) if m else url

def baixar_imagem_hd(url, destino):
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and len(r.content) > 5000:
            with open(destino, "wb") as f:
                f.write(r.content)
            return True
    except Exception:
        pass
    return False

def processar():
    posts_coletados = []
    
    # Carrega o que já temos válido no disco
    cache_existente = {}
    if os.path.exists(DATA_JSON):
        try:
            with open(DATA_JSON, "r", encoding="utf-8") as f:
                for it in json.load(f):
                    arq = it.get("arquivo", "")
                    if arq and os.path.exists(arq) and os.path.getsize(arq) > 1000:
                        cache_existente[it.get("id")] = it
        except Exception:
            pass

    print(f"Mídias válidas já em cache: {len(cache_existente)}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        usr = "championct_"
        print(f"Acessando feed de @{usr}...")
        page.goto(f"https://www.instagram.com/{usr}/", wait_until="domcontentloaded", timeout=60000)
        
        # Rola mais vezes para encontrar pelo menos 18 URLs candidatas
        urls_candidatas = []
        for _ in range(12):
            anchors = page.query_selector_all('a[href*="/p/"], a[href*="/reel/"]')
            for a in anchors:
                href = a.get_attribute("href")
                if href:
                    clean = href.split("?")[0].strip("/")
                    full = f"https://www.instagram.com/{clean}/"
                    if full not in urls_candidatas:
                        urls_candidatas.append(full)
            if len(urls_candidatas) >= 18:
                break
            page.evaluate("window.scrollBy(0, 1200)")
            page.wait_for_timeout(600)

        print(f"Total de posts identificados no feed: {len(urls_candidatas)}")

        for url in urls_candidatas:
            if len(posts_coletados) >= TARGET_TOTAL:
                break

            sc = extrair_shortcode(url)

            # Se já está baixado e válido, reaproveita
            if sc in cache_existente:
                print(f"  [CACHE OK] {sc}")
                posts_coletados.append(cache_existente[sc])
                continue

            print(f"  [BAIXANDO NOVO] {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)

            caption = ""
            meta_tag = page.query_selector('meta[property="og:title"]')
            if meta_tag:
                caption = meta_tag.get_attribute("content") or ""

            temp_id = f"temp_{sc}"
            arquivo_final = None
            tipo = "image"

            # Tenta como vídeo via yt-dlp
            if "/reel/" in url:
                ydl_opts = {
                    'outtmpl': f'{temp_id}.%(ext)s',
                    'format': 'bestvideo+bestaudio/best',
                    'socket_timeout': 15,
                    'retries': 2,
                    'quiet': True
                }
                if os.path.exists(COOKIES_FILE):
                    ydl_opts['cookiefile'] = COOKIES_FILE
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    for ext in [".mp4", ".mkv", ".webm"]:
                        if os.path.exists(f"{temp_id}{ext}"):
                            arquivo_final = f"{temp_id}{ext}"
                            tipo = "video"
                            break
                except Exception:
                    pass

            # Se não for vídeo, baixa imagem HD
            if not arquivo_final:
                tipo = "image"
                arquivo_final = f"{temp_id}.jpg"
                img_url = None
                
                # Procura imagem de melhor resolução
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
                    meta_og = page.query_selector('meta[property="og:image"]')
                    if meta_og:
                        img_url = meta_og.get_attribute("content")

                if img_url:
                    sucesso = baixar_imagem_hd(img_url, arquivo_final)
                    if not sucesso or not os.path.exists(arquivo_final):
                        arquivo_final = None

            if arquivo_final and os.path.exists(arquivo_final):
                posts_coletados.append({
                    "id": sc,
                    "url": url,
                    "caption": caption,
                    "tipo": tipo,
                    "arquivo": arquivo_final,
                    "badge": "",
                    "cor": "#ff1744",
                    "perfil": usr
                })
                print(f"    -> Salvo com sucesso ({tipo})")

        browser.close()

    # Organiza os 12 slots finais
    finais = posts_coletados[:TARGET_TOTAL]
    novos_itens = []
    preservar = set()

    print(f"\nConsolidando {len(finais)} arquivos de media_1 a media_{len(finais)}...")
    for idx, item in enumerate(finais, start=1):
        ext = os.path.splitext(item["arquivo"])[1]
        nome_slot = f"media_{idx}{ext}"
        
        origem = item["arquivo"]
        if origem != nome_slot:
            if os.path.exists(nome_slot):
                os.remove(nome_slot)
            shutil.move(origem, nome_slot)
            item["arquivo"] = nome_slot

        preservar.add(nome_slot)
        novos_itens.append(item)

    # Limpeza de sobras
    for arq in os.listdir("."):
        if arq.startswith("temp_"):
            try: os.remove(arq)
            except: pass

    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(novos_itens, f, indent=2, ensure_ascii=False)

    print(f"Pronto! {len(novos_itens)} posts prontos no data.json.")

if __name__ == "__main__":
    processar()
