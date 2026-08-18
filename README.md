# LiDAR SLAM Benchmark with Optuna

[![ROS Melodic](https://img.shields.io/badge/ROS-Melodic-22314E?logo=ros)](http://wiki.ros.org/melodic)
[![Python](https://img.shields.io/badge/Python-2%20%7C%203-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Optuna](https://img.shields.io/badge/Optuna-optimization-6B4FBB)](https://optuna.org/)
[![License](https://img.shields.io/badge/license-academic-lightgrey)](#license)

> Reproducible benchmarking of LiDAR-inertial SLAM systems in forest environments, with automated hyperparameter optimization and computational-cost analysis.

**Topics:** `SLAM` `LiDAR` `LiDAR-inertial odometry` `ROS` `forest robotics` `Optuna` `TPE` `Gaussian Process` `CMA-ES` `evo` `benchmarking`

<!-- MEDIA PLACEHOLDER 1
Put the GIF at: assets/fast_lio_forest01.gif
Suggested caption: FAST-LIO2 replay on the TIERS-FOREST01 dataset.
When the file is available, replace this comment with:
<p align="center">
    <img src="assets/fast_lio_forest01.gif" alt="FAST-LIO2 running on a forest dataset" width="850">
</p>
-->

## Overview

This repository evaluates SLAM methods under the geometric and sensing conditions of forest environments. The benchmark replays ROS bag files, injects trial-specific parameters, runs a SLAM launch file, converts the estimated odometry to TUM format, and minimizes aligned Absolute Pose Error (APE) RMSE with [Optuna](https://optuna.org/).

The experiment compares three samplers:

- **TPE**: Tree-structured Parzen Estimator
- **GP**: Gaussian Process Bayesian optimization
- **CMA-ES**: Covariance Matrix Adaptation Evolution Strategy

The evaluation workflow is:

```text
TIERS ROS bag + ground truth
                            |
                            v
     parameter injection / build
                            |
                            v
             ROS SLAM replay
                            |
                            v
             odometry -> TUM
                            |
                            v
            evo APE / RMSE score
                            |
                            v
             Optuna next trial
```

## Methods and status

The canonical method definitions, topics, parameter ranges, offsets, and pose thresholds are in [`methods/registry.yaml`](methods/registry.yaml).

| Registry key | Method | Coupling | Sensor/configuration | Status |
|---|---|---|---|---|
| `fast_lio` | FAST-LIO2 | Tightly coupled | Ouster128, runtime YAML | Ready for calibrated datasets |
| `lio_livox` | LIO-Livox | Tightly coupled | Livox Horizon, runtime YAML | Ready for calibrated datasets |
| `lego_loam` | LeGO-LOAM | Loosely coupled | Velodyne16, compile-time header | Ready; recompiles per trial |
| `loam_livox` | LOAM-Livox | Loosely coupled | Livox, runtime YAML | Ready for calibrated datasets |
| `liorf` | LIO-RF | Tightly coupled | Ouster128, runtime YAML | Registered, calibration pending |

`liorf` is intentionally not presented as reproducible yet: its registry entry still contains placeholder values for `time_offset` and `min_matched_poses`. Calibrate those values before running it in a benchmark study.

## Repository layout

```text
.
├── configs/                 # Master configurations and search-space inputs
├── datasets/                # Local ROS bags and TUM ground truth
├── methods/registry.yaml    # Method registry and optimization definitions
├── results/                 # Studies, trial outputs, logs, and analysis artifacts
├── scripts/
│   ├── run_method.py        # Run one method on one bag
│   ├── optuna_optimize.py   # Run one persisted Optuna study
│   ├── run_full_benchmark.py# Run method/sampler combinations
│   ├── bag_to_tum.py        # Convert recorded odometry to TUM
│   ├── evaluate.py          # Align and evaluate trajectories with evo
│   └── plot_*.py            # Convergence, fANOVA, and cost reports
├── src/                     # ROS/catkin workspaces and SLAM implementations
├── Dockerfile               # ROS Melodic development environment
└── README.md
```

## Environment

The supported environment is **Ubuntu 18.04 with ROS Melodic**, as defined by [`Dockerfile`](Dockerfile). The image installs ROS, PCL, the Livox SDK, GTSAM, Optuna, `evo`, and the Python dependencies used by the scripts.

The Dockerfile creates `/root/slam_ws` but does not copy this repository into the image. Mount the repository's `src/` directory into that workspace when starting the container:

```bash
docker build -t slam-lidar-benchmark-optuna:ros-melodic .

docker run --rm -it --network host \
    -v "$PWD:/workspace/repo" \
    -v "$PWD/src:/root/slam_ws/src" \
    -w /workspace/repo \
    slam-lidar-benchmark-optuna:ros-melodic
```

Inside the container, build the catkin workspace before running a study:

```bash
source /opt/ros/melodic/setup.bash
cd /root/slam_ws
catkin_make
source devel/setup.bash
cd /workspace/repo
```

The optimizer currently assumes the workspace path `/root/slam_ws`. Run the benchmark in an isolated ROS environment because cleanup uses broad ROS process termination commands.

If `catkin_make` reports that `GeographicLibConfig.cmake` cannot be found, rebuild the Docker image after pulling the current [`Dockerfile`](Dockerfile). LIO-RF requires `libgeographiclib-dev`, which is installed by the image:

```bash
docker build --no-cache -t slam-lidar-benchmark-optuna:ros-melodic .
```

Then start a new container and rebuild the workspace:

```bash
cd /root/slam_ws
catkin_make
source devel/setup.bash
rospack find fast_lio
```

The `rospack find` command should return `/root/slam_ws/src/FAST_LIO`. A successful `catkin_make` is required before launching `fast_lio`; sourcing `devel/setup.bash` alone does not create the `fastlio_mapping` executable.

## Datasets

The experiments use the TIERS multi-modal LiDAR dataset:

- [TIERS-FOREST01](https://github.com/tiers/tiers-lidars-dataset): closed-loop trajectory (`forest01_square`)
- [TIERS-FOREST02](https://github.com/tiers/tiers-lidars-dataset): mostly straight trajectory (`forest02_straight`)

Place the files using this exact layout. Dataset files are ignored by Git because of their size, although they may be present in a local checkout:

```text
datasets/
├── forest01_square.bag
├── forest02_straight.bag
└── ground_truth/
        ├── gt_forest01_square.tum
        └── gt_forest02_straight.tum
```

The command-line dataset name is the basename without `.bag`, for example `forest01_square`.

## Running the benchmark

### Run one optimized study

The baseline is enqueued as trial `0000`. The study is persisted in SQLite and resumes when the same method, dataset, and sampler are invoked again.

```bash
python3 scripts/optuna_optimize.py \
    --method loam_livox \
    --sampler tpe \
    --trials 50 \
    --dataset forest01_square
```

Supported method keys are `fast_lio`, `lio_livox`, `lego_loam`, `loam_livox`, and `liorf` subject to the calibration status above. Supported samplers are `tpe`, `gp`, and `cmaes`.

### Run combinations sequentially

The wrapper defaults to `fast_lio`, `lio_livox`, and `lego_loam`. Pass `--methods` explicitly when including `loam_livox`; do not include `liorf` until it is calibrated.

```bash
python3 scripts/run_full_benchmark.py \
    --trials 50 \
    --methods fast_lio lio_livox lego_loam loam_livox \
    --samplers tpe cmaes gp \
    --dataset forest01_square
```

### Run one method without Optuna

```bash
python3 scripts/run_method.py \
    --package loam_livox \
    --launch livox.launch \
    --bag datasets/forest01_square.bag \
    --odom_topic /aft_mapped_to_init \
    --output_tum results/manual_loam_livox.tum
```

This command starts the ROS master, launches the SLAM node, records the selected odometry topic, replays the bag with simulated time, and writes a TUM trajectory.

### Convert and evaluate trajectories

`bag_to_tum.py` uses Python 2 for compatibility with the ROS bag stack in Melodic; the optimization and reporting scripts use Python 3.

```bash
python2 scripts/bag_to_tum.py \
    --bag /path/to/odometry.bag \
    --topic /Odometry \
    --out results/odometry.tum \
    --offset 0
```

```bash
python3 scripts/evaluate.py \
    datasets/ground_truth/gt_forest01_square.tum \
    results/odometry.tum \
    --offset dynamic \
    --plot results/ape.png
```

The evaluator supports numeric offsets, `dynamic`, and `none`. Offsets are dataset- and method-dependent and must be recalibrated if the bags or timestamps change.

## Analysis and reports

After one or more studies have completed, the included scripts can generate summaries and figures:

```bash
python3 scripts/report_best_trials.py \
    --results-dir results \
    --dataset forest01_square \
    --top-n 5 \
    --csv-out results/best_trials.csv
```

```bash
python3 scripts/plot_convergencia.py \
    --method loam_livox \
    --sensor performance_realtime \
    --dataset forest01_square \
    --results-dir results \
    --out results/convergence.png
```

```bash
python3 scripts/plot_fanova.py \
    --method loam_livox \
    --sensor performance_realtime \
    --dataset forest01_square \
    --sampler tpe \
    --results-dir results
```

To compare resource usage between the baseline and best trial:

```bash
python3 scripts/measure_cost.py \
    --method loam_livox \
    --sensor performance_realtime \
    --dataset forest01_square \
    --sampler tpe \
    --results-dir results

python3 scripts/plot_custo_baseline_vs_best.py \
    --method loam_livox \
    --sensor performance_realtime \
    --dataset forest01_square \
    --sampler tpe \
    --results-dir results
```

<!-- MEDIA PLACEHOLDER 2
Put the article figure at: assets/results-convergence-forest01.png
Recommended image: the complete Figure 4 convergence grid, showing TPE, GP, and CMA-ES across the evaluated methods and datasets.
This is the strongest README image because it connects the repository directly to the Optuna contribution described in the article.
If the convergence grid is too small, use a high-resolution crop of one method/dataset panel or use the fANOVA importance plot as a secondary figure.
When the file is available, replace this comment with:
<p align="center">
    <img src="assets/results-convergence-forest01.png" alt="Optuna convergence results for the forest benchmark" width="900">
</p>
-->

## Output structure

```text
results/
├── <method>/<config>/<dataset>/
│   ├── study_<sampler>.db
│   ├── study_<sampler>.csv
│   └── <sampler>/trial_0000/
│       ├── config_used.yaml    # Runtime-YAML methods
│       ├── utility_used.h      # LeGO-LOAM
│       ├── odom.tum
│       ├── ape_stats.json
│       └── baseline_ape.png    # Record-setting trials only
├── _logs/                      # Per-combination logs and summary.json
└── fanova/<dataset>/           # HTML fANOVA reports
```

Invalid infrastructure, evaluation, or insufficient-pose trials receive the finite penalty `999.0`; this is required by the GP sampler and is not a measured RMSE. `psutil` is optional, but resource metrics are zero when it is unavailable.

## Current evidence

The checked-in `results/` directory contains selected studies and analysis artifacts, not a guaranteed complete matrix of every method, sampler, and dataset. Treat generated result files as the source of truth for a particular run, and record the dataset version, registry revision, sampler, trial count, and hardware when reporting results.

The repository supports the analysis used in the accompanying article template: baseline-versus-best RMSE, convergence curves, fANOVA parameter importance, execution time, peak memory, and average CPU utilization.

## Reproducibility notes

- Keep the ROS bag, ground-truth timestamps, sensor topics, and registry offsets consistent.
- `lego_loam` recompiles with `catkin_make --pkg lego_loam` for every trial.
- Existing SQLite studies are resumed because `load_if_exists=True`.
- The vendored SLAM implementations retain their upstream licenses and attribution requirements.
- Pin the container image and Python package versions for publication-grade reruns.

## Citation

If this benchmark contributes to your work, cite the associated manuscript and the upstream SLAM, dataset, Optuna, and `evo` projects. Add the final publication metadata here when available.

## License

This repository is intended for academic use. The bundled SLAM implementations and third-party dependencies are distributed under their respective upstream licenses; consult each project before redistribution.

## Author

**Lucas Froes Belinassi**<br>
Department of Computer Science, Federal University of Sao Carlos, Brazil
