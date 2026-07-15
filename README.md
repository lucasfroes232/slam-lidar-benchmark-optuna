# Benchmark de Algoritmos SLAM LiDAR com Otimização via Optuna

Benchmark comparativo de três algoritmos de SLAM LiDAR-inercial (**FAST-LIO**, **LIO-Livox** e **LeGO-LOAM**) em ambientes florestais, com otimização automática de hiperparâmetros usando o [Optuna](https://optuna.org/).

O objetivo é maximizar a precisão de localização (RMSE do APE) automatizando a busca por configurações ótimas, já que os parâmetros *default* desses algoritmos são calibrados para ambientes urbanos e degradam em cenários com vegetação densa.

## Contexto

- **Datasets:** trajetórias reais coletadas em floresta (TIERS-FOREST01 e TIERS-FOREST02), com sensores Ouster128, Livox e Velodyne16.
- **Otimizador:** Optuna, comparando três estratégias de busca — **TPE**, **CMA-ES** e **GP**.
- **Métrica:** RMSE do APE (*Absolute Pose Error*), calculado via `evo_ape`.
- **Configuração:** 50 *trials* por combinação algoritmo × sampler, com o *trial* #0 fixado no baseline.

## Estrutura do repositório

```
.
├── src/                     # Código do pipeline (execução do SLAM + integração com Optuna)
├── configs/                 # Arquivos de configuração / espaços de busca por algoritmo
├── scripts/                 # Scripts auxiliares (conversão TUM, avaliação evo_ape, etc.)
├── results/                 # Resultados dos trials (RMSE por trial, melhores configs)
├── figs/                    # Gráficos gerados (convergência, comparação baseline vs. otimizado)
├── report/
│   ├── Relatorio_Benchmark_SLAM_Optuna.tex
│   └── Relatorio_Benchmark_SLAM_Optuna.pdf
├── slides/                  # Apresentação e script de fala
├── .gitignore
└── README.md
```

> Datasets `.bag` **não são versionados** neste repositório (ver `.gitignore`). Veja a seção [Datasets](#datasets) para obter os arquivos originais.

## Pipeline experimental

1. **Input** — leitura dos `.bag` reais (Ouster128, Livox, Velodyne16).
2. **Processamento** — execução do algoritmo de SLAM em ROS, com os parâmetros sugeridos pelo *trial* corrente do Optuna.
3. **Formatação** — conversão da odometria estimada para o formato TUM.
4. **Avaliação** — cálculo do RMSE via `evo_ape`, comparando com o *ground truth*.
5. **Feedback** — RMSE reportado ao Optuna, que sugere o próximo *trial*.

## Algoritmos avaliados

| Método | Arquitetura | Pontos fortes | Desafios |
|---|---|---|---|
| **FAST-LIO** | Tightly-coupled (LiDAR+IMU via ESKF), ikd-Tree | Rápido, robusto a movimentos bruscos, nuvem bruta | Sensível à calibração extrínseca LiDAR-IMU |
| **LIO-Livox** | Tightly-coupled, especializado para Livox | Excelente em sensores Livox, foco em features planas | Depende de features estáveis na cena |
| **LeGO-LOAM** | Loosely-coupled, segmentação de solo em 2 estágios | Leve computacionalmente, separa chão de obstáculos | Mais sujeito a *drift* em trajetórias longas |

## Principais resultados

- A otimização automática trouxe ganho **heterogêneo entre algoritmos**: reduções de até **68%** no RMSE do LeGO-LOAM no dataset FOREST01, contra ganhos marginais (<3%) para FAST-LIO.
- O **CMA-ES** foi o sampler mais consistente entre os três algoritmos; o **TPE** se destacou quando o espaço de busca é dominado por poucos limiares de classificação (caso do LeGO-LOAM); o **GP** teve o pior desempenho prático, chegando a estagnar completamente no LeGO-LOAM.
- A análise de correlação de Spearman identificou os parâmetros de maior impacto no RMSE de cada algoritmo (ex.: `filter_size_map` e `blind` no FAST-LIO; `LidarNearestDis` no LIO-Livox; `edgeThreshold` e `surfThreshold` no LeGO-LOAM).

Resultados completos, gráficos e discussão estão no [relatório técnico](report/Relatorio_Benchmark_SLAM_Optuna.pdf).

## Requisitos

- ROS (Noetic ou Melodic, conforme a versão dos algoritmos utilizados)
- Python 3.8+
- [Optuna](https://optuna.org/)
- [evo](https://github.com/MichaelGrupp/evo) (avaliação de trajetórias)
- Implementações de [FAST-LIO](https://github.com/hku-mars/FAST_LIO), [LIO-Livox](https://github.com/Livox-SDK/LIO-Livox) e [LeGO-LOAM](https://github.com/RobustFieldAutonomyLab/LeGO-LOAM)

```bash
pip install optuna evo
```

## Datasets

Os datasets utilizados (TIERS-FOREST01 e TIERS-FOREST02) não estão incluídos neste repositório por tamanho. [Descreva aqui onde obtê-los — ex: link do TIERS ou repositório original.]

## Reproduzindo os experimentos

```bash
# Exemplo genérico — ajustar conforme a estrutura real do seu código
python src/run_optuna_study.py \
    --algorithm fast_lio \
    --sampler cmaes \
    --dataset data/tiers_forest01.bag \
    --n-trials 50
```

## Relatório

O relatório técnico completo (revisão teórica, metodologia, resultados e discussão) está disponível em:
- [`report/Relatorio_Benchmark_SLAM_Optuna.pdf`](report/Relatorio_Benchmark_SLAM_Optuna.pdf)
- Código-fonte LaTeX: [`report/Relatorio_Benchmark_SLAM_Optuna.tex`](report/Relatorio_Benchmark_SLAM_Optuna.tex)

## Trabalhos futuros

- Incluir métodos mais recentes (LIO-SAM, POINT-LIO).
- Ampliar para outros biomas além de floresta.
- Implementar fechamento de loop (*loop closure*) automático no pipeline.
- Otimização multi-objetivo: RMSE vs. tempo de CPU.

## Autor

Lucas Froes Belinassi

## Licença

[Defina aqui a licença do projeto — ex: MIT, ou "uso acadêmico".]
