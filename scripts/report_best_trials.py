#!/usr/bin/env python3
"""
report_best_trials.py

Varre os CSVs de estudos do Optuna e reporta, para cada combinação, 
os melhores trials (menor RMSE) e a porcentagem de melhoria em relação ao baseline.

Padrão de arquivo esperado:
    ~/results/{metodo}/{sensor}/{dataset}/study_{sampler}.csv

Uso:
    python3 report_best_trials.py
    python3 report_best_trials.py --dataset forest02_straight
    python3 report_best_trials.py --results-dir ~/results --top-n 5
"""

import os
import glob
import argparse
import pandas as pd


def find_study_csvs(results_dir):
    """Encontra todos os CSVs de forma recursiva."""
    pattern = os.path.join(results_dir, "**", "study_*.csv")
    paths = sorted(glob.glob(pattern, recursive=True))
    return paths


def parse_path_info(csv_path, results_dir):
    """
    Extrai o método, sensor, dataset e sampler a partir do caminho do arquivo.
    Espera a estrutura: {metodo}/{sensor}/{dataset}/study_{sampler}.csv
    """
    rel = os.path.relpath(csv_path, results_dir)
    parts = rel.split(os.sep)
    
    metodo = parts[0] if len(parts) > 0 else "unknown"
    sensor = parts[1] if len(parts) > 1 else "unknown"
    dataset = parts[2] if len(parts) > 2 else "unknown"
    
    filename = parts[-1]
    sampler = filename.replace("study_", "").replace(".csv", "")
    
    return metodo, sensor, dataset, sampler


def analyze_csv(csv_path, top_n=3):
    """Lê um CSV de estudo e retorna baseline + top N melhores trials."""
    df = pd.read_csv(csv_path)

    if "value" not in df.columns:
        raise ValueError(f"Coluna 'value' não encontrada em {csv_path}")

    if "state" in df.columns:
        df = df[df["state"] == "COMPLETE"]

    df = df[df["value"].notna()]
    df = df[df["value"] != float("inf")]

    if df.empty:
        return None, None

    baseline_row = df[df["number"] == 0]
    baseline_value = baseline_row["value"].iloc[0] if not baseline_row.empty else None

    top_trials = df.nsmallest(top_n, "value")

    return baseline_value, top_trials


def format_params(row, df_columns):
    """Extrai e formata as colunas params_* de uma linha do dataframe."""
    param_cols = [c for c in df_columns if c.startswith("params_")]
    parts = []
    for c in param_cols:
        val = row[c]
        if pd.notna(val):
            name = c.replace("params_", "")
            if isinstance(val, float):
                parts.append(f"{name}={val:.4f}")
            else:
                parts.append(f"{name}={val}")
    return ", ".join(parts)


def main():
    parser = argparse.ArgumentParser(
        description="Relatório dos melhores trials por método/sensor/dataset/sampler."
    )
    parser.add_argument("--results-dir", default=os.path.expanduser("~/results"),
                        help="Diretório raiz de resultados (default: ~/results)")
    parser.add_argument("--top-n", type=int, default=3,
                        help="Quantos melhores trials mostrar por combinação (default: 3)")
    parser.add_argument("--csv-out", default=None,
                        help="Caminho opcional para salvar um resumo consolidado em CSV")
    # NOVO ARGUMENTO AQUI:
    parser.add_argument("--dataset", type=str, default=None,
                        help="Filtrar os resultados para um dataset específico (ex: forest02_straight)")
    
    args = parser.parse_args()

    results_dir = os.path.expanduser(args.results_dir)
    todas_paths = find_study_csvs(results_dir)

    # Filtragem pelo dataset desejado
    csv_paths = []
    for p in todas_paths:
        _, _, dset, _ = parse_path_info(p, results_dir)
        if args.dataset and dset != args.dataset:
            continue # Ignora se não for o dataset que você pediu
        csv_paths.append(p)

    if not csv_paths:
        if args.dataset:
            print(f"Nenhum CSV encontrado para o dataset '{args.dataset}' em {results_dir}")
        else:
            print(f"Nenhum CSV encontrado no padrão {results_dir}/**/study_*.csv")
        return

    summary_rows = []

    print("=" * 90)
    filtro_msg = f" (Filtrado para: {args.dataset})" if args.dataset else ""
    print(f"RELATÓRIO DE MELHORES TRIALS - {len(csv_paths)} estudos encontrados{filtro_msg}")
    print("=" * 90)

    for csv_path in csv_paths:
        metodo, sensor, dataset, sampler = parse_path_info(csv_path, results_dir)

        try:
            baseline_value, top_trials = analyze_csv(csv_path, top_n=args.top_n)
        except Exception as e:
            print(f"\n[ERRO] {csv_path}: {e}")
            continue

        print(f"\n--- {metodo} | {sensor} | {dataset} | {sampler} ---")

        if top_trials is None:
            print("  (sem trials válidos)")
            continue

        if baseline_value is not None:
            print(f"  Baseline (trial 0): RMSE = {baseline_value:.4f} m")
        else:
            print("  Baseline (trial 0): não encontrado no CSV")

        for rank, (_, row) in enumerate(top_trials.iterrows(), 1):
            rmse = row["value"]
            trial_num = int(row["number"])
            params_str = format_params(row, top_trials.columns)

            if baseline_value and baseline_value > 0:
                improvement = (baseline_value - rmse) / baseline_value * 100
                improvement_str = f"{improvement:+.1f}%"
            else:
                improvement = None
                improvement_str = "N/A"

            marker = " <- BASELINE" if trial_num == 0 else ""
            print(f"  #{rank}  trial_{trial_num:04d}  RMSE={rmse:.4f} m  "
                  f"(melhoria vs baseline: {improvement_str}){marker}")
            if params_str:
                print(f"        params: {params_str}")

            summary_rows.append({
                "metodo": metodo,
                "sensor": sensor,
                "dataset": dataset,
                "sampler": sampler,
                "rank": rank,
                "trial_number": trial_num,
                "rmse": rmse,
                "baseline_rmse": baseline_value,
                "improvement_pct": improvement,
                "params": params_str,
            })

    print("\n" + "=" * 90)

    if args.csv_out and summary_rows:
        out_df = pd.DataFrame(summary_rows)
        out_path = os.path.expanduser(args.csv_out)
        out_df.to_csv(out_path, index=False)
        print(f"Resumo consolidado salvo em: {out_path}")

    if summary_rows:
        best_per_combo = [r for r in summary_rows if r["rank"] == 1]
        best_per_combo_valid = [r for r in best_per_combo if r["improvement_pct"] is not None]
        best_per_combo_valid.sort(key=lambda r: r["improvement_pct"], reverse=True)

        print("\nRANKING GERAL (melhor trial de cada combinação, por % de melhoria):")
        for r in best_per_combo_valid:
            print(f"  {r['metodo']:10s} | {r['sensor']:10s} | {r['dataset']:15s} | {r['sampler']:6s}  "
                  f"RMSE={r['rmse']:.4f}  melhoria={r['improvement_pct']:+.1f}%")


if __name__ == "__main__":
    main()