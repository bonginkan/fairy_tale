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
- **Canon compliance and token contract.** Name the governing canon first: the
  project's existing tokens and components, then the platform or product
  design system it already follows. Inventory before adding. Map primitive
  values to semantic roles (for example surface, text, border, focus, danger)
  and semantic roles to component/state tokens; components consume roles, not
  raw one-off values. Inherit one bounded spacing scale and type scale from the
  governing system rather than imposing a universal 4/8-point grid. A new raw
  color, size, radius, shadow, breakpoint, or z-index is an excess-pass
  candidate and needs evidence that the canon cannot express it. DTCG defines
  the interoperable token format; a governing design system such as USWDS is
  an implementation example, never a mandated aesthetic.
- **Supported-theme parity is Tier A.** If the governing product supports
  multiple themes, build a token/state matrix for every supported theme and
  validate each rendered theme. Do not auto-invert one theme or invent a dark
  theme for a single-theme product. Contrast and semantic meaning must survive
  the mapping; color alone never carries status.
- **Layout is a system, not a stack.** Choose the governing grid/container,
  alignment anchors, content measure, density, and responsive transformation
  before component placement. Use proximity and whitespace to encode groups;
  keep repeated rows and controls on stable tracks; set explicit constraints
  for boards, tables, toolbars, and media so state or content changes do not
  shift the layout. Density is a task decision: operational surfaces optimize
  scanning and comparison, while editorial surfaces may spend more space.
- **Information architecture and action hierarchy.** Map task -> entry point ->
  destination -> recovery. Keep navigation breadth/depth and labels consistent
  with the governing product; use progressive disclosure only for secondary
  complexity, never to hide required context or destructive consequences.
  Declare the primary task and action hierarchy for each view. Dense tables or
  repeated workflows may legitimately have coequal row actions; do not force a
  universal one-primary-button rule.
- **Business-surface contracts.** Build only the relevant contract before
  styling. Keep source strength explicit: normative WCAG outcomes are
  requirements, WAI tutorial patterns are conditional techniques, and authored
  prompts below are scoped completeness questions. Forms require programmatic
  names, logical keyboard order, and instructions/error identification where
  applicable. Preserve user input when feasible as a recovery technique.
  Choose inline errors and/or a summary by context; a summary is warranted when
  multiple, page-level, or hard-to-discover errors would otherwise impair
  recovery, not for every form. Data tables require correctly associated
  headers and, when surrounding context does not identify them, an accessible
  name or caption; add units/time basis and
  sort/filter/loading/empty/error or small-screen behavior only when the data
  and task entail them. WAI form/table tutorials own these accessibility
  outcomes while allowing more than one conforming technique. For dashboards,
  ask whether metric definition, source/freshness, comparison basis,
  drill-down, and empty/stale handling are needed; for pricing or checkout, ask
  whether charged unit/period, inclusions, next step, and recovery are needed.
  These are authored completeness prompts grounded in NN/g system-status,
  real-world-match, error-prevention, and recovery heuristics plus the
  governing product/task evidence -- not universal WAI requirements. Record a
  reason when a listed prompt is not applicable rather than inventing a field.
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
- **Accessibility floor.** Preserve a meaningful focus order (SC 2.4.3) and a
  visible keyboard focus indicator (SC 2.4.7). Text contrast is at least 4.5:1
  (3:1 for large text, SC 1.4.3); non-text UI states and focus indicators are
  at least 3:1 where SC 1.4.11 applies; pointer targets meet 24x24 CSS px or an
  allowed spacing/exception (SC 2.5.8). Content reflows without two-dimensional
  scrolling at 320 CSS px width for vertically scrolling content or 256 CSS px
  height for horizontally scrolling content, except genuinely two-dimensional
  content (SC 1.4.10). Keep full keyboard operability, labels/instructions,
  identified errors, and reduced motion.
- **Full state and content coverage are entailed.** For each affected
  component and viewport, enumerate default, hover where applicable, focus,
  active, selected, disabled, loading, empty, error, success, overflow/long
  content, permission-limited, offline/stale where relevant, and responsive
  behavior. A happy-path-only screen or a component with an undefined state is
  incomplete, not finished.
- **Rendered evidence is the acceptance artifact.** Render the actual UI at
  stable, named viewports and every supported theme/state. When the project has
  visual-regression infrastructure, bind each screenshot to a reproducible
  named render environment (or pinned CI image/config), browser/engine and
  fonts, baseline artifact revision or hash, diff configuration/threshold, and
  justified mask set; Playwright `toHaveScreenshot` is one example, not a
  mandated framework. Record the reviewer/approver identity and evidence
  reference that authorize a baseline update. Replacing a baseline follows
  defect review and is never itself the fix; masked regions receive separate
  semantic/state validation where relevant. Record
  viewport/theme/state and the observed defect. Code-only review must disclose
  `visual not measured`.
  Hand the surface to GUI Dogfood QA for black-box task execution; design-class
  findings return to the brief/token/component/state contract, then rerender
  and rerun the affected matrix. Hand 3D/spatial work to Spatial Forge.

Primary and near-primary sources (checked 2026-07-16): W3C WCAG 2.2
Understanding SC 1.4.3, 1.4.10, 1.4.11, 2.4.3, 2.4.7, and 2.5.8 plus WAI
form/table tutorials (including their conditional-technique scope); DTCG Design
Tokens Format 2025.10; USWDS token, layout, form, and table guidance; NN/g ten
usability heuristics and progressive disclosure; Playwright visual comparisons
(artifact example and same-environment constraint only). Secondary
field reference: Laws of UX — not the original Fitts / Hick / Jakob literature;
cite the originals when a claim depends on a specific law. URLs and source-tier
notes live in `references/sources.md`.
