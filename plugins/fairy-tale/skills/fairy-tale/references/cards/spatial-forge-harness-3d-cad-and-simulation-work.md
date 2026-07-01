# Spatial Forge Harness: 3D, CAD, and simulation work

- Require an explicit spatial brief: coordinate system, units, camera,
  interactions, geometry constraints, physics assumptions, and performance
  target.
- Prefer proven engines or libraries for the domain, such as Three.js for
  browser 3D, Unreal Engine or Unity for full game/editor workflows, Blender
  Python or Geometry Nodes for asset and scene generation, platform-native
  renderers for native apps, or CAD APIs for mechanical modeling.
- Build the scene in layers: primitives -> lighting/materials -> controls ->
  physics/simulation -> validation overlays -> polish.
- Verify by rendering the actual output, checking nonblank frames, camera
  framing, interaction, animation, and obvious geometry defects.
- For CAD or printable objects, distinguish visual plausibility from mechanical
  correctness; require dimensional checks before claiming functional design.

