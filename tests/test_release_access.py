"""Check release integrity boundaries and exclusion of future model information."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]


def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


class ReleaseAccessTests(unittest.TestCase):
    def test_uncensored_survival_cohort_is_eligible(self):
        sys.path.insert(0,str(ROOT/'code/reconstruction'))
        from scripts.applications.financial.common import survival_cohort_supported
        frame=pd.DataFrame({'event_observed':[True]*100,'observed_duration_seconds':range(1,101)})
        self.assertTrue(survival_cohort_supported(frame,100))
        frame['event_observed']=False
        self.assertFalse(survival_cohort_supported(frame,100))

    def test_financial_sampling_is_order_and_outcome_invariant(self):
        sys.path.insert(0,str(ROOT/'code/reconstruction'))
        from scripts.applications.financial.common import select_benchmark_sample
        frame=pd.DataFrame([dict(episode_id=f'e{i:04}',track='reward',protocol=f'p{i%3}',
                                 chronological_split=['train','valid','test'][i%3],
                                 event_observed=bool(i%2)) for i in range(300)])
        first=select_benchmark_sample(frame,60)
        changed=frame.sample(frac=1,random_state=7).copy()
        changed['event_observed']=~changed.event_observed
        second=select_benchmark_sample(changed,60)
        self.assertEqual(list(first.episode_id),list(second.episode_id))
        self.assertEqual(len(first),60)
        self.assertEqual(set(first.protocol),set(frame.protocol))

    def test_prefix_features_do_not_retain_full_outcomes(self):
        sys.path.insert(0,str(ROOT/'code/reconstruction'))
        from scripts.applications.oata.common import prefix_feature_frame
        first=pd.DataFrame([dict(episode_id='e1',protocol='UMA',episode_type='request',
                                state_sequence=['INITIATED','CHALLENGED','REWARD_PAID','CLOSED'],
                                state_reward_paid=1,total_duration_seconds=9999,reward_to_locked=9.0,
                                transfer_confirmed_share=1,cross_chain_flag=True)])
        changed=first.copy(deep=True)
        changed.at[0,'state_sequence']=['INITIATED','CHALLENGED','PRINCIPAL_SLASHED','RIGHT_CENSORED']
        changed['total_duration_seconds']=1
        changed['reward_to_locked']=0
        changed['state_reward_paid']=0
        changed['cross_chain_flag']=False
        pd.testing.assert_frame_equal(prefix_feature_frame(first),prefix_feature_frame(changed))

    def test_unsettled_rule_is_specific_and_not_a_settlement_claim(self):
        sys.path.insert(0,str(ROOT/'code/reconstruction'))
        from scripts.revision_semantics import UNSETTLED_RULE_EXPR
        import duckdb
        frame=pd.DataFrame(dict(native_table=['polygon_uma_request_rounds']*3,
                                outcome_status=['not_settled','settled_disputed_proposer_wins','not_settled'],
                                rule_id=[None,None,'existing_rule']))
        con=duckdb.connect();con.register('events',frame)
        values=[row[0] for row in con.execute('SELECT '+UNSETTLED_RULE_EXPR+' FROM events').fetchall()]
        self.assertEqual(values,['uma_oov2_unsettled_request_observation_v2',None,'existing_rule'])

    def test_future_outcomes_cannot_change_model_features(self):
        benchmark=module('run_decision_benchmark')
        frame=pd.DataFrame({name:[1,2] for name in benchmark.FEATURES})
        before=benchmark.feature_frame(frame)
        frame['proposal_rejected_by_protocol']=[False,True]
        frame['future_reward_paid_raw']=['90000000','0']
        frame['future_arbitrator_decision']=['yes','no']
        pd.testing.assert_frame_equal(before,benchmark.feature_frame(frame))

    def test_corrupted_existing_download_is_not_replaced(self):
        downloader=module('download_atlas')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);target=root/'out/data/test.parquet'
            target.parent.mkdir(parents=True);target.write_bytes(b'corrupted')
            manifest=root/'release.json'
            manifest.write_text(json.dumps({'components':{'native':{'revision':'a'*40,'files':[
                {'path':'data/test.parquet','bytes':4,'sha256':hashlib.sha256(b'good').hexdigest(),
                 'url':'https://example.org/resolve/'+'a'*40+'/data/test.parquet'}]}}}))
            with patch.object(downloader.requests,'get',side_effect=AssertionError('No network expected')):
                with self.assertRaisesRegex(ValueError,'Existing file differs'):
                    downloader.download(manifest,'native',root/'out')
            self.assertEqual(target.read_bytes(),b'corrupted')


if __name__=='__main__':unittest.main()
