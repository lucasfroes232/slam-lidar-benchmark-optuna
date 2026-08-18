#!/usr/bin/env python3
"""
measure_cost.py

Mede custo computacional (tempo, memória, CPU) rodando de novo SÓ o baseline
e o melhor trial de uma combinação método/sensor/dataset/sampler -- em vez de
instrumentar os 50 trials da otimização inteira.

Pré-requisito: a otimização (optuna_optimize.py) já rodou e gerou o
study_{sampler}.csv com pelo menos um trial válido (value diferente de 999/inf).

Uso:
    python3 measure_cost.py --method fast_lio --sensor ouster128 \
        --dataset forest02_straight --sampler tpe

    # Rodar só um dos dois (ex: só o melhor, se já tiver o custo do baseline salvo)
    python3 measure_cost.py --method fast_lio --sensor ouster128 \
        --dataset forest02_straight --sampler tpe --only best
"""

import os
import re
import json
import yaml
import shutil
import argparse
import subprocess
import pandas as pd

PENALIDADE_TRIAL_INVALIDO = 999.0


def get_project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def get_ws_src_root():
    return "/root/slam_ws/src"


def get_ws_root():
    return "/root/slam_ws"


def resolve_path(relative_path, root_dir):
    if relative_path.startswith("src/"):
        return os.path.join(get_ws_src_root(), relative_path[len("src/"):])
    return os.path.join(root_dir, relative_path)


def inject_yaml_params(master_yaml, target_yaml, method_name, params):
    with open(master_yaml, 'r') as f:
        content = f.read()
    lines = content.splitlines()
    lines = [ln for ln in lines if not ln.strip().startswith('%YAML')]
    content = '\n'.join(lines)
    data = yaml.safe_load(content)

    for key, value in params.items():
        if method_name == "fast_lio" and key == "blind":
            if 'preprocess' not in data:
                data['preprocess'] = {}
            data['preprocess'][key] = value
        else:
            data[key] = value

    with open(target_yaml, 'w') as f:
        if method_name == "lio_livox":
            f.write("%YAML:1.0\n")
        yaml.dump(data, f, default_flow_style=False, indent=2, sort_keys=False)


def inject_cpp_params(master_cpp, target_cpp, params):
    with open(master_cpp, 'r') as f:
        content = f.read()
    for key, value in params.items():
        pattern = r"^(?!//)(.*extern\s+const\s+\w+\s+" + key + r"\s*=\s*)[^;]+;"
        replacement = rf"\g<1>{value};"
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    with open(target_cpp, 'w') as f:
        f.write(content)


def recompile_workspace(package_name):
    ws_dir = get_ws_root()
    cmd = f"catkin_make --pkg {package_name}"
    print(f">>> Recompilando o workspace para o {package_name}...")
    subprocess.run(cmd, cwd=ws_dir, shell=True, check=True)


def get_best_params(study_csv, tunable_params):
    """Lê o CSV do estudo e retorna os params_* do melhor trial válido."""
    if not os.path.exists(study_csv):
        print(f"[ERRO] CSV não encontrado: {study_csv}")
        return None

    df = pd.read_csv(study_csv)
    if "state" in df.columns:
        df = df[df["state"] == "COMPLETE"]
    df = df[df["value"].notna()]
    df = df[df["value"] != PENALIDADE_TRIAL_INVALIDO]
    df = df[df["value"] != float("inf")]

    if df.empty:
        print("[ERRO] Nenhum trial válido encontrado nesse CSV (todos com penalidade/erro).")
        return None

    best_row = df.nsmallest(1, "value").iloc[0]
    params = {}
    for p in tunable_params:
        col = f"params_{p}"
        if col not in df.columns:
            continue
        val = best_row[col]
        # Converte para tipo nativo do Python (evita numpy.int64/float64 quebrando o yaml.dump)
        if float(val).is_integer():
            params[p] = int(val)
        else:
            params[p] = float(val)
    return params, float(best_row["value"]), int(best_row["number"])


def run_and_measure(root_dir, config, method_name, dataset_bag, params, label, out_dir):
    """Injeta os params, roda o método com monitoramento de recursos, retorna as métricas."""
    master_path = resolve_path(config['config_master'], root_dir)
    target_path = resolve_path(config['config_target'], root_dir)

    if config['config_type'] == 'yaml_runtime':
        inject_yaml_params(master_path, target_path, method_name, params)
    elif config['config_type'] == 'cpp_compile_time':
        inject_cpp_params(master_path, target_path, params)
        recompile_workspace(config['package'])

    odom_out = os.path.join(out_dir, f"{label}_odom.tum")
    resource_out = os.path.join(out_dir, f"{label}_resource_stats.json")

    run_cmd = (
        f"python3 {os.path.join(root_dir, 'scripts', 'run_method.py')} "
        f"--package {config['package']} "
        f"--launch {config['launch_file']} "
        f"--bag {dataset_bag} "
        f"--odom_topic {config['odom_topic']} "
        f"--output_tum {odom_out} "
        f"--resource_out {resource_out}"
    )
    print(f"\n>>> Rodando '{label}' para medição de custo...")
    subprocess.run(run_cmd, shell=True, check=True)

    stats = {}
    if os.path.exists(resource_out):
        with open(resource_out) as f:
            stats = json.load(f)
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Mede custo computacional só do baseline e do melhor trial."
    )
    parser.add_argument("--method", required=True)
    parser.add_argument("--sensor", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--sampler", required=True, choices=["tpe", "cmaes", "gp"])
    parser.add_argument("--only", choices=["baseline", "best"], default=None,
                         help="Rodar só um dos dois (default: os dois)")
    parser.add_argument("--results-dir", default=os.path.expanduser("~/results"))
    args = parser.parse_args()

    root_dir = get_project_root()
    registry_path = os.path.join(root_dir, "methods", "registry.yaml")
    with open(registry_path) as f:
        registry = yaml.safe_load(f)

    if args.method not in registry:
        print(f"[ERRO] Método '{args.method}' não encontrado no registry.yaml")
        return
    config = registry[args.method]

    dataset_bag = os.path.join(root_dir, "datasets", f"{args.dataset}.bag")
    base_dir = os.path.join(args.results_dir, args.method, args.sensor, args.dataset)
    study_csv = os.path.join(base_dir, f"study_{args.sampler}.csv")
    out_dir = os.path.join(base_dir, "cost")
    os.makedirs(out_dir, exist_ok=True)

    results = {}

    if args.only in (None, "baseline"):
        baseline_params = config['baseline']
        stats = run_and_measure(root_dir, config, args.method, dataset_bag,
                                 baseline_params, "baseline", out_dir)
        results["baseline"] = {"params": baseline_params, "stats": stats}

    if args.only in (None, "best"):
        best = get_best_params(study_csv, config['tunable_params'])
        if best is None:
            print("[AVISO] Pulando medição do melhor trial (sem dados válidos).")
        else:
            best_params, best_rmse, best_trial_num = best
            print(f"Melhor trial encontrado: #{best_trial_num} (RMSE={best_rmse:.4f})")
            stats = run_and_measure(root_dir, config, args.method, dataset_bag,
                                     best_params, "best", out_dir)
            results["best"] = {
                "params": best_params, "rmse": best_rmse,
                "trial_number": best_trial_num, "stats": stats
            }

    summary_path = os.path.join(out_dir, f"custo_{args.sampler}.json")
    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print("\n" + "=" * 60)
    print(f"Resumo salvo em: {summary_path}")
    for label, data in results.items():
        s = data.get("stats", {})
        print(f"  {label}: tempo={s.get('wall_time_sec', 'N/A')}s  "
              f"mem_pico={s.get('peak_mem_mb', 'N/A')}MB  cpu_médio={s.get('avg_cpu_pct', 'N/A')}%")
    print("=" * 60)


if __name__ == "__main__":
    main()