"""Pure patch-local interpolation regressions."""

import importlib.util
import math
import struct
import sys
import types
from pathlib import Path


ROOT = Path(__file__).parents[1]
PACKAGE = "dan_form_core_test"
pkg = types.ModuleType(PACKAGE)
pkg.__path__ = [str(ROOT / "dan_form" / "core")]
sys.modules[PACKAGE] = pkg


def _load(name):
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE}.{name}", ROOT / "dan_form" / "core" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_load("graph")
_load("proportional")
_load("harmonic")
DEFORMATION = _load("deformation")
OPERATION = _load("operation")


class V:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.values = [float(x), float(y), float(z)]

    def __iter__(self):
        return iter(self.values)

    def __sub__(self, other):
        return V(*(a - b for a, b in zip(self.values, other.values)))

    def __add__(self, other):
        return V(*(a + b for a, b in zip(self.values, other.values)))

    def __mul__(self, scalar):
        return V(*(a * scalar for a in self.values))

    __rmul__ = __mul__

    def __truediv__(self, scalar):
        return V(*(a / scalar for a in self.values))

    def copy(self):
        return V(*self.values)

    def __eq__(self, other):
        return isinstance(other, V) and self.values == other.values


def test_moving_boundary_interpolates_toward_stationary_boundary():
    p0 = {index: V(index, 0, 0) for index in range(5)}
    output, changed = DEFORMATION.compute_preview(
        p0,
        moved_targets={0},
        scope=set(p0),
        patches=[{"vertex_ids": list(p0)}],
        edge_vids={index: (index, index + 1) for index in range(4)},
        targets={0: V(1, 0, 0)},
        stationary={4},
        profile="LINEAR",
        radius=0.0,
    )

    assert output[0] == V(1, 0, 0)
    assert output[4] == p0[4]
    assert 1.0 < output[1].values[0] < 2.0
    assert 2.0 < output[2].values[0] < 3.0
    assert changed == 4


def test_nonuniform_loop_targets_are_not_reduced_to_one_average_vector():
    p0 = {index: V(index, 0, 0) for index in range(5)}
    output, _ = DEFORMATION.compute_preview(
        p0,
        moved_targets={0, 4},
        scope=set(p0),
        patches=[{"vertex_ids": list(p0)}],
        edge_vids={index: (index, index + 1) for index in range(4)},
        targets={0: V(1, 0, 0), 4: V(4, 1, 0)},
        stationary=set(),
        profile="LINEAR",
        radius=0.0,
    )

    # The midpoint receives the spatially varying loop displacement, rather
    # than the same averaged vector as every interior vertex.
    assert output[2].values[0] == 2.5
    assert output[2].values[1] == 0.5


def test_finite_radius_cannot_expand_or_cross_patch_scope():
    p0 = {index: V(index, 0, 0) for index in range(7)}
    output, changed = DEFORMATION.compute_preview(
        p0,
        moved_targets={0},
        scope={0, 1, 2, 3},
        patches=[
            {"vertex_ids": [0, 1, 2, 3]},
            {"vertex_ids": [4, 5, 6]},
        ],
        edge_vids={index: (index, index + 1) for index in range(6)},
        targets={0: V(1, 0, 0)},
        stationary=set(),
        profile="LINEAR",
        radius=2.0,
    )

    assert output[0] == V(1, 0, 0)
    assert output[1].values[0] == 1.5
    assert output[2] == p0[2]
    assert output[3] == p0[3]
    assert output[4] == p0[4]
    assert output[5] == p0[5]
    assert output[6] == p0[6]
    assert changed == 2


def test_noop_target_clears_to_operation_rest_exactly():
    p0 = {index: V(index, 0, 0) for index in range(4)}
    output, changed = DEFORMATION.compute_preview(
        p0,
        moved_targets={0},
        scope=set(p0),
        patches=[{"vertex_ids": list(p0)}],
        edge_vids={index: (index, index + 1) for index in range(3)},
        targets={0: p0[0]},
        stationary={3},
        profile="SMOOTH",
        radius=2.0,
    )

    assert output == p0
    assert changed == 0


def test_shared_free_vertex_conflict_is_rejected_before_writeback():
    p0 = {index: V(index, 0, 0) for index in range(4)}
    patches = [
        {"vertex_ids": [0, 1, 2]},
        {"vertex_ids": [1, 2, 3]},
    ]
    edges = {0: (0, 1), 1: (1, 2), 2: (2, 3)}

    try:
        DEFORMATION.compute_preview(
            p0,
            moved_targets={0, 3},
            scope=set(p0),
            patches=patches,
            edge_vids=edges,
            targets={0: V(1, 0, 0), 3: V(3, 2, 0)},
            stationary=set(),
            profile="LINEAR",
            radius=0.0,
        )
    except ValueError as error:
        assert str(error) == "TARGET_CONFLICT"
    else:
        raise AssertionError("shared patch candidates must not be resolved by iteration order")


def test_single_control_owns_rotation_of_the_whole_patch():
    # A planar ring is the common control shape.  The patch continues along X;
    # averaging ring displacements would incorrectly erase the rotation there.
    p0 = {
        0: V(0, 1, 0), 1: V(0, 0, 1), 2: V(0, -1, 0), 3: V(0, 0, -1),
        4: V(1, 0.5, 0.5),
    }
    target = {0: V(0, 0, 1), 1: V(0, -1, 0), 2: V(0, 0, -1), 3: V(0, 1, 0)}
    output, _ = DEFORMATION.compute_preview(
        p0, {0, 1, 2, 3}, set(p0),
        [{"vertex_ids": list(p0), "incident_control_uuids": ["B"]}],
        {0: (0, 1), 1: (1, 2), 2: (2, 3), 3: (3, 4)},
        target, set(), "LINEAR", 0.0,
        control_groups={"B": {0, 1, 2, 3}},
    )

    assert output[4].values[0] == 1.0
    assert abs(output[4].values[1] + 0.5) < 1e-6
    assert abs(output[4].values[2] - 0.5) < 1e-6


def test_single_control_owns_scale_of_the_whole_patch():
    p0 = {0: V(0, 1, 0), 1: V(0, 0, 1), 2: V(1, 0.5, 0.5)}
    target = {0: V(0, 2, 0), 1: V(0, 0, 2)}
    output, _ = DEFORMATION.compute_preview(
        p0, {0, 1}, set(p0),
        [{"vertex_ids": list(p0), "incident_control_uuids": ["B"]}],
        {0: (0, 1), 1: (1, 2)}, target, set(), "LINEAR", 0.0,
        control_groups={"B": {0, 1}},
    )

    assert output[2].values[0] == 1.0
    assert abs(output[2].values[1] - 1.0) < 1e-6
    assert abs(output[2].values[2] - 1.0) < 1e-6


def test_all_selected_controls_scale_as_one_mesh_across_patch_cuts():
    # Two nearly planar control rings divide the mesh into separate patches.
    # Each ring alone cannot determine scale along its normal, but together
    # they define the same full 3D Scale that Blender applied to the proxy.
    def f32(value):
        return struct.unpack("f", struct.pack("f", float(value)))[0]

    p0 = {}
    patches = []
    selected = set()
    edge_vids = {}
    for group, z in enumerate((10.123456, 20.654321)):
        offset = group * 5
        ring = {
            offset: V(f32(10.123456), f32(0.123456), f32(z)),
            offset + 1: V(f32(12.654321), f32(0.123456), f32(z)),
            offset + 2: V(f32(12.654321), f32(2.654321), f32(z)),
            offset + 3: V(f32(10.123456), f32(2.654321), f32(z)),
        }
        p0.update(ring)
        p0[offset + 4] = V(f32(11.4), f32(1.4), f32(z + 1.0))
        selected.update(ring)
        patches.append({"vertex_ids": list(range(offset, offset + 5))})
        for side in range(4):
            edge_vids[offset * 8 + side] = (offset + side, offset + (side + 1) % 4)
            edge_vids[offset * 8 + side + 4] = (offset + side, offset + 4)

    for factor in (1.0, 0.98, 0.9, 0.7, 0.5, 0.4):
        targets = {
            vertex_id: V(*(f32(factor * component) for component in p0[vertex_id]))
            for vertex_id in selected
        }
        output, changed = DEFORMATION.compute_preview(
            p0, selected, set(p0), patches, edge_vids, targets, set(),
            "LINEAR", 0.0, selection_intent=selected,
            all_controls_selected=True,
        )
        if factor == 1.0:
            assert output == p0 and changed == 0
        else:
            assert changed == len(p0)
            for vertex_id, rest in p0.items():
                expected = [factor * component for component in rest]
                assert math.dist(tuple(output[vertex_id]), expected) < 1e-4


def test_single_planar_control_keeps_axis_scale_continuous_for_free_patch_vertices():
    # Four non-collinear samples define an in-plane non-uniform Scale.  The
    # free center must follow that same affine field; a coherent whole-control
    # transform must not be mistaken for unrelated per-vertex targets.
    p0 = {
        0: V(-1, -1, 0), 1: V(1, -1, 0), 2: V(1, 1, 0),
        3: V(-1, 1, 0), 4: V(0, 0, 0), 5: V(0, 0, 1),
    }
    edges = {
        0: (0, 1), 1: (1, 2), 2: (2, 3), 3: (3, 0),
        4: (0, 4), 5: (1, 4), 6: (2, 4), 7: (3, 4),
    }
    selected = {0, 1, 2, 3}
    targets = {vertex_id: V(p0[vertex_id].values[0] * 1.7,
                            p0[vertex_id].values[1] * 0.45, 0)
               for vertex_id in selected}
    output, _ = DEFORMATION.compute_preview(
        p0, selected, set(p0),
        [{"vertex_ids": list(p0), "incident_control_uuids": ["RING"]}],
        edges, targets, set(), "LINEAR", 0.0,
        control_groups={"RING": selected},
    )
    assert abs(output[4].values[0]) < 1e-6
    assert abs(output[4].values[1]) < 1e-6
    assert abs(output[4].values[2]) < 1e-6
    assert abs(output[5].values[2] - 1.0) < 1e-6


def test_axis_scale_keeps_unchanged_selected_loop_in_the_transforming_region():
    sides = 8
    for axis in range(3):
        across = (axis + 1) % 3
        p0 = {}
        edges = {}
        for ring, radius in enumerate((1.0, 0.75, 0.5)):
            for side in range(sides):
                angle = 2.0 * math.pi * side / sides
                coordinates = [0.0, 0.0, 0.0]
                coordinates[axis] = radius * math.cos(angle)
                coordinates[across] = radius * math.sin(angle)
                vertex_id = ring * sides + side
                p0[vertex_id] = V(*coordinates)
                edges[ring * sides + side] = (
                    vertex_id, ring * sides + (ring * sides + (side + 1) % sides)
                )
                if ring:
                    edges[100 + ring * sides + side] = (
                        (ring - 1) * sides + side, vertex_id
                    )

        intent = set(range(sides))
        moved = {vertex_id for vertex_id in intent
                 if abs(p0[vertex_id].values[axis]) > 1e-10}
        targets = {}
        for vertex_id in moved:
            coordinates = p0[vertex_id].values.copy()
            coordinates[axis] *= 1.6
            targets[vertex_id] = V(*coordinates)
        patch = [{"vertex_ids": list(p0)}]

        free_patch, _ = DEFORMATION.compute_preview(
            p0, moved, set(p0), patch, edges, targets, set(), "LINEAR", 0.0,
            selection_intent=intent,
        )
        for side in range(sides):
            source = p0[sides + side]
            result = free_patch[sides + side]
            assert abs(result.values[axis] - source.values[axis] * 1.6) < 1e-6
            for component in set(range(3)) - {axis}:
                assert abs(result.values[component] - source.values[component]) < 1e-6
        for vertex_id in intent - moved:
            assert free_patch[vertex_id] == p0[vertex_id]

        fixed_loop = set(range(2 * sides, 3 * sides))
        anchored_patch, _ = DEFORMATION.compute_preview(
            p0, moved, set(p0), patch, edges, targets, fixed_loop, "LINEAR", 0.0,
            selection_intent=intent,
        )
        assert all(anchored_patch[vertex_id] == p0[vertex_id]
                   for vertex_id in fixed_loop)
        assert any(anchored_patch[sides + side] != free_patch[sides + side]
                   for side in range(sides))


def test_radius_zero_preserves_ratio_between_moving_and_stationary_boundaries():
    # A one-dimensional patch models a cylinder section: the top boundary
    # moves, the bottom boundary is an unselected control, and the middle
    # vertex must receive exactly half of the boundary displacement.
    p0 = {0: V(0, 1, 0), 1: V(0, 1, 1), 2: V(0, 1, 2)}
    target = {0: V(0, 1, 1)}
    output, _ = DEFORMATION.compute_preview(
        p0, {0}, set(p0),
        [{"vertex_ids": list(p0), "incident_control_uuids": ["TOP"]}],
        {0: (0, 1), 1: (1, 2)}, target, {2}, "LINEAR", 0.0,
        control_groups={"TOP": {0}},
    )
    assert abs(output[1].values[2] - 1.5) < 1e-6
    assert output[2] == p0[2]


def test_cylinder_rings_keep_their_longitudinal_ratios_when_controls_approach():
    # This matches the user's basic-cylinder case: two control rings and five
    # free rings.  Both uniform and irregular initial spacing must retain the
    # same fraction of the new total height across every circumferential point.
    for heights in (
        [0, 1, 2, 3, 4, 5, 6],
        [0, 0.25, 0.75, 1.5, 2.5, 4, 6],
    ):
        sides = 8
        p0 = {}
        edges = {}
        next_edge = 0
        for ring, height in enumerate(heights):
            for side in range(sides):
                vertex_id = ring * sides + side
                angle = 2 * math.pi * side / sides
                p0[vertex_id] = V(math.cos(angle), math.sin(angle), height)
                edges[next_edge] = (vertex_id, ring * sides + (side + 1) % sides)
                next_edge += 1
                if ring:
                    edges[next_edge] = ((ring - 1) * sides + side, vertex_id)
                    next_edge += 1
        selected = set(range((len(heights) - 1) * sides, len(heights) * sides))
        stationary = set(range(sides))
        targets = {vertex_id: p0[vertex_id] + V(0, 0, -3) for vertex_id in selected}
        output, _ = DEFORMATION.compute_preview(
            p0, selected, set(p0),
            [{"vertex_ids": list(p0), "incident_control_uuids": ["top", "bottom"]}],
            edges, targets, stationary, "LINEAR", 0.0,
            control_groups={"top": selected, "bottom": stationary},
        )
        for ring, height in enumerate(heights):
            expected_z = height * 0.5
            for side in range(sides):
                actual = output[ring * sides + side]
                assert abs(actual.values[2] - expected_z) < 1e-6
                assert abs(actual.values[0] - p0[ring * sides + side].values[0]) < 1e-6
                assert abs(actual.values[1] - p0[ring * sides + side].values[1]) < 1e-6


def test_unselected_control_is_an_identity_anchor_for_shared_patch():
    p0 = {index: V(index, 0, 0) for index in range(5)}
    target = {0: V(1, 0, 0), 1: V(2, 0, 0)}
    output, _ = DEFORMATION.compute_preview(
        p0, {0, 1}, set(p0),
        [{"vertex_ids": list(p0), "incident_control_uuids": ["A", "B"]}],
        {index: (index, index + 1) for index in range(4)}, target, {3, 4},
        "LINEAR", 0.0,
        control_groups={"A": {0, 1}, "B": {3, 4}},
    )

    assert output[0] == target[0]
    assert output[1] == target[1]
    assert output[3] == p0[3]
    assert output[4] == p0[4]
    assert 2.0 < output[2].values[0] < 3.0


def test_native_proportional_targets_shape_the_patch_from_each_vertex():
    # A cylinder side unwrapped as a grid. The right control line has a local
    # proportional bulge; every untouched point on either line stays pinned.
    width, height = 7, 7
    vertex_id = lambda x, y: y * width + x
    p0 = {vertex_id(x, y): V(x, y, 0)
          for y in range(height) for x in range(width)}
    edges = {}
    for y in range(height):
        for x in range(width):
            current = vertex_id(x, y)
            if x:
                edges[len(edges)] = (current, vertex_id(x - 1, y))
            if y:
                edges[len(edges)] = (current, vertex_id(x, y - 1))
    moved = {vertex_id(6, y): V(6 + delta, y, 0)
             for y, delta in ((2, 0.5), (3, 1.0), (4, 0.5))}
    fixed = {vertex_id(x, y) for y in range(height) for x in (0, 6)} - set(moved)
    args = (p0, set(moved), set(p0), [{"vertex_ids": list(p0)}],
            edges, moved, fixed, "LINEAR", 0.0)
    grouped, _ = DEFORMATION.compute_preview(
        *args, control_groups={"left": {vertex_id(0, y) for y in range(height)},
                               "right": {vertex_id(6, y) for y in range(height)}},
        selection_intent={vertex_id(6, 3)},
    )
    regrouped, _ = DEFORMATION.compute_preview(
        *args,
        control_groups={"all": set(moved) | fixed},
        selection_intent={vertex_id(6, 3)},
    )

    assert grouped == regrouped
    for vertex_id_, target in moved.items():
        assert grouped[vertex_id_] == target
    for vertex_id_ in fixed:
        assert grouped[vertex_id_] == p0[vertex_id_]
    displacement = lambda x, y: grouped[vertex_id(x, y)].values[0] - x
    assert 0.0 < displacement(3, 0) < displacement(3, 2) < displacement(3, 3) < 1.0
    assert abs(displacement(3, 2) - displacement(3, 4)) < 1e-7
    assert all(-1e-8 <= displacement(x, y) <= 1.0 + 1e-8
               for y in range(height) for x in range(width))


def test_no_movement_with_selection_intent_is_exact_no_op():
    p0 = {index: V(index, index * 0.5, 0) for index in range(4)}
    output, changed = DEFORMATION.compute_preview(
        p0, set(), set(p0), [{"vertex_ids": list(p0)}],
        {index: (index, index + 1) for index in range(3)}, {}, set(),
        "LINEAR", 0.0, selection_intent={1, 2},
    )
    assert output == p0
    assert changed == 0


def test_canonical_operation_resolves_absolute_targets_for_agent_and_ui():
    p0 = {0: V(0, 1, 0), 1: V(1, 0, 0)}
    transform = OPERATION.OperationTransform(
        operation="ROTATE", pivot=(0, 0, 0), rotation=(0.0, 0.0, 1.5707963267948966)
    )
    targets = OPERATION.targets_from_transform(p0, set(p0), transform)
    assert abs(targets[0].values[0] + 1.0) < 1e-6
    assert abs(targets[0].values[1]) < 1e-6
    assert abs(targets[1].values[0]) < 1e-6
    assert abs(targets[1].values[1] - 1.0) < 1e-6


def test_canonical_operation_matches_xyz_rotation_order_on_each_axis():
    cases = (
        ((math.pi / 2, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        ((0.0, math.pi / 2, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
        ((0.0, 0.0, math.pi / 2), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    )
    for rotation, source, expected in cases:
        transform = OPERATION.OperationTransform(
            operation="ROTATE", rotation=rotation,
        )
        target = OPERATION.targets_from_transform({0: V(*source)}, {0}, transform)[0]
        assert all(abs(actual - wanted) < 1e-6
                   for actual, wanted in zip(target.values, expected))


def test_world_space_requires_an_explicit_source_matrix():
    transform = OPERATION.OperationTransform(operation="MOVE", space="WORLD",
                                             translation=(1.0, 0.0, 0.0))
    try:
        OPERATION.targets_from_transform({0: V(0, 0, 0)}, {0}, transform)
    except ValueError as exc:
        assert str(exc) == "WORLD_SPACE_MATRIX_REQUIRED"
    else:
        raise AssertionError("WORLD transforms must not be silently treated as local")


def test_world_space_rejects_a_singular_source_matrix():
    class SingularMatrix:
        def __iter__(self):
            return iter(((0.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0),
                          (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0)))

        def inverted(self):
            raise ValueError("matrix is singular")

    transform = OPERATION.OperationTransform(operation="MOVE", space="WORLD")
    try:
        OPERATION.targets_from_transform({0: V(1, 2, 3)}, {0}, transform,
                                         source_to_world=SingularMatrix())
    except ValueError as exc:
        assert str(exc) == "WORLD_SPACE_MATRIX_SINGULAR"
    else:
        raise AssertionError("singular WORLD frames must be rejected")
