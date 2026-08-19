#!/usr/bin/env python3
import os
import re
import time
import yaml
import json
import optuna
import shutil
import argparse
import subprocess
from optuna.samplers import TPESampler, CmaEsSampler
from optuna.integration import SkoptSampler

# Penalidade finita para trials inválidos (NÃO usar float('inf') -- quebra o sampler GP,
# que exige valores finitos para ajustar o GaussianProcessRegressor)
PENALIDADE_TRIAL_INVALIDO = 999.0


def get_project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def get_ws_src_root():
    return "/root/slam_ws/src"


def get_ws_root():
    return "/root/slam_ws"


def resolve_path(relative_path, root_dir):
    """Resolve caminhos do registry.yaml, tratando 'src/' como pertencente ao workspace catkin."""
    if relative_path.startswith("src/"):
        return os.path.join(get_ws_src_root(), relative_path[len("src/"):])
    return os.path.join(root_dir, relative_path)


def inject_yaml_params(master_yaml, target_yaml, method_name, params):
    """Lê o YAML mestre, injeta os novos parâmetros e salva no destino."""
    with open(master_yaml, 'r') as f:
        content = f.read()

    # Remove a diretiva do OpenCV FileStorage (%YAML:1.0), incompatível com PyYAML padrão
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
        # Métodos cujo config original usa sintaxe OpenCV FileStorage (%YAML:1.0)
        if method_name in ("lio_livox",):
            f.write("%YAML:1.0\n")
        yaml.dump(data, f, default_flow_style=False, indent=2, sort_keys=False)


def inject_cpp_params(master_cpp, target_cpp, params):
    """Usa Regex para substituir valores em variáveis globais no C++."""
    with open(master_cpp, 'r') as f:
        content = f.read()

    for key, value in params.items():
        pattern = r"^(?!//)(.*extern\s+const\s+\w+\s+" + key + r"\s*=\s*)[^;]+;"
        replacement = rf"\g<1>{value};"
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

    with open(target_cpp, 'w') as f:
        f.write(content)


def recompile_workspace(package_name="lego_loam"):
    ws_dir = get_ws_root()
    cmd = f"catkin_make --pkg {package_name}"
    print(f">>> Recompilando o workspace para o {package_name}...")
    start = time.time()
    subprocess.run(cmd, cwd=ws_dir, shell=True, check=True)
    return time.time() - start


def objective(trial, method_name, config, dataset_bag, gt_tum, sampler_name):
    study = trial.study
    root_dir = get_project_root()

    # Preparar pastas do Trial separadas por motor (sampler) e por dataset
    config_name = os.path.splitext(os.path.basename(config['config_master']))[0]
    dataset_name = os.path.splitext(os.path.basename(dataset_bag))[0]
    trial_dir = os.path.join(root_dir, "results", method_name, config_name, dataset_name,
                              sampler_name, f"trial_{trial.number:04d}")
    os.makedirs(trial_dir, exist_ok=True)

    # Sugerir Parâmetros 
    suggested_params = {}
    for param in config['tunable_params']:
        base_val = config['baseline'][param]
        lo, hi = config['search_space'][param]
        if isinstance(base_val, int):
            suggested_params[param] = int(trial.suggest_int(param, lo, hi))
        elif isinstance(base_val, float):
            suggested_params[param] = float(trial.suggest_float(param, lo, hi))

    # Injetar Parâmetros
    master_path = resolve_path(config['config_master'], root_dir)
    target_path = resolve_path(config['config_target'], root_dir)

    if config['config_type'] == 'yaml_runtime':
        inject_yaml_params(master_path, target_path, method_name, suggested_params)
        shutil.copy(target_path, os.path.join(trial_dir, "config_used.yaml"))

    elif config['config_type'] == 'cpp_compile_time':
        inject_cpp_params(master_path, target_path, suggested_params)
        recompile_workspace(config['package'])
        shutil.copy(target_path, os.path.join(trial_dir, "utility_used.h"))

   # Executar o SLAM (com retry automático em caso de falha de infraestrutura ROS)
    odom_out = os.path.join(trial_dir, "odom.tum")
    run_cmd = (
        f"python3 {os.path.join(root_dir, 'scripts', 'run_method.py')} "
        f"--package {config['package']} "
        f"--launch {config['launch_file']} "
        f"--bag {dataset_bag} "
        f"--odom_topic {config['odom_topic']} "
        f"--output_tum {odom_out}"
    )

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            subprocess.run(run_cmd, shell=True, check=True)
            break
        except subprocess.CalledProcessError as e:
            print(f"*** run_method.py falhou (tentativa {attempt}/{max_retries}): {e} ***")
            # limpeza extra + espera antes de tentar de novo
            subprocess.run(
                "pkill -9 -f roslaunch; pkill -9 -f roscore; pkill -9 -f rosmaster; "
                "pkill -9 -f rosbag; pkill -9 -f rosout; pkill -9 -f rviz; "
                "pkill -9 -f livox_laserMapping; pkill -9 -f livox_scanRegistration; pkill -9 -f livox_repub",
                shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            time.sleep(10)
            if attempt == max_retries:
                print("*** Esgotadas as tentativas. Penalizando o trial. ***")
                return PENALIDADE_TRIAL_INVALIDO

    # Avaliar o resultado gerando a imagem temporariamente
    plot_out = os.path.join(trial_dir, "baseline_ape.png")
    eval_cmd = (
        f"python3 {os.path.join(root_dir, 'scripts', 'evaluate.py')} "
        f"{gt_tum} {odom_out} "
        f"--offset {config['time_offset']} "
        f"--plot {plot_out}"
    )
    try:
        result = subprocess.run(
            eval_cmd, shell=True, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
        )
    except subprocess.CalledProcessError as e:
        print(f"*** Trial falhou na avaliação (evaluate.py): {e.stderr} ***")
        return PENALIDADE_TRIAL_INVALIDO  # penaliza o trial, mas não derruba o estudo

    # Extrair estatísticas
    stats_str = result.stdout[result.stdout.find('{'):]
    stats = json.loads(stats_str)
    rmse = stats['rmse']

    with open(os.path.join(trial_dir, "ape_stats.json"), 'w') as f:
        json.dump(stats, f, indent=2)

    min_matched = config.get('min_matched_poses', 60)  # fallback de segurança
    if stats['n_matched'] < min_matched:
        print(f"*** Trial descartado: apenas {stats['n_matched']} poses casadas (mínimo: {min_matched}) ***")
        if os.path.exists(plot_out):
            os.remove(plot_out)
        return PENALIDADE_TRIAL_INVALIDO

    #Lógica de preservação de disco: Deleta a imagem se não for um recorde
    try:
        best_rmse_so_far = study.best_value
    except ValueError:
        best_rmse_so_far = float('inf')  # Primeiro trial (baseline) -- comparação, não retorno

    if rmse >= best_rmse_so_far:
        if os.path.exists(plot_out):
            os.remove(plot_out)
    else:
        print(f"*** NOVO ÓTIMO ENCONTRADO! RMSE: {rmse:.4f} - Imagem salva. ***")

    return rmse


def main():
    parser = argparse.ArgumentParser(description="Otimização Optuna para SLAM.")
    parser.add_argument("--method", required=True, help="Nome do método (ex: fast_lio, lego_loam)")
    parser.add_argument("--trials", type=int, default=30, help="Número de iterações")
    parser.add_argument("--sampler", choices=['tpe', 'gp', 'cmaes'], default='tpe', help="Motor de otimização")
    parser.add_argument("--dataset", required=True, help="Nome do dataset, sem extensão (ex: forest01_st_square_2022-02-08-23-14-55)")
    args = parser.parse_args()

    root_dir = get_project_root()
    registry_path = os.path.join(root_dir, "methods", "registry.yaml")

    with open(registry_path, 'r') as f:
        registry = yaml.safe_load(f)

    if args.method not in registry:
        print(f"Erro: Método '{args.method}' não encontrado no registry.yaml")
        return

    config = registry[args.method]
    dataset_bag = os.path.join(root_dir, "datasets", f"{args.dataset}.bag")
    gt_tum = os.path.join(root_dir, "datasets", "ground_truth", f"gt_{args.dataset}.tum")

    if args.sampler == 'tpe':
        sampler = TPESampler()
    elif args.sampler == 'gp':
        sampler = SkoptSampler(skopt_kwargs={"base_estimator": "GP", "n_initial_points": 5})
    elif args.sampler == 'cmaes':
        sampler = CmaEsSampler()

    # Inicia o Estudo (persistido em SQLite, separado por método/config/dataset/sampler)
    config_name = os.path.splitext(os.path.basename(config['config_master']))[0]
    dataset_name = os.path.splitext(os.path.basename(dataset_bag))[0]
    study_name = f"{args.method}_{config_name}_{dataset_name}_{args.sampler}"

    db_dir = os.path.join(root_dir, "results", args.method, config_name, dataset_name)
    os.makedirs(db_dir, exist_ok=True)
    storage_path = f"sqlite:///{os.path.join(db_dir, f'study_{args.sampler}.db')}"

    study = optuna.create_study(
        study_name=study_name,
        storage=storage_path,
        direction="minimize",
        sampler=sampler,
        load_if_exists=True
    )

    # ENFILEIRA O BASELINE COMO TRIAL 0000 (só se o estudo ainda não tiver nenhum trial)
    if 'baseline' in config and len(study.trials) == 0:
        print(f"Enfileirando parâmetros baseline para o {args.method} (Trial 0000)...")
        study.enqueue_trial(config['baseline'])

    print(f"\n=== Iniciando Otimização ({args.sampler.upper()}) para: {args.method} | dataset: {args.dataset} ===")

    study.optimize(lambda t: objective(t, args.method, config, dataset_bag, gt_tum, args.sampler), n_trials=args.trials)

    print("\n=== Otimização Finalizada ===")
    print("Melhor Trial:")
    print(study.best_trial)

    study_csv = os.path.join(root_dir, "results", args.method, config_name, dataset_name, f"study_{args.sampler}.csv")
    df = study.trials_dataframe()
    df.to_csv(study_csv, index=False)
    print(f"CSV completo salvo em: {study_csv}")


if __name__ == "__main__":
    main()