# External Reconstruction Adapter Harness

- Use external reconstruction repos through adapter manifests instead of
  vendoring speculative implementations into this repo.
- Validate the adapter manifest before trusting it.
- Record upstream/fork commit, local path, configuration, input, output, and
  baseline evidence for every claim.
- Treat architectural probes as hypotheses; never claim proprietary equivalence
  without independent evidence.
- For OpenMythos specifically, use `adapters/openmythos.adapter.json` and
  `references/openmythos-external-adapter.md`.

