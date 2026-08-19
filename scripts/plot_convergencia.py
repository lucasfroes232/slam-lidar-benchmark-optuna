#!/usr/bin/env python3
"""
plot_convergencia.py

Gera o gráfico de convergência (melhor RMSE acumulado por trial) comparando
os três samplers (TPE, CMA-ES, GP) para um método/sensor/dataset específico.

Uso:
    python3 plot_convergencia.py --method lio_livox --sensor horizon --dataset forest02_straight
    python3 plot_convergencia.py --method fast_lio --sensor ouster128 --dataset forest02_straight
    python3 plot_convergencia.py --method lego_loam --sensor velodyne16_utility --dataset forest02_straight

Opcional:
    --results-dir  (default: ~/results)
    --out          (caminho de saída; default: ~/results/convergencia_{method}.png)
"""

import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt


def extrair_convergencia(csv_path):
    """Lê um study_{sampler}.csv e retorna (numero_trials, melhor_rmse_cumulativo)."""
    if not os.path.exists(csv_path):
        print(f"[AVISO] Arquivo não encontrado: {csv_path}")
        return [], []

    df = pd.read_csv(csv_path)

    # Filtra apenas os trials que completaram com sucesso
    if "state" in df.columns:
        df = df[df["state"] == "COMPLETE"]

    # Garante que está na ordem cronológica de execução
    df = df.sort_values("number")

    # Calcula o menor valor visto ATÉ aquele trial
    melhor_rmse = df["value"].cummin()
    numero_trials = df["number"]

    return numero_trials, melhor_rmse


def main():
    parser = argparse.ArgumentParser(
        description="Gráfico de convergência (TPE vs CMA-ES vs GP) para um método/sensor/dataset."
    )
    parser.add_argument("--method", required=True,
                         help="Nome do método (ex: fast_lio, lio_livox, lego_loam)")
    parser.add_argument("--sensor", required=True,
                         help="Nome da pasta de config/sensor (ex: ouster128, horizon, velodyne16_utility)")
    parser.add_argument("--dataset", required=True,
                         help="Nome do dataset (ex: forest02_straight)")
    parser.add_argument("--results-dir", default=os.path.expanduser("~/results"),
                         help="Diretório raiz de resultados (default: ~/results)")
    parser.add_argument("--out", default=None,
                         help="Caminho de saída do PNG (default: ~/results/convergencia_{method}.png)")
    args = parser.parse_args()

    base_dir = os.path.join(args.results_dir, args.method, args.sensor, args.dataset)

    caminho_tpe = os.path.join(base_dir, "study_tpe.csv")
    caminho_cmaes = os.path.join(base_dir, "study_cmaes.csv")
    caminho_gp = os.path.join(base_dir, "study_gp.csv")

    trials_tpe, conv_tpe = extrair_convergencia(caminho_tpe)
    trials_cma, conv_cma = extrair_convergencia(caminho_cmaes)
    trials_gp, conv_gp = extrair_convergencia(caminho_gp)

    if len(trials_tpe) == 0 and len(trials_cma) == 0 and len(trials_gp) == 0:
        print("[ERRO] Nenhum CSV válido encontrado. Confira --method/--sensor/--dataset.")
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    if len(trials_tpe) > 0:
        ax.plot(trials_tpe, conv_tpe, label='TPE', color='#3b82f6',
                linewidth=2.5, marker='o', markersize=4)
    if len(trials_cma) > 0:
        ax.plot(trials_cma, conv_cma, label='CMA-ES', color='#10b981',
                linewidth=2.5, marker='s', markersize=4)
    if len(trials_gp) > 0:
        ax.plot(trials_gp, conv_gp, label='GP', color='#6366f1',
                linewidth=2.5, marker='^', markersize=4)

    ax.set_xlabel('Número do Trial', fontsize=12, fontweight='bold', color='#1e293b')
    ax.set_ylabel('Melhor RMSE Encontrado (m)', fontsize=12, fontweight='bold', color='#1e293b')
    ax.set_title(f'Curva de Convergência do Optuna - {args.method}', fontsize=16, pad=20, color='#1e293b')

    ax.grid(True, linestyle='--', alpha=0.6)
    ax.set_axisbelow(True)
    ax.legend(fontsize=12, loc='upper right', framealpha=0.9)

    for spine in ax.spines.values():
        spine.set_color('#94a3b8')

    fig.tight_layout()

    out_path = args.out or os.path.join(args.results_dir, f"convergencia_{args.method}.png")
    out_path = os.path.expanduser(out_path)
    plt.savefig(out_path, dpi=300, transparent=False, facecolor='white')
    plt.close(fig)
    print(f"Gráfico salvo com sucesso como '{out_path}'!")


if __name__ == "__main__":
    main()