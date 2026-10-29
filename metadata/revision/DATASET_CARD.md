---
license: cc-by-4.0
task_categories:
- tabular-classification
language:
- en
configs:
- config_name: uma
  data_files:
  - split: train
    path: data/native/polygon_uma_request_rounds.parquet
- config_name: chainlink
  data_files:
  - split: train
    path: data/native/chainlink_staking_v02_events.parquet
- config_name: tellor
  data_files:
  - split: train
    path: data/native/tellor_disputes.parquet
- config_name: flare_ftsov2
  data_files:
  - split: train
    path: data/native/flare_reward_epochs.parquet
- config_name: pyth
  data_files:
  - split: train
    path: data/native/pyth_ois_reward_epochs.parquet
- config_name: chronicle
  data_files:
  - split: train
    path: data/native/chronicle_ethereum_events.parquet
- config_name: redstone_push
  data_files:
  - split: train
    path: data/native/redstone_ethereum_push_events.parquet
- config_name: dia
  data_files:
  - split: train
    path: data/native/dia_staking_withdrawals.parquet
- config_name: uma_prediction
  data_files:
  - split: train
    path: data/prediction/uma_prediction_tasks.parquet
- config_name: daily_measurements
  data_files:
  - split: train
    path: data/daily/daily_measurements.parquet
---
# Oracle4SD Atlas: local coordinated revision

This deposit contains ten logical products: eight native oracle branches, a request-level UMA prediction task and coverage-qualified daily measurements. The ten Viewer configurations expose representative tables; the full physical-table inventory and relationships are in the catalogue. A Viewer `train` split here is a file-loading label, not a declared modelling partition.

The daily product retains date, branch, mechanism, actor role, asset, unit, economic stage, denominator and coverage. Missing days are not zero-filled. Signing policies remain epoch-supported. Escrow exposure uses observed closed-request balances; it is not protocol-wide collateral or participant wealth.

The UMA task is retrospectively restricted to challenged, deterministically linked, settled and transfer-reconciled requests. The target compares the protocol's resolved and proposed integers, including special values. Sixteen candidate features have explicit missingness and availability records. No fitted model or model performance is part of this revision.

Native UTC tables preserve original fields. Core parent tables retain legacy fields. Keyed clock companions supply authoritative supported UTC event clocks and are joined by the retained record identifier. Epochs and snapshots remain distinct from events. Older application/model views are archived with the reconstruction and are not relabelled as updated decision-time data.

Semantic corrections preserve previous values, new values and native source locators. Machine checks do not constitute author sign-off. Contract/runtime binding, incomplete acquisition intervals, unmatched relay steps and independent factual truth remain qualified in the evidence records.

This is a local review deposit, not a newly published Hugging Face version. Public predecessor: https://huggingface.co/datasets/Oracle4CEG/OracleEconLab-Oracle-Incentives-v1 . Processing repository: https://github.com/Oracle4CEG/Oracle4SD-Atlas . Publication should preserve the file manifest, physical recordsets, product membership and tutorial together.
