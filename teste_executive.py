import requests

resp = requests.get("http://127.0.0.1:8000/api/vagas", params={
    "cargo": "Executive",
    "cidade": "Sao Paulo",
    "estado": "SP",
    "modalidade": "Híbrido",
    "pagina": 1
}, timeout=30)

data = resp.json()
print("Total:", data["total_vagas"])
print("\nFontes com vagas:")
for fonte in data["fontes"]:
    if fonte.get("retornadas", 0) > 0:
        print(f"  {fonte['fonte']}: {fonte['retornadas']}")

gh = [v for v in data["vagas"] if v["fonte"] == "Greenhouse"]
print(f"\nGreenhouse: {len(gh)}")

if gh:
    for vaga in gh[:2]:
        print(f"  - {vaga['titulo']} | {vaga['local']} | {vaga['modalidade']}")
