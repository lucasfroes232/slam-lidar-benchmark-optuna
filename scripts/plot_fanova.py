#!/usr/bin/env python3
"""
plot_fanova.py

Gera o gráfico de importância de hiperparâmetros (fANOVA) para um
método/sensor/dataset/sampler específico, a partir do estudo Optuna
persistido em SQLite. Exporta como HTML (contorna a falta de display
gráfico no container).

Uso:
    python3 plot_fanova.py --method lio_livox --sensor horizon --dataset forest02_straight --sampler cmaes
    python3 plot_fanova.py --method fast_lio --sensor ouster128 --dataset forest02_straight --sampler tpe
"""

import os
import argparse
import optuna
import optuna.visualization as vis


def main():
    parser = argparse.ArgumentParser(
        description="Gráfico fANOVA de importância de hiperparâmetros."
    )
    parser.add_argument("--method", required=True,
                         help="Nome do método (ex: fast_lio, lio_livox, lego_loam)")
    parser.add_argument("--sensor", required=True,
                         help="Nome da pasta de config/sensor (ex: ouster128, horizon, velodyne16_utility)")
    parser.add_argument("--dataset", required=True,
                         help="Nome do dataset (ex: forest02_straight)")
    parser.add_argument("--sampler", required=True, choices=["tpe", "cmaes", "gp"],
                         help="Sampler cujo estudo será analisado")
    parser.add_argument("--results-dir", default=os.path.expanduser("~/results"),
                         help="Diretório raiz de resultados (default: ~/results)")
    parser.add_argument("--out", default=None,
                         help="Caminho de saída do HTML (default: ~/results/fanova/{dataset}/importancia_fanova_{method}_{sampler}.html)")
    args = parser.parse_args()

    db_path = os.path.join(args.results_dir, args.method, args.sensor, args.dataset,
                            f"study_{args.sampler}.db")

    if not os.path.exists(db_path):
        print(f"[ERRO] Banco de dados não encontrado em: {db_path}")
        return

    storage_url = f"sqlite:///{db_path}"

    estudos_salvos = optuna.get_all_study_summaries(storage=storage_url)
    if not estudos_salvos:
        print("[ERRO] O banco de dados foi encontrado, mas está vazio.")
        return

    nome_do_estudo = estudos_salvos[0].study_name
    print(f"Carregando histórico do estudo: '{nome_do_estudo}'...")

    study = optuna.load_study(study_name=nome_do_estudo, storage=storage_url)

    fig = vis.plot_param_importances(study)
    fig.update_layout(
        title=f"Importância de Hiperparâmetros (fANOVA) — {args.method} / {args.sampler.upper()}",
        title_x=0.5,
        font=dict(size=14)
    )

    if args.out:
        caminho_final = os.path.expanduser(args.out)
    else:
        out_dir = os.path.join(args.results_dir, "fanova", args.dataset)
        os.makedirs(out_dir, exist_ok=True)
        caminho_final = os.path.join(out_dir, f"importancia_fanova_{args.method}_{args.sampler}.html")

    os.makedirs(os.path.dirname(caminho_final), exist_ok=True)
    fig.write_html(caminho_final)

    print("=" * 60)
    print(f"Sucesso! Gráfico salvo em: {caminho_final}")
    print("Vá no explorador de arquivos do VS Code, clique com o botão direito")
    print(f"no arquivo e abra no seu navegador!")
    print("=" * 60)


if __name__ == "__main__":
    main()