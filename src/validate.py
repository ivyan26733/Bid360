"""
Check that the ID recovery rule is trustworthy.

Idea: take PPD rows whose ID we KNOW, hide their IDs, run the recovery rule,
and count how many come back - and how many come back CORRECT.
"""
import numpy as np

from src import config
from src.clean import QualityLog, recover_missing_ids, replace_null_tokens, to_numeric


def simulate_id_recovery(raw_ppd, ct_clean, n_hidden=94, rounds=5, seed=0) -> dict:
    log = QualityLog()  # throw-away log, not part of the real cleaning log
    ppd = to_numeric(replace_null_tokens(raw_ppd, "PPD", log), "PPD", log)  # same prep as real cleaning
    known = ppd.index[ppd[config.KEY].notna()]        # rows whose true ID we know
    real_orphans = ppd.index[ppd[config.KEY].isna()]  # leave the real orphans out of the test
    rng = np.random.default_rng(seed)                 # fixed seed -> same result every run

    hidden_total = recovered = correct = 0
    for _ in range(rounds):
        hide = rng.choice(known, n_hidden, replace=False)  # pick rows to blank out
        truth = ppd.loc[hide, config.KEY]                  # remember their real IDs
        test = ppd.drop(index=real_orphans).copy()
        test.loc[hide, config.KEY] = np.nan                # hide the IDs
        result = recover_missing_ids(test, ct_clean, log).loc[hide, config.KEY]  # run the rule
        hidden_total += n_hidden
        recovered += result.notna().sum()                  # how many got an ID back
        correct += (result == truth).sum()                 # how many got the RIGHT ID back
    return {"hidden": int(hidden_total), "recovered": int(recovered), "correct": int(correct)}
