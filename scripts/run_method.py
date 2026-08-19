#!/usr/bin/env python3
import os
import time
import json
import argparse
import subprocess
import signal
import threading

try:
    import psutil
except ImportError:
    psutil = None


def get_ros_env():
    """Ambiente com ROS_MASTER_URI/HOSTNAME fixos, evitando resolução inconsistente de hostname."""
    env = os.environ.copy()
    env["ROS_MASTER_URI"] = "http://localhost:11311"
    env["ROS_HOSTNAME"] = "localhost"
    env.pop("ROS_IP", None)
    return env


def cleanup_ros_processes():
    """Mata qualquer processo ROS órfão de execuções anteriores."""
    for pattern in ["roslaunch", "roscore", "rosmaster", "rosbag","rosout", "rviz"]:
        subprocess.run(f"pkill -9 -f {pattern}", shell=True,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)


def run_cmd(cmd, bg=False):
    """Roda um comando no terminal. Retorna o processo se bg=True."""
    print(f"[RUN] {cmd}")
    env = get_ros_env()
    if bg:
        return subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid, env=env)
    else:
        subprocess.run(cmd, shell=True, check=True, env=env)


def wait_for_roscore(timeout=30):
    """Espera o roscore estar totalmente pronto, checando o parâmetro /run_id."""
    env = get_ros_env()
    for _ in range(timeout * 2):
        result = subprocess.run(
            "rosparam get /run_id", shell=True, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        if result.returncode == 0:
            time.sleep(0.5)
            return
        time.sleep(0.5)
    raise RuntimeError("roscore não respondeu a tempo (/run_id nunca apareceu)")


def monitor_resources(pid, stop_event, interval=1.0):
    """Monitora CPU e memória via cálculo manual de delta (cpu_times), pois
    psutil.cpu_percent() é pouco confiável em containers Docker Desktop/WSL2."""
    samples_cpu = []
    samples_mem = []
    if psutil is None:
        return {"peak_mem_mb": 0, "avg_cpu_pct": 0}

    try:
        root_proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return {"peak_mem_mb": 0, "avg_cpu_pct": 0}

    num_cpus = psutil.cpu_count() or 1
    prev = {}

    def get_all_procs():
        try:
            children = root_proc.children(recursive=True)
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            children = []
        return [root_proc] + children

    while not stop_event.is_set():
        now = time.time()
        total_cpu_time = 0.0
        total_mem = 0.0

        for p in get_all_procs():
            try:
                ct = p.cpu_times()
                total_cpu_time += ct.user + ct.system
                total_mem += p.memory_info().rss
            except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
                continue

        if "prev" in prev:
            prev_time, prev_ts = prev["prev"]
            elapsed_wall = now - prev_ts
            elapsed_cpu = total_cpu_time - prev_time
            if elapsed_wall > 0:
                cpu_pct = (elapsed_cpu / elapsed_wall) * 100
                samples_cpu.append(max(0.0, cpu_pct))

        prev["prev"] = (total_cpu_time, now)
        samples_mem.append(total_mem / (1024 * 1024))

        stop_event.wait(interval)

    return {
        "peak_mem_mb": max(samples_mem) if samples_mem else 0,
        "avg_cpu_pct": sum(samples_cpu) / len(samples_cpu) if samples_cpu else 0,
    }


def main():
    parser = argparse.ArgumentParser(description="Inicia o SLAM, toca o bag e grava a odometria.")
    parser.add_argument("--package", required=True, help="Pacote ROS (ex: fast_lio)")
    parser.add_argument("--launch", required=True, help="Arquivo de launch")
    parser.add_argument("--bag", required=True, help="Caminho para o dataset .bag")
    parser.add_argument("--odom_topic", required=True, help="Tópico da odometria para gravar")
    parser.add_argument("--output_tum", required=True, help="Caminho final para o arquivo .tum")
    parser.add_argument("--resource_out", default=None,
                         help="Caminho para salvar métricas de custo computacional (JSON). Opcional.")
    args = parser.parse_args()

    cleanup_ros_processes()

    temp_bag = "/tmp/temp_odom.bag"
    if os.path.exists(temp_bag):
        os.remove(temp_bag)

    #Inicia o roscore
    roscore_p = run_cmd("roscore", bg=True)
    wait_for_roscore()

    slam_p = None
    record_p = None
    resource_stats = {}
    stop_event = threading.Event()
    monitor_thread = None
    start_time = None

    try:
        #Inicia o algoritmo de SLAM
        slam_cmd = f"roslaunch {args.package} {args.launch} rviz:=true"
        slam_p = run_cmd(slam_cmd, bg=True)
        time.sleep(3)  # Aguarda os nós do SLAM inicializarem

        start_time = time.time()
        if args.resource_out and psutil is not None:
            monitor_thread = threading.Thread(
                target=lambda: resource_stats.update(monitor_resources(slam_p.pid, stop_event))
            )
            monitor_thread.start()

        # Inicia a gravação da odometria em um bag temporário
        record_cmd = f"rosbag record -O {temp_bag} {args.odom_topic}"
        record_p = run_cmd(record_cmd, bg=True)
        time.sleep(2)

        # Toca o dataset bag (Processo Bloqueante)
        play_cmd = f"rosbag play {args.bag} --clock"
        print(">>> Tocando o dataset... Aguarde terminar.")
        subprocess.run(play_cmd, shell=True, check=True)
        print(">>> Dataset finalizado!")

    finally:
        stop_event.set()
        if monitor_thread:
            monitor_thread.join(timeout=5)
        if start_time:
            resource_stats["wall_time_sec"] = time.time() - start_time

        print(">>> Encerrando o sistema ROS...")
        run_cmd("rosnode kill -a", bg=False)
        time.sleep(2)

        # SIGINT -> SIGTERM -> SIGKILL
        for p in [record_p, slam_p, roscore_p]:
            if p is None:
                continue
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGINT)
            except Exception:
                pass
        time.sleep(3)

        for p in [record_p, slam_p, roscore_p]:
            if p is None:
                continue
            try:
                if p.poll() is None:
                    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            except Exception:
                pass
        time.sleep(3)

        for p in [record_p, slam_p, roscore_p]:
            if p is None:
                continue
            try:
                if p.poll() is None:
                    os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            except Exception:
                pass
        time.sleep(1)

        # garante que nada de ROS fica pendurado
        cleanup_ros_processes()

    # bag gravado para TUM
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bag_to_tum_cmd = (
        f"python2 {script_dir}/bag_to_tum.py "
        f"--bag {temp_bag} --topic {args.odom_topic} --out {args.output_tum}"
    )
    run_cmd(bag_to_tum_cmd)

    if args.resource_out:
        with open(args.resource_out, 'w') as f:
            json.dump(resource_stats, f, indent=2)
        print(f">>> Métricas de custo salvas em: {args.resource_out}")

    print(f">>> Sucesso! Odometria salva em: {args.output_tum}")


if __name__ == "__main__":
    main()