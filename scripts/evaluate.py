#!/usr/bin/env python3
import json
import argparse
from evo.tools import file_interface
from evo.core import sync, metrics

def evaluate(gt_path, est_path, offset=None, save_plot=None, max_diff=0.05):
    traj_ref = file_interface.read_tum_trajectory_file(gt_path)
    traj_est = file_interface.read_tum_trajectory_file(est_path)

    # Se você NÃO passar o offset, ele avisa e usa o dinâmico (como backup)
    if offset is None:
        offset = traj_ref.timestamps[0] - traj_est.timestamps[0]
        print(f"Aviso: Offset não fornecido. Usando cálculo dinâmico: {offset:.3f} s")
    else:
        print(f"Usando o offset informado via terminal: {offset:.3f} s")

    # Aplica o offset
    traj_est.timestamps += offset

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
        
        # 6. Exibe apenas o RMSE discretamente no canto, já que removemos a legenda
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
    parser.add_argument("--offset", type=float, help="Offset de tempo hardcoded para este método")
    parser.add_argument("--plot", help="Caminho para salvar o gráfico .png (opcional)")

    args = parser.parse_args()

    stats = evaluate(args.gt, args.est, offset=args.offset, save_plot=args.plot)
    print(json.dumps(stats, indent=2))