# UI Design Best-Practices Harness

Use when building or reviewing a real UI surface — a screen, component, page,
or flow — for design quality, not only for function. Do not fire it for a
workflow-less divergent ask ("propose N layout options"): the Default-workflow
scope gate owns that. Post-hoc bug-hunting on a running GUI stays with GUI
Dogfood QA; this harness governs how the UI is *designed and built*.

- **Design brief before pixels.** Fix the audience, platform, governing design
  system, primary user tasks, information hierarchy, required states, and the
  success metric (which action must be obvious and cheap) before writing UI
  code. The Narrative Empathy card owns voice/microcopy/feel; reference it
  from the brief rather than restating it.
- **Canon compliance, anti-reinvention.** Name the governing canon first: the
  project's existing design tokens and components, then the platform or
  product design system the project already follows (e.g. Apple HIG, Material
  Design, an in-house system). Reuse before inventing; a new one-off style,
  spacing value, or color is an excess-pass candidate and needs evidence that
  the canon cannot express it. Verify best-practice claims against official
  sources with a checked date (Best-Practice Gate) — never from memory.
- **Established heuristics are the review lens.** Evaluate against NN/g's ten
  usability heuristics (visibility of system status; match to the real world;
  user control and freedom; consistency and standards; error prevention;
  recognition over recall; flexibility and efficiency; aesthetic and
  minimalist design; error recognition and recovery; help and documentation)
  rather than personal taste. (nngroup.com, checked 2026-07-07.)
- **Measure simplicity, do not assert it.** Clicks-to-action for the primary
  task, time-on-task, task success, findability, and cognitive load are the
  default metrics. Fitts's law (target size/distance), Hick's law (choice
  count), and Jakob's law (familiar patterns) are the standard levers when a
  metric is bad.
- **Structural fundamentals checklist.** Visual hierarchy that matches task
  priority; consistent spacing scale and grid; a deliberate type scale; text
  contrast at least 4.5:1 (3:1 for large text, WCAG 2.2 SC 1.4.3); pointer
  targets at least 24x24 CSS px or spaced/excepted per SC 2.5.8 (AA); full
  keyboard operability with visible focus; reduced-motion respected.
- **Full state coverage is entailed, not optional.** Empty, loading, error,
  success, disabled, overflow/long-content, and responsive breakpoints are
  entailed companions of every screen (Closure/Negative-Space Tier A). A
  happy-path-only screen is an incomplete design, not a finished one.
- **Validate on the rendered artifact.** Render the actual UI and inspect it
  (screenshot or live run) before claiming design quality; code-only review
  must disclose "visual not measured" and recommend a human or visual-QA
  pass. Hand the finished surface to GUI Dogfood QA for the black-box pass;
  hand 3D/spatial work to Spatial Forge.

Primary sources (checked 2026-07-07): NN/g ten usability heuristics
(nngroup.com/articles/ten-usability-heuristics/); WCAG 2.2 Understanding SC
1.4.3 Contrast (Minimum) and SC 2.5.8 Target Size (Minimum) (w3.org/WAI);
Laws of UX (lawsofux.com) for the named interaction laws.
