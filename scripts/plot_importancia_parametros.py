import pandas as pd
import matplotlib.pyplot as plt
import os

# =====================================================================
# 1. CONFIGURAÇÃO DO ARQUIVO
# Aponte para o CSV do primeiro dataset (forest01_square)
# =====================================================================
METODO = "LIO_Livox"
DATASET = "forest01_square"

caminho_csv = os.path.expanduser(f"~/results/lego_loam/velodyne16_utility/forest01_square/study_cmaes.csv")
nome_saida = "importancia_parametros.png"
# =====================================================================
# 2. CÁLCULO ESTATÍSTICO (SPEARMAN)
# =====================================================================
if not os.path.exists(caminho_csv):
    print(f"[ERRO] Arquivo não encontrado: {caminho_csv}")
    exit()

df = pd.read_csv(caminho_csv)

# Garante que só vamos analisar trials que não falharam
if "state" in df.columns:
    df = df[df["state"] == "COMPLETE"]

# Remove valores que deram infinito (falhas de tracking do SLAM)
df = df.dropna(subset=["value"])
df = df[df["value"] != float("inf")]

# Isola as colunas de parâmetros e a coluna do RMSE ("value")
colunas_params = [col for col in df.columns if col.startswith("params_")]
df_clean = df[colunas_params + ["value"]]

# Calcula a Correlação de Spearman e pega o valor absoluto (0 a 1)
correlacao = df_clean.corr(method="spearman")["value"].drop("value")
importancia = correlacao.abs().sort_values(ascending=True)

# Limpa o prefixo 'params_' para o gráfico ficar bonito
nomes_limpos = [nome.replace("params_", "") for nome in importancia.index]

# =====================================================================
# 3. GERAÇÃO DO GRÁFICO PARA OS SLIDES
# =====================================================================
fig, ax = plt.subplots(figsize=(10, 6))

barras = ax.barh(nomes_limpos, importancia, color='#10b981', height=0.6) # Verde para diferenciar

ax.set_xlabel('Importância do Parâmetro (Correlação de Spearman)', fontsize=12, fontweight='bold', color='#1e293b')
ax.set_title(f'Impacto no RMSE - {METODO}', fontsize=16, pad=20, color='#1e293b')

ax.xaxis.grid(True, linestyle='--', alpha=0.7)
ax.set_axisbelow(True)
for spine in ax.spines.values():
    spine.set_color('#94a3b8')

# Método clássico para adicionar rótulos (compatível com Matplotlib antigo)
for barra in barras:
    largura = barra.get_width()
    # Adiciona o texto um pouco à direita do fim da barra
    ax.text(largura + 0.01, 
            barra.get_y() + barra.get_height() / 2, 
            f'{largura:.2f}', 
            va='center', 
            fontsize=11, 
            color='#334155', 
            fontweight='bold')
ax.set_xlim(0, max(importancia.max() * 1.15, 0.1)) # Evita erro se a importância for muito baixa

fig.tight_layout()

# Salva a imagem solta na pasta atual
caminho_final = os.path.expanduser(f"~/results/lego_loam/velodyne16_utility/plots/{nome_saida}.png")
plt.savefig(caminho_final, dpi=300, transparent=False, facecolor='white')
print(f"Gráfico salvo em: {caminho_final}")

print("="*60)
print(f"Gráfico gerado com sucesso! Arquivo: {nome_saida}")
print("Você pode abrir clicando nele pelo VS Code.")
print("="*60)