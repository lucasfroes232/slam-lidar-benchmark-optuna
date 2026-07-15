#!/usr/bin/env python3
import os
import time
import argparse
import subprocess
import signal

def get_ros_env():
    """Ambiente com ROS_MASTER_URI/HOSTNAME fixos, evitando resolução inconsistente de hostname."""
    env = os.environ.copy()
    env["ROS_MASTER_URI"] = "http://localhost:11311"
    env["ROS_HOSTNAME"] = "localhost"
    env.pop("ROS_IP", None)
    return env

def cleanup_ros_processes():
    """Mata qualquer processo ROS órfão de execuções anteriores."""
    for pattern in ["roslaunch", "roscore", "rosmaster", "rosbag"]:
        subprocess.run(f"pkill -9 -f {pattern}", shell=True,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)

def run_cmd(cmd, bg=False):
    """Roda um comando no terminal. Retorna o processo se bg=True."""
    print(f"[RUN] {cmd}")
    env = get_ros_env()
    if bg:
        return subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid, env=env)
    else:
        subprocess.run(cmd, shell=True, check=True, env=env)

def wait_for_roscore(timeout=15):
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

def main():
    parser = argparse.ArgumentParser(description="Inicia o SLAM, toca o bag e grava a odometria.")
    parser.add_argument("--package", required=True, help="Pacote ROS (ex: fast_lio)")
    parser.add_argument("--launch", required=True, help="Arquivo de launch")
    parser.add_argument("--bag", required=True, help="Caminho para o dataset .bag")
    parser.add_argument("--odom_topic", required=True, help="Tópico da odometria para gravar")
    parser.add_argument("--output_tum", required=True, help="Caminho final para o arquivo .tum")
    args = parser.parse_args()

    cleanup_ros_processes()
    # Nomes de arquivos temporários
    temp_bag = "/tmp/temp_odom.bag"
    if os.path.exists(temp_bag):
        os.remove(temp_bag)



    # 1. Inicia o roscore
    roscore_p = run_cmd("roscore", bg=True)
    wait_for_roscore()  # Aguarda roscore subir de verdade (polling, não sleep fixo)

    slam_p = None
    record_p = None

    try:
        # 2. Inicia o algoritmo de SLAM
        slam_cmd = f"roslaunch {args.package} {args.launch} rviz:=false"
        slam_p = run_cmd(slam_cmd, bg=True)
        time.sleep(5)  # Aguarda os nós do SLAM inicializarem

        # 3. Inicia a gravação da odometria em um bag temporário
        record_cmd = f"rosbag record -O {temp_bag} {args.odom_topic}"
        record_p = run_cmd(record_cmd, bg=True)
        time.sleep(2)

        # 4. Toca o dataset bag (Processo Bloqueante)
        play_cmd = f"rosbag play {args.bag} --clock"
        print(">>> Tocando o dataset... Aguarde terminar.")
        subprocess.run(play_cmd, shell=True, check=True)
        print(">>> Dataset finalizado!")

    finally:
        # 5. Mata os processos graciosamente na ordem inversa
        print(">>> Encerrando o sistema ROS...")
        run_cmd("rosnode kill -a", bg=False)  # Mata nós do ROS suavemente
        time.sleep(2)

        # Garante que os subprocessos morreram usando o Group ID
        for p in [record_p, slam_p, roscore_p]:
            if p is None:
                continue
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGINT)
            except Exception:
                pass
        time.sleep(2)

    # 6. Converte o bag gravado para TUM (flags nomeadas, sem offset — isso fica pro evaluate.py)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bag_to_tum_cmd = (
        f"python2 {script_dir}/bag_to_tum.py "
        f"--bag {temp_bag} --topic {args.odom_topic} --out {args.output_tum}"
    )
    run_cmd(bag_to_tum_cmd)

    print(f">>> Sucesso! Odometria salva em: {args.output_tum}")

if __name__ == "__main__":
    main()