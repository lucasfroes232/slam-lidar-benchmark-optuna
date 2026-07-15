#!/usr/bin/env python3
"""
run_full_benchmark.py

Roda TODOS os métodos (fast_lio, lio_livox, lego_loam) x TODOS os samplers
(tpe, cmaes, gp) em sequência, um atrás do outro, sem travar a execução
inteira se uma combinação individual falhar.

Pensado para rodar em background durante a noite via nohup:

    nohup python3 ~/scripts/run_full_benchmark.py --trials 50 > ~/results/overnight_run.log 2>&1 &

Gera:
- Um log geral (via stdout, redirecionado pelo nohup)
- Um log individual por combinação em ~/results/_logs/{method}_{sampler}.log
- Um resumo final em ~/results/_logs/summary.json com status de cada combinação
"""

import os
import sys
import json
import time
import argparse
import subprocess
from datetime import datetime, timedelta

METHODS = ["fast_lio", "lio_livox", "lego_loam"]
SAMPLERS = ["tpe", "cmaes", "gp"]


def get_project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_combo(method, sampler, trials, root_dir, logs_dir):
    """Roda uma combinação método+sampler, capturando output em arquivo próprio."""
    log_path = os.path.join(logs_dir, f"{method}_{sampler}.log")
    optimize_script = os.path.join(root_dir, "scripts", "optuna_optimize.py")

    cmd = [
        "python3", optimize_script,
        "--method", method,
        "--trials", str(trials),
        "--sampler", sampler,
    ]

    start = time.time()
    log(f">>> Iniciando: método={method} sampler={sampler} trials={trials}")

    with open(log_path, "w") as logfile:
        result = subprocess.run(cmd, stdout=logfile, stderr=subprocess.STDOUT)

    duration = time.time() - start
    duration_str = str(timedelta(seconds=int(duration)))

    if result.returncode == 0:
        log(f"    OK   método={method} sampler={sampler} duração={duration_str}")
        status = "success"
    else:
        log(f"    FALHOU método={method} sampler={sampler} "
            f"(exit code {result.returncode}) duração={duration_str} "
            f"-- ver log: {log_path}")
        status = "failed"

    return {
        "method": method,
        "sampler": sampler,
        "status": status,
        "exit_code": result.returncode,
        "duration_seconds": round(duration, 1),
        "log_file": log_path,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Roda todos os métodos x todos os samplers em sequência."
    )
    parser.add_argument("--trials", type=int, default=50,
                         help="Número de trials por combinação método+sampler")
    parser.add_argument("--methods", nargs="+", default=METHODS,
                         help=f"Métodos a rodar (default: {METHODS})")
    parser.add_argument("--samplers", nargs="+", default=SAMPLERS,
                         help=f"Samplers a rodar (default: {SAMPLERS})")
    args = parser.parse_args()

    root_dir = get_project_root()
    logs_dir = os.path.join(root_dir, "results", "_logs")
    os.makedirs(logs_dir, exist_ok=True)

    combos = [(m, s) for m in args.methods for s in args.samplers]

    log("=" * 60)
    log(f"BENCHMARK COMPLETO - {len(combos)} combinações")
    log(f"Métodos:  {args.methods}")
    log(f"Samplers: {args.samplers}")
    log(f"Trials por combinação: {args.trials}")
    log("=" * 60)

    overall_start = time.time()
    results = []

    for i, (method, sampler) in enumerate(combos, 1):
        log(f"\n--- Combinação {i}/{len(combos)} ---")
        r = run_combo(method, sampler, args.trials, root_dir, logs_dir)
        results.append(r)

        # Salva o resumo parcial a cada combinação concluída,
        # assim mesmo que o processo seja interrompido no meio da noite,
        # você já tem o progresso registrado até aquele ponto.
        summary_path = os.path.join(logs_dir, "summary.json")
        with open(summary_path, "w") as f:
            json.dump({
                "started_at": datetime.fromtimestamp(overall_start).isoformat(),
                "last_updated": datetime.now().isoformat(),
                "completed": i,
                "total": len(combos),
                "results": results,
            }, f, indent=2)

    total_duration = str(timedelta(seconds=int(time.time() - overall_start)))
    n_success = sum(1 for r in results if r["status"] == "success")
    n_failed = len(results) - n_success

    log("\n" + "=" * 60)
    log(f"BENCHMARK FINALIZADO em {total_duration}")
    log(f"Sucesso: {n_success}/{len(results)}   Falhas: {n_failed}/{len(results)}")
    if n_failed > 0:
        log("Combinações que falharam:")
        for r in results:
            if r["status"] == "failed":
                log(f"  - {r['method']} / {r['sampler']}  (ver {r['log_file']})")
    log("=" * 60)


if __name__ == "__main__":
    main()