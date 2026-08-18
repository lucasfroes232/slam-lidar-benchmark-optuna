#!/usr/bin/env python3
"""
plot_custo_baseline_vs_best.py

Gera UMA imagem comparando o custo computacional (tempo, memória, CPU) entre
o baseline e o melhor trial de uma combinação método/sensor/dataset/sampler.

Pré-requisito: rodar measure_cost.py antes, para gerar o
~/results/{method}/{sensor}/{dataset}/cost/custo_{sampler}.json

Uso:
    python3 plot_custo_baseline_vs_best.py --method fast_lio --sensor ouster128 \
        --dataset forest02_straight --sampler tpe
"""

import os
import json
import argparse
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(
        description="Compara custo computacional: baseline vs. melhor trial."
    )
    parser.add_argument("--method", required=True)
    parser.add_argument("--sensor", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--sampler", required=True, choices=["tpe", "cmaes", "gp"])
    parser.add_argument("--results-dir", default=os.path.expanduser("~/results"))
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    cost_json = os.path.join(args.results_dir, args.method, args.sensor,
                              args.dataset, "cost", f"custo_{args.sampler}.json")

    if not os.path.exists(cost_json):
        print(f"[ERRO] Não encontrado: {cost_json}")
        print("Rode primeiro: python3 measure_cost.py --method ... --sensor ... --dataset ... --sampler ...")
        return

    with open(cost_json) as f:
        data = json.load(f)

    if "baseline" not in data or "best" not in data:
        print("[ERRO] O JSON não tem os dois lados (baseline e best). "
              "Rode measure_cost.py sem --only para gerar os dois.")
        return

    baseline_stats = data["baseline"]["stats"]
    best_stats = data["best"]["stats"]

    metrics = [
        ("wall_time_sec", "Tempo de execução (s)"),
        ("peak_mem_mb", "Memória de pico (MB)"),
        ("avg_cpu_pct", "CPU média (%)"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(13, 5))
    colors = ["#94a3b8", "#3b82f6"]  # cinza = baseline, azul = melhor

    for ax, (key, label) in zip(axes, metrics):
        vals = [baseline_stats.get(key, 0), best_stats.get(key, 0)]
        bars = ax.bar(["Baseline", "Melhor Trial"], vals, color=colors)
        ax.set_title(label, fontsize=12, fontweight="bold")
        ax.grid(True, axis="y", linestyle="--", alpha=0.4)
        ax.set_axisbelow(True)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, v, f"{v:.1f}",
                    ha="center", va="bottom", fontsize=10)

    rmse_info = ""
    if "rmse" in data["best"]:
        rmse_info = f" — RMSE do melhor trial: {data['best']['rmse']:.4f} m"

    fig.suptitle(f"Custo Computacional: Baseline vs. Melhor Trial — "
                 f"{args.method} ({args.sampler.upper()}){rmse_info}", fontsize=13)
    fig.tight_layout()

    out_dir = os.path.join(args.results_dir, args.method, args.sensor, args.dataset, "cost")
    out_path = args.out or os.path.join(out_dir, f"custo_baseline_vs_best_{args.sampler}.png")
    out_path = os.path.expanduser(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    fig.savefig(out_path, dpi=200, facecolor="white")
    print(f"Imagem salva em: {out_path}")


if __name__ == "__main__":
    main()