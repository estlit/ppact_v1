# Test Suite Inventory - Phase T1

Generated 2026-08-05T02:32:12Z. Engine 4.17.3.

**No code was changed while producing this record.** It exists so
that anything changed after it can be identified as a change.

## Verdict

| | |
|---|---|
| engine correctness evidence | **previously observed** |
| test governance integrity | **NOT ESTABLISHED** |
| current release evidence | **STALE - suite manifest mismatch** |
| rc3 final status | **NOT PERMITTED** |

The engine's numbers were checked and the checks passed. What is
not established is whether the SET OF CHECKS that ran is the set
this program now has. Those are different claims, and only the
first was ever tested.

## The three sets

    discovered   18
    registered   18
    reported     18

All three are 18, and the counts agree. The MEMBERS do not:

```
registered_but_not_reported       ['menu paths']
reported_but_not_registered       ['quick start example']
discovered_but_not_registered     (none)
registered_but_not_discovered     (none)
```

`menu paths` is registered and absent from the record. `quick
start example` is in the record and not in the registry - it runs
as a separate release step rather than a suite.

A count is not a set. Three eighteens hid a mismatch in both
directions.

## Why the record still looks current

The record names engine 4.17.3
and the engine is 4.17.3. They match, so every
integrity check treats the record as evidence about this build.

Registering a suite changes what verification MEANS and changes no
engine file. Keying freshness on the engine version alone cannot
see that.

## Findings

- Nothing enforces discovered = registered = executed = reported.
- The verification record is keyed on engine version only, so a change to the suite set leaves it looking current.
- Twelve suites carry no positive control, so their discriminating power is NOT ESTABLISHED - which is not the same as invalid.
- Ten suites declare no limits, so what their pass counts do NOT establish is unstated.
- No suite declares the engine or contract version it was written against.
- tests_library_validation performs static checks only and never calls the engine.

## Suite digests

```
tests_corner.py                 c3d85f49f948719d
tests_differential.py           0775dd7c4cbb0880
tests_docs.py                   ab135e7e5094e1fb
tests_dual.py                   353e9e7f3b55a158
tests_freeze.py                 5f91d72bf00a1961
tests_holdout.py                d6d891cbaca57141
tests_independent.py            79dd9562b4f9ce65
tests_language.py               54ccb7072c2c9511
tests_library_validation.py     ebb2cb38c9d3304c
tests_logical_consistency.py    30d269428da56142
tests_memory.py                 bf6f68852102a8d2
tests_menu_paths.py             3c95019515a457ea
tests_model.py                  99a82bafd0dbf327
tests_mutation.py               caea3e0f8a1a2884
tests_questions.py              deb6b246cd4d6889
tests_review_contract.py        b89a94c3540595ac
tests_scenarios.py              f2d55e3c2843ff71
tests_user_validation.py        aced70c66715b763
```

engine source digest       c6c99dfc7356e434
verification runner        ef1e49d043b95256

## What this record does NOT establish

- That any suite is wrong. Twelve have no positive control, which
  means their discriminating power is unproven, not absent.
- That the engine is incorrect. Its checks were observed passing.
- That the inventory is complete. It lists files matching
  `tests_*.py`; a check living anywhere else is not counted here.
