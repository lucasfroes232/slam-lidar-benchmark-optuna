import pandas as pd
import matplotlib.pyplot as plt
import os

# =====================================================================
# 1. CONFIGURAÇÃO DOS ARQUIVOS
# Substitua pelos caminhos reais dos seus CSVs do dataset forest02_straight
# =====================================================================
METODO = "FAST_LIO" # Mude para o método que quer plotar (ex: LIO-Livox)

caminho_tpe = os.path.expanduser("~/results/lio_livox/horizon/forest02_straight/study_tpe.csv")
caminho_cmaes = os.path.expanduser("~/results/lio_livox/horizon/forest02_straight/study_cmaes.csv") # <-- Sem hífen!
caminho_gp = os.path.expanduser("~/results/lio_livox/horizon/forest02_straight/study_gp.csv")

# =====================================================================
# 2. FUNÇÃO DE PROCESSAMENTO MATEMÁTICO (CUMULATIVE MINIMUM)
# =====================================================================
def extrair_convergencia(csv_path):
    if not os.path.exists(csv_path):
        print(f"[AVISO] Arquivo não encontrado: {csv_path}")
        return [], []
        
    df = pd.read_csv(csv_path)
    
    # Filtra apenas os trials que completaram com sucesso
    if "state" in df.columns:
        df = df[df["state"] == "COMPLETE"]
        
    # Garante que está na ordem cronológica de execução
    df = df.sort_values("number")
    
    # O PULO DO GATO: calcula o menor valor visto ATÉ aquele trial
    melhor_rmse = df["value"].cummin()
    numero_trials = df["number"]
    
    return numero_trials, melhor_rmse

# =====================================================================
# 3. EXTRAÇÃO DOS DADOS
# =====================================================================
trials_tpe, conv_tpe = extrair_convergencia(caminho_tpe)
trials_cma, conv_cma = extrair_convergencia(caminho_cmaes)
trials_gp, conv_gp = extrair_convergencia(caminho_gp)

# =====================================================================
# 4. CRIAÇÃO DO GRÁFICO (DESIGN PARA O GOOGLE SLIDES)
# =====================================================================
fig, ax = plt.subplots(figsize=(10, 6))

# Plota cada linha com estilos e cores diferentes para facilitar a leitura
if len(trials_tpe) > 0:
    ax.plot(trials_tpe, conv_tpe, label='TPE', color='#3b82f6', linewidth=2.5, marker='o', markersize=4)
if len(trials_cma) > 0:
    ax.plot(trials_cma, conv_cma, label='CMA-ES', color='#10b981', linewidth=2.5, marker='s', markersize=4)
if len(trials_gp) > 0:
    ax.plot(trials_gp, conv_gp, label='GP', color='#6366f1', linewidth=2.5, marker='^', markersize=4)

# Customização de eixos e títulos
ax.set_xlabel('Número do Trial', fontsize=12, fontweight='bold', color='#1e293b')
ax.set_ylabel('Melhor RMSE Encontrado (m)', fontsize=12, fontweight='bold', color='#1e293b')
ax.set_title(f'Curva de Convergência do Optuna - {METODO}', fontsize=16, pad=20, color='#1e293b')

# Grade de fundo e legenda
ax.grid(True, linestyle='--', alpha=0.6)
ax.set_axisbelow(True)
ax.legend(fontsize=12, loc='upper right', framealpha=0.9)

# Estilização das bordas
for spine in ax.spines.values():
    spine.set_color('#94a3b8')

fig.tight_layout()

# Salva a imagem direto na pasta de resultados
nome_saida = os.path.expanduser(f'~/results/convergencia_{METODO.lower()}.png')
plt.savefig(nome_saida, dpi=300, transparent=False, facecolor='white')
print(f"Gráfico salvo com sucesso como '{nome_saida}'!")

#plt.show()