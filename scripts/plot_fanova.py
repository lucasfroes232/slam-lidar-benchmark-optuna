import optuna
import optuna.visualization as vis
import os

# =====================================================================
# 1. ESCOLHA QUAL BANCO DE DADOS ANALISAR
# (Descomente a linha do método que quer gerar agora)
# =====================================================================

# Para o FAST-LIO:
#db_path = os.path.expanduser("~/results/fast_lio/ouster128/forest02_straight/study_cmaes.db")
#nome_saida = "importancia_fanova_fast_lio.html"

# Para o LIO-Livox (descomente as duas linhas abaixo para usar):
db_path = os.path.expanduser("~/results/lio_livox/horizon/forest02_straight/study_cmaes.db")
nome_saida = "importancia_fanova_lio_livox.html"

# =====================================================================
# 2. CONEXÃO COM O BANCO DE DADOS
# =====================================================================
if not os.path.exists(db_path):
    print(f"[ERRO] Banco de dados não encontrado em: {db_path}")
    exit()

storage_url = f"sqlite:///{db_path}"

# O Optuna exige o nome do estudo para carregá-lo. 
# Como as vezes esquecemos qual nome demos no optuna.create_study(), 
# este comando vasculha o banco e pega o nome automaticamente:
estudos_salvos = optuna.get_all_study_summaries(storage=storage_url)

if not estudos_salvos:
    print("[ERRO] O banco de dados foi encontrado, mas está vazio.")
    exit()

nome_do_estudo = estudos_salvos[0].study_name
print(f"Carregando histórico do estudo: '{nome_do_estudo}'...")

# =====================================================================
# 3. GERAÇÃO DO GRÁFICO (fANOVA)
# =====================================================================
study = optuna.load_study(study_name=nome_do_estudo, storage=storage_url)

# A função plot_param_importances usa fANOVA por padrão
fig = vis.plot_param_importances(study)

# Customizando o título para ficar com cara de artigo/apresentação
fig.update_layout(
    title=f"Importância de Hiperparâmetros (fANOVA) ",
    title_x=0.5,
    font=dict(size=14)
)

# =====================================================================
# 4. EXPORTAÇÃO
# Exportamos como HTML para contornar a falta de interface do Docker
# =====================================================================
caminho_final = os.path.expanduser(f"~/results/{nome_saida}")
fig.write_html(caminho_final)

print("="*60)
print(f"Sucesso! Gráfico salvo em: {caminho_final}")
print("Vá no explorador de arquivos do VS Code, clique com o botão direito")
print(f"no arquivo '{nome_saida}' e abra no seu navegador!")
print("="*60)