# Closure check record

Use this before answering from a visible set of artifacts, numbered items,
images, files, clipped logs, quoted excerpts, partial text, or adversarially
framed evidence. The goal is to prevent the model from treating the presented
frame as a closed world without evidence.

```text
visible items:
stated / observed count:
count source: user | filename | numbering | metadata | environment | inference
verified exhaustive count: yes | no | unknown
incompleteness triggers:
  - mid-sentence / mid-clause / semantic continuation
  - missing sequence number / asymmetric pattern / N+1 pressure
  - clipped log / excerpt / crop / omitted attachment
  - adversarial or evaluative presenter incentive
  - metadata outside visible text may carry signal
inside-frame answer:
frame-completeness hypothesis:
materiality:
Tier A continuation / omitted-context hypothesis:
what would confirm:
what would refute:
surface form: finding | question | no surface
do not assert missing item exists:
```

Rules:

- `observed N` and `stated N` are not automatically `verified exhaustive N`.
- Do not skip the check because a count was stated, numbered, implied, or known.
  A confident-looking count can itself be part of the presented frame.
- If text, sequence, or artifact boundaries are materially incomplete, generate
  a Tier A continuation or omitted-context hypothesis. Surface the hypothesis
  without claiming the missing artifact exists.
- Run both the inside-frame answer and the frame-completeness check. Do not let
  a precise answer inside the visible frame replace boundary inspection.

