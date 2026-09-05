# Helix run split record

Use this for every Helix increment or finished loop, from the moment the
directive arrives until the merge or the handover, to record the route's
splits, the sanctioned warps it used, and where the time went. Create the
strict JSON record and validate it from the source checkout with:

```bash
python3 scripts/helix_split_check.py validate --record <record.json>
```

```text
run:
  run_id / repo / effort ref (issue or PR URL):
  category (any_percent_dev | full_percent_prod | deliverable):
  size_class (small | medium | large):
  loop_profile (two_party | three_party) / implementer / reviewers:
clock (ISO instants, read not estimated; `not read` when not read):
  directive_received / target_located / contract_closed:
  impl_pushed / review_requested:
  findings_returned: [round, at, finding_count]
  signoffs_complete / validation_read / finished:
pace:
  target_minutes / target_source (owner | default | sum_of_best):
  elapsed_minutes / verdict (derived by the validator):
warps_used: [W1 .. W10]
rounds / round_cap / round_cap_disposition (issue refs or tie-break ref):
time_sinks: [phase, cause, minutes]   (required when over pace)
void: false | reason (a banned glitch names itself here)
```

The validator owns the semantics. Splits must not run backwards; `finished`
cannot precede `signoffs_complete`, and `signoffs_complete` cannot precede the
last `findings_returned`. Only the ten sanctioned warp ids validate; any
banned-glitch name in `warps_used` voids the run. `rounds` above the cap needs
a disposition ref. An over-pace run needs at least one attributed time sink,
and a run whose target has no source does not validate. The record carries
no authority: it grants no merge, deploy, or access, and it never shortens a
safety-floor check.
