# Contributing

The specification is behavior-first. Changes fall into three classes:

- **Behavior change** — changes what a user/agent observes; requires an ADR and updated geometry tests.
- **Technical experiment** — changes interpolation or performance internals while preserving behavior; requires benchmark evidence, not a product rewrite.
- **Implementation detail** — Blender/API/storage work already covered by the specification; code and tests are sufficient.

Never promote an experiment into a core invariant because it is mathematically sophisticated or convenient to implement.
