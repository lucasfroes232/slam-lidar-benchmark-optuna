#!/usr/bin/env python3
import json
import argparse
from evo.tools import file_interface
from evo.core import sync, metrics
import numpy as np

def evaluate(gt_path, est_path, offset=None, save_plot=None, max_diff=0.1, skip_seconds=0.0):
    traj_ref = file_interface.read_tum_trajectory_file(gt_path)
    traj_est = file_interface.read_tum_trajectory_file(est_path)

    # 1. Calcula o offset PRIMEIRO (para alinhar T=0 com T=0 antes de cortar)
    if offset is None:
        offset = traj_ref.timestamps[0] - traj_est.timestamps[0]
        print(f"Aviso: Offset não fornecido. Usando cálculo dinâmico: {offset:.3f} s")
    else:
        print(f"Usando o offset informado: {offset:.3f} s")

    # 2. Aplica o offset
    traj_est.timestamps += offset

    # 3. DEPOIS corta os N primeiros segundos da trajetória estimada
    if skip_seconds > 0:
        cutoff = traj_est.timestamps[0] + skip_seconds
        mask = traj_est.timestamps >= cutoff
        traj_est.reduce_to_ids(np.where(mask)[0])

    # Sincroniza e alinha
    traj_ref_sync, traj_est_sync = sync.associate_trajectories(
        traj_ref, traj_est, max_diff=max_diff)
    
    # Alinhamento Umeyama tradicional (você pode desativar se a trajetória entortar)
    traj_est_sync.align(traj_ref_sync, correct_scale=False)

    # Calcula APE
    ape_metric = metrics.APE(metrics.PoseRelation.translation_part)
    ape_metric.process_data((traj_ref_sync, traj_est_sync))

    stats = {
        "rmse": ape_metric.get_statistic(metrics.StatisticsType.rmse),
        "mean": ape_metric.get_statistic(metrics.StatisticsType.mean),
        "median": ape_metric.get_statistic(metrics.StatisticsType.median),
        "max": ape_metric.get_statistic(metrics.StatisticsType.max),
        "min": ape_metric.get_statistic(metrics.StatisticsType.min),
        "std": ape_metric.get_statistic(metrics.StatisticsType.std),
        "offset_used": offset,
        "n_matched": len(traj_ref_sync.timestamps),
    }

    if save_plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 10), dpi=200)

        xyz_ref = traj_ref_sync.positions_xyz
        xyz_est = traj_est_sync.positions_xyz

        # 1. Fundo e Grade (Estilo Seaborn limpo)
        ax.set_facecolor('#EAEAF2')
        ax.grid(True, color='white', linewidth=1.5, linestyle='-')
        for spine in ax.spines.values():
            spine.set_visible(False)

        # 2. Ground Truth: Cinza-azulado elegante
        ax.plot(xyz_ref[:, 0], xyz_ref[:, 1], color='#636E72', linestyle='--', 
                linewidth=2.5, zorder=2)

        # 3. Trajetória Estimada: Azul vibrante natural
        ax.plot(xyz_est[:, 0], xyz_est[:, 1], color='#1E88E5', linestyle='-', 
                linewidth=2.5, zorder=3)

        # 4. Símbolos de Começo e Fim (Cores ricas e orgânicas)
        ax.scatter(xyz_ref[0, 0], xyz_ref[0, 1], color='#43A047', s=130, marker='o', 
                   zorder=4, edgecolors='white', linewidths=1.5)
        ax.scatter(xyz_ref[-1, 0], xyz_ref[-1, 1], color='#8E24AA', s=130, marker='X', 
                   zorder=4, edgecolors='white', linewidths=1.5)

        # 5. Textos dos Eixos (Mantendo a notação matemática limpa)
        ax.set_xlabel(r'$x$ (m)', fontsize=12)
        ax.set_ylabel(r'$y$ (m)', fontsize=12)
        
        # 6. Exibe apenas o RMSE discretamente no canto
        ax.text(0.02, 0.98, f"RMSE: {stats['rmse']:.4f} m", 
                transform=ax.transAxes, fontsize=12, fontweight='bold', color='#333333',
                verticalalignment='top', bbox=dict(boxstyle='round,pad=0.4', facecolor='#FFFFFF', alpha=0.9, edgecolor='none'))
        
        # Escala igual (Obrigatório para visualização correta de mapas)
        ax.set_aspect('equal', adjustable='box')

        fig.tight_layout()
        fig.savefig(save_plot, bbox_inches='tight', dpi=300) 
        plt.close(fig)
        print(f"Plot salvo em: {save_plot}")
        
    return stats

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Avaliação de SLAM usando EVO com Offset customizado.")
    parser.add_argument("gt", help="Caminho do Ground Truth (TUM)")
    parser.add_argument("est", help="Caminho da Odometria Estimada (TUM)")
    parser.add_argument("--offset", type=str, default="dynamic", help="Offset de tempo ('dynamic' ou valor numérico)")
    parser.add_argument("--plot", help="Caminho para salvar o gráfico .png (opcional)")
    parser.add_argument("--skip_seconds", type=float, default=0.0, help="Descarta os N primeiros segundos da trajetória estimada (instabilidade de inicialização)")
    
    args = parser.parse_args()

    # Lida com a string vinda do bash. Se for 'dynamic' ou 'none', passa None para a função.
    offset_val = None
    if args.offset and args.offset.lower() not in ["none", "dynamic"]:
        offset_val = float(args.offset)

    stats = evaluate(args.gt, args.est, offset=offset_val, save_plot=args.plot, skip_seconds=args.skip_seconds)
    print(json.dumps(stats, indent=2))