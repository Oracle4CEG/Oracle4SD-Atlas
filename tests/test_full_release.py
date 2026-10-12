"""Regression checks against frozen native evidence and adversarial inputs."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
CASE = "0x699c0842ebca1553171853de9853d07f0336ca0909c90156e731b76442a875ca"


class FullReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.work = Path(cls.tmp.name)
        shutil.copytree(ROOT/"tests/fixtures/revision_native", cls.work/"data/curated/parquet")
        env = os.environ.copy()
        env.update(ORACLE_WORKSPACE=str(cls.work), PYTHONPATH=str(ROOT/"code/reconstruction"),
                   MPLBACKEND="Agg", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1")
        result = subprocess.run([sys.executable,"-c",
            "from scripts.applications.oata.common import build_episodes; print(build_episodes())"],
            cwd=ROOT, env=env, capture_output=True,text=True)
        if result.returncode:
            raise RuntimeError(result.stdout+result.stderr)
        cls.con = duckdb.connect(config={"threads":1,"memory_limit":"1GB"})
        cls.con.read_parquet(str(cls.work/"data/applications/oata/accountability_episodes.parquet")).create_view("episodes")

    @classmethod
    def tearDownClass(cls):
        cls.con.close()
        cls.tmp.cleanup()

    def test_case_gross_payment_is_principal_plus_gain(self):
        row = self.con.execute("SELECT gross_payout_raw,principal_returned_raw,reward_paid_raw,principal_locked_raw,total_profit_raw FROM episodes WHERE unit_id=?",[CASE]).fetchone()
        self.assertEqual(row,("1000000000","750000000","250000000","750000000",None))

    def test_zero_address_is_not_a_challenge(self):
        row = self.con.execute("SELECT challenged,list_contains(state_sequence,'CHALLENGED') FROM episodes WHERE unit_id='0x0000694348feeb28610ac89f5fc775184b8a6a394591d19d249f501b1be44d56'").fetchone()
        self.assertEqual(row,(False,False))

    def test_open_lifecycle_has_no_realized_payment(self):
        row = self.con.execute("SELECT transfer_confirmed,reward_paid_raw,gross_payout_raw,right_censored FROM episodes WHERE unit_id='0x008e1ef7980b530a83960d213222d4d3585f1840ad95ee71c3904807d25cc8c4'").fetchone()
        self.assertEqual(row,(False,None,None,True))

    def test_tellor_only_three_support_outcomes_keep_principal_slash(self):
        self.assertEqual(self.con.execute("SELECT count(*) FROM episodes WHERE episode_type='tellor_dispute' AND try_cast(principal_slashed_raw AS HUGEINT)>0").fetchone()[0],3)
        self.assertEqual(self.con.execute("SELECT count(*) FROM episodes WHERE episode_type='tellor_dispute' AND principal_slashed_raw='0'").fetchone()[0],10)

    def test_tellor_escrow_is_not_report_power(self):
        row=self.con.execute("SELECT principal_locked_raw,reward_accrued_raw,end_time FROM episodes WHERE episode_type='tellor_dispute' AND unit_id='1'").fetchone()
        self.assertEqual(row,("9980000",None,None))

    def test_negative_accrual_does_not_establish_applied_slash(self):
        row=self.con.execute("SELECT principal_slashed_raw,signed_stake_delta_raw,state_change_confirmed,list_contains(state_sequence,'PRINCIPAL_SLASHED'),list_contains(state_sequence,'PENALTY_ACCRUED') FROM episodes WHERE try_cast(signed_accrual_delta_raw AS HUGEINT)<0").fetchone()
        self.assertEqual(row,(None,None,False,False,True))

    def test_zero_accrual_is_not_negative_adjudication(self):
        self.assertFalse(self.con.execute("SELECT list_contains(state_sequence,'ADJUDICATED_NEGATIVE') FROM episodes WHERE signed_accrual_delta_raw='0'").fetchone()[0])

    def test_reward_rate_is_never_a_token_amount(self):
        self.assertEqual(self.con.execute("SELECT count(*) FROM episodes WHERE episode_type='pyth_publisher_epoch' AND reward_accrued_raw IS NOT NULL").fetchone()[0],0)

    def test_pyth_corrupted_snapshot_fails(self):
        spec=importlib.util.spec_from_file_location("pyth_replay",ROOT/"scripts/replay_pyth_snapshot.py")
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        bad=self.work/"bad_snapshot.gz";bad.write_bytes(b"changed bytes")
        with self.assertRaisesRegex(ValueError,"hash mismatch"):
            module.decode_snapshot(bad)

    def test_common_projection_preserves_negative_accrual(self):
        spec=importlib.util.spec_from_file_location("revision_semantics",ROOT/"code/reconstruction/scripts/revision_semantics.py")
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        source="""(SELECT '1.1.0' schema_version,'uma_dvm_voter_payoffs' native_table,
          '123' principal_slashed_raw,'principal_slash' penalty_class,NULL::VARCHAR reward_class,
          'protocol_vote_adjudication' truth_basis,'old' interpretation_note)"""
        row=self.con.execute(module.common_projection(source)).fetchdf().iloc[0]
        self.assertEqual(row.penalty_accrued_raw,'123')
        self.assertEqual(row.penalty_class,'accrued_stake_penalty')
        self.assertIsNone(row.principal_slashed_raw)


if __name__ == "__main__":
    unittest.main()
