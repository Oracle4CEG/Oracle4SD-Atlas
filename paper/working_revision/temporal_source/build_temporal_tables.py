"""Update scientific availability rates without inserting audit logs into prose.
The detailed worked records and validation counts remain in the data metadata.
Editorially reviewed Tables S4/S5 and the validation narrative are not generated
from execution logs.
"""
from pathlib import Path
import csv,re
root=Path(__file__).resolve().parents[1]
rows=list(csv.DictReader((root/'supplementary/temporal/time_recovery_populations.csv').open()))
rates={(r['table'],r['population']):100*float(r['utc_fraction']) for r in rows}
p=root/'tables/temporal_recovery.tex';s=p.read_text()
for label,key in [
 ('UMA DVM voter accruals',('uma_dvm_voter_payoffs','all native rows')),
 ('Chainlink native staking logs',('chainlink_staking_v02_events','all native rows')),
 ('Chainlink analytical subset',('chainlink_staking_v02_events','legacy common-projection eligible rows'))]:
 s=re.sub('('+re.escape(label)+r' & )[0-9.]+',lambda m:m.group(1)+f'{rates[key]:.1f}',s)
p.write_text(s)
print('Updated the three availability rates; retained reviewed scientific prose.')
