# Tabel Hasil Evaluasi — Bab 4 (final)

> Single-run (NaN→0), Proposed/K=5 = hyde_t07. Uji konsistensi = 3 run.

## Tabel 4.x — Uji Kontribusi Komponen (Ablasi, K=5)
| Mode | Precision@5 | Recall@5 | Hit@5 | Faithfulness | Answer Rel. |
|---|---|---|---|---|---|
| Baseline | 0,6402 | 0,8569 | 0,8958 | 0,5809 | 0,9027 |
| HyDE | 0,5946 | 0,8523 | 0,8889 | 0,5589 | 0,8932 |
| CoT | 0,6402 | 0,8569 | 0,8958 | 0,5807 | 0,8782 |
| Proposed | 0,6157 | 0,8394 | 0,8681 | 0,6317 | 0,8905 |

## Tabel 4.x — Variasi Nilai K (Mode Proposed)
| K | Precision@K | Recall@K | Hit@K | Faithfulness | Answer Rel. |
|---|---|---|---|---|---|
| 3 | 0,6609 | 0,8127 | 0,8472 | 0,6027 | 0,8483 |
| 5 | 0,6157 | 0,8394 | 0,8681 | 0,6317 | 0,8905 |
| 10 | 0,4785 | 0,9106 | 0,9444 | 0,6267 | 0,8958 |

## Tabel 4.x — Evaluasi per Topik (Proposed, K=5)
| Topik | n | Precision@5 | Recall@5 | Hit@5 | Faithfulness | Answer Rel. |
|---|---|---|---|---|---|---|
| Computer Vision | 76 | 0,6086 | 0,7724 | 0,8026 | 0,5893 | 0,8835 |
| Telecom/Radar | 30 | 0,6667 | 1,0000 | 1,0000 | 0,6667 | 0,9361 |
| Software Eng/IT | 22 | 0,6553 | 0,8561 | 0,9091 | 0,6462 | 0,8667 |
| NLP | 5 | 0,2500 | 0,8000 | 0,8000 | 0,6767 | 0,9270 |
| ML/Forecasting | 4 | 0,8750 | 1,0000 | 1,0000 | 1,0000 | 0,9180 |
| Drone/UAV | 4 | 0,6250 | 1,0000 | 1,0000 | 0,8333 | 0,9422 |
| E-Nose/Sensor | 3 | 0,2500 | 0,4444 | 0,6667 | 0,4167 | 0,6223 |

## Tabel 4.x — Sensitivitas Temperature HyDE (Proposed, K=5, CoT 0,2)
| Temp HyDE | Precision@5 | Recall@5 | Hit@5 | Faithfulness | Answer Rel. |
|---|---|---|---|---|---|
| 0,2 | 0,5771 | 0,8336 | 0,8681 | 0,6229 | 0,8774 |
| 0,4 | 0,5956 | 0,8405 | 0,8750 | 0,5892 | 0,8724 |
| 0,7 | 0,6157 | 0,8394 | 0,8681 | 0,6317 | 0,8905 |

## Tabel 4.x — Sensitivitas Temperature CoT (Proposed, K=5, HyDE=0)
| Temp CoT | Precision@5 | Recall@5 | Hit@5 | Faithfulness | Answer Rel. |
|---|---|---|---|---|---|
| 0,2 | 0,5973 | 0,8581 | 0,8958 | 0,5964 | 0,8751 |
| 0,5 | 0,6084 | 0,8419 | 0,8819 | 0,6001 | 0,8800 |
| 0,7 | 0,5787 | 0,8405 | 0,8750 | 0,6002 | 0,8666 |

## Tabel 4.x — Sensitivitas Panjang Abstrak HyDE (Proposed, K=5, HyDE 0,7)
| Panjang (kata) | Precision@5 | Recall@5 | Hit@5 | Faithfulness | Answer Rel. |
|---|---|---|---|---|---|
| 50–80 | 0,6245 | 0,8581 | 0,8958 | 0,6006 | 0,8828 |
| 100–150 | 0,6157 | 0,8394 | 0,8681 | 0,6317 | 0,8905 |
| 200–250 | 0,5811 | 0,8347 | 0,8681 | 0,5779 | 0,8526 |

## Tabel 4.x — Uji Konsistensi (HyDE & Proposed, K=5, 3 run)
| Mode | Metrik | Run 1 | Run 2 | Run 3 | Mean ± Std |
|---|---|---|---|---|---|
| HyDE | Precision@5 | 0,5863 | 0,6137 | 0,5884 | 0,5961 ± 0,0152 |
|  | Recall@5 | 0,8405 | 0,8613 | 0,8475 | 0,8498 ± 0,0106 |
|  | Hit@5 | 0,8750 | 0,8958 | 0,8819 | 0,8843 ± 0,0106 |
|  | Faithfulness | 0,5755 | 0,6091 | 0,5522 | 0,5790 ± 0,0286 |
|  | Answer Rel. | 0,9002 | 0,9010 | 0,9070 | 0,9027 ± 0,0037 |
| Proposed | Precision@5 | 0,6157 | 0,6006 | 0,5889 | 0,6017 ± 0,0135 |
|  | Recall@5 | 0,8394 | 0,8498 | 0,8521 | 0,8471 ± 0,0068 |
|  | Hit@5 | 0,8681 | 0,8819 | 0,8889 | 0,8796 ± 0,0106 |
|  | Faithfulness | 0,6317 | 0,6141 | 0,6044 | 0,6167 ± 0,0138 |
|  | Answer Rel. | 0,8905 | 0,8912 | 0,8655 | 0,8824 ± 0,0147 |

> Proposed Run 1 = hyde_t07; Run 2–3 = multirun. HyDE Run 1–3 = multirun.