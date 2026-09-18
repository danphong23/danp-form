# Product Definition

**Status: Normative**

## Simple description

DANP Form lets a person or AI reshape an existing template mesh by manipulating a sparse network of control lines that are backed by real Source topology.

The user creates controls once, then works mainly with ordinary selection and G/R/S. Effective enabled control edges divide the surface into topology-derived patches. When a control changes, only patches incident to that control are eligible to deform. Their **current dense shape** is retained as the operation baseline, and a smooth displacement is propagated from control targets into the patch according to the proportional setting.

The result is written directly to the Source Mesh without changing topology.

## Product promise

A small number of predictable control actions should be enough to make broad and local shape edits while retaining the useful form already present in the template/current mesh.

## Core workflow

```text
1 Source Edit Mode: select real edges/vertices → Make Control
2 DANP Form derives patches from enabled control edges
3 Control Proxy: select node/edge/control
4 G / R / S or explicit numeric target
5 Resolve selected node/strip/span/loop geometry into Source targets; other enabled vertices hold
6 Propagate those targets over adjacent patches
7 Write preview from immutable Operation Rest
8 Commit → Source becomes the new current shape
```

## Core does not know semantics

`front`, `side`, `arm`, `leg`, `head`, `car`, or anatomical meaning are not core concepts. A control is just source topology plus interaction metadata.

## Non-goals of core

Core does not require:

- automatic image segmentation;
- camera calibration;
- AI 3D reconstruction;
- semantic anatomy recognition;
- a permanent deformation modifier;
- a rig/armature replacement;
- a specific numerical solver family.

Reference fitting may be added later only as a **target producer** for the same controls.

Enabled unselected controls hold their coordinates. DANP Form Hide releases a line or
portion from both constraints and patch cuts; Reveal restores it on the current mesh.
This replaces a separate deactivate/nesting system. See leg-control-examples.md.
