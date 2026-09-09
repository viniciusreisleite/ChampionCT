import os, json, subprocess

print("=" * 60)
print("--- RELATÓRIO DE AUDITORIA: ChampionCT ---")
print("=" * 60)

# 1. Arquivos locais em disco
arquivos_disco = sorted([f for f in os.listdir(".") if f.startswith("media_") and (f.endswith(".mp4") or f.endswith(".jpg"))])
print(f"\n1. Mídias no disco local ({len(arquivos_disco)} arquivos):")
for f in arquivos_disco:
    tam_kb = os.path.getsize(f) / 1024
    print(f"   - {f:<15} ({tam_kb:.1f} KB)")

# 2. Arquivos rastreados no Git
res_git = subprocess.run(["git", "ls-files", "media_*"], capture_output=True, text=True)
arquivos_git = res_git.stdout.strip().splitlines() if res_git.stdout.strip() else []
print(f"\n2. Mídias rastreadas no Git ({len(arquivos_git)} arquivos):")
for f in arquivos_git:
    print(f"   - {f}")

# 3. Conteúdo do data.json
if os.path.exists("data.json"):
    try:
        with open("data.json", "r", encoding="utf-8") as jf:
            dados = json.load(jf)
        print(f"\n3. Entradas no data.json ({len(dados)} itens):")
        for idx, item in enumerate(dados, start=1):
            print(f"   [{idx:02d}] id: {item.get('id')} | tipo: {item.get('tipo')} | arq: {item.get('arquivo')}")
    except Exception as e:
        print(f"\n3. Erro ao ler data.json: {e}")
else:
    print("\n3. data.json NÃO EXISTE!")

# 4. Inspeção do index.html (busca como a mídia é chamada)
if os.path.exists("index.html"):
    with open("index.html", "r", encoding="utf-8", errors="ignore") as hf:
        html = hf.read()
    print("\n4. Diagnóstico do index.html:")
    tem_video = "<video" in html
    tem_autoplay = "autoplay" in html
    tem_muted = "muted" in html
    tem_img = "<img" in html
    print(f"   - Tag <video>: {'OK' if tem_video else 'FALTANDO'}")
    print(f"   - Atributo muted (obrigatório para autoplay de TV): {'OK' if tem_muted else 'FALTANDO/SEM MUTED'}")
    print(f"   - Suporte a <img> (para posts foto): {'OK' if tem_img else 'FALTANDO'}")
else:
    print("\n4. index.html NÃO EXISTE!")

print("\n" + "=" * 60)
