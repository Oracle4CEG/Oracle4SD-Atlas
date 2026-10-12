"""Run a chronological 810-decision protocol-outcome benchmark on CPU.

The endpoint is later protocol adjudication, not independent factual truth.
All post-decision identifiers and labels are excluded from the feature matrix.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC = ["log_bond_raw","log_final_fee_raw","log_reward_plus1_raw","reward_to_bond_ratio",
           "liveness_hours","proposal_latency_hours","ancillary_bytes",
           "proposer_prior_completed","proposer_prior_dispute_rate","proposer_prior_rejection_rate",
           "requester_prior_completed","requester_prior_dispute_rate","requester_prior_rejection_rate"]
CATEGORICAL = ["requester_is_polymarket_adapter","proposed_price_class","adapter_version"]
FEATURES = NUMERIC+CATEGORICAL
TARGET = "proposal_rejected_by_protocol"


def feature_frame(frame):
    """Select the registered information set; unknown added columns cannot enter."""
    return frame.loc[:,FEATURES].copy()


def run(release, output):
    release,output=Path(release),Path(output)
    output.mkdir(parents=True,exist_ok=False)
    base=release/"data/applications/trustworthy_ai_challenge"
    samples=base/"decision_samples.parquet"; splits=base/"splits.parquet"
    frame=pd.read_parquet(samples); assignment=pd.read_parquet(splits)
    if frame.sample_id.duplicated().any() or assignment.sample_id.duplicated().any():
        raise ValueError("Duplicate decision/split identity")
    if set(frame.sample_id)!=set(assignment.sample_id):
        raise ValueError("Split IDs do not cover exactly the decision table")
    frame=frame.merge(assignment[['sample_id','split']],on='sample_id',validate='one_to_one')
    if (frame.evidence_snapshot_time_unix > frame.decision_time_unix).any() or not frame.future_fields_excluded.all():
        raise ValueError("Decision-time evidence boundary failed")
    names=set(frame.split)
    train=frame[frame.split=='train'].copy()
    valid=frame[frame.split.isin(['validation','valid','val'])].copy()
    test=frame[frame.split=='test'].copy()
    if len(train)+len(valid)+len(test)!=len(frame) or min(len(train),len(valid),len(test))==0:
        raise ValueError(f"Unsupported or empty split: {names}")
    if not (train.decision_time_unix.max() < valid.decision_time_unix.min() and valid.decision_time_unix.max() < test.decision_time_unix.min()):
        raise ValueError("Chronological splits overlap in decision time")
    for col in CATEGORICAL:
        frame[col]=frame[col].fillna('unknown').astype(str)
        for part in (train,valid,test): part[col]=part[col].fillna('unknown').astype(str)
    metrics=[];predictions=[]
    estimators={
        'prior_baseline':DummyClassifier(strategy='prior'),
        'logistic_regression':LogisticRegression(max_iter=2000,random_state=20261012),
        'hist_gradient_boosting':HistGradientBoostingClassifier(max_iter=100,max_leaf_nodes=15,random_state=20261012),
    }
    for name,estimator in estimators.items():
        prep=ColumnTransformer([
            ('numeric',make_pipeline(SimpleImputer(strategy='median'),StandardScaler()),NUMERIC),
            ('categorical',OneHotEncoder(handle_unknown='ignore',sparse_output=False),CATEGORICAL),
        ])
        model=make_pipeline(prep,estimator)
        model.fit(feature_frame(train),train[TARGET].astype(int))
        for split,part in [('validation',valid),('test',test)]:
            prob=model.predict_proba(feature_frame(part))[:,list(model.classes_).index(1)]
            label=part[TARGET].astype(int).to_numpy()
            metrics.append(dict(model=name,split=split,rows=len(part),accuracy=accuracy_score(label,prob>=.5),
                                brier=brier_score_loss(label,prob),log_loss=log_loss(label,prob,labels=[0,1]),
                                roc_auc=roc_auc_score(label,prob) if len(np.unique(label))==2 else None))
            predictions.extend(dict(sample_id=sid,model=name,split=split,probability=float(p),protocol_label=int(y))
                               for sid,p,y in zip(part.sample_id,prob,label))
    pd.DataFrame(metrics).to_csv(output/"metrics.csv",index=False)
    pd.DataFrame(predictions).to_parquet(output/"predictions.parquet",index=False)
    report=dict(passed=True,source_files={str(p.relative_to(release)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [samples,splits]},
                split_counts={"train":len(train),"validation":len(valid),"test":len(test)},features=FEATURES,
                training="Training split only; transformations are fit on training data; fixed hyperparameters, no test-set selection.",
                scope="Conditional challenged-UMA protocol-outcome prediction; no independent factual-truth or causal policy claim.",
                checks={"unique_ids":True,"exact_split_coverage":True,"strict_time_order":True,"declared_evidence_not_after_decision":True,"future_columns_excluded_by_allowlist":True},
                limitation="Historical feature construction is retained; timing checks do not independently authenticate every off-chain item.")
    (output/"validation.json").write_text(json.dumps(report,indent=2)+"\n")
    print(pd.DataFrame(metrics).to_string(index=False))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--release',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.release,a.output)
