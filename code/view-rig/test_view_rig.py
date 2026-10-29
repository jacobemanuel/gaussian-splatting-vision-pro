# tests for the view rig: the sphere, the cameras and the change of world
import math

import numpy as np

from view_rig import BLENDER_TO_TRAINER, camera_to_world, fibonacci_sphere, shortest_turn, sphere_radius, to_trainer, transforms


def test_150_unit_directions():
    d = fibonacci_sphere(150)
    assert d.shape == (150, 3)
    assert np.allclose(np.linalg.norm(d, axis=1), 1.0)


def test_heights_step_evenly():
    # equal steps in height cut the sphere into bands of equal area, so each band gets one camera
    z = fibonacci_sphere(150)[:, 2]
    assert np.allclose(np.diff(z), -2 / 150)
    assert abs(z.mean()) < 1e-12


def test_first_two_directions_by_hand():
    d = fibonacci_sphere(150)
    t0 = math.acos(1 - 1 / 150)
    assert np.allclose(d[0], (math.sin(t0), 0.0, math.cos(t0)))
    t1, p1 = math.acos(1 - 3 / 150), 2 * math.pi / ((1 + math.sqrt(5)) / 2)
    assert np.allclose(d[1], (math.sin(t1) * math.cos(p1), math.sin(t1) * math.sin(p1), math.cos(t1)))


def test_no_clumps_and_no_holes():
    # every camera's nearest neighbour is between 14 and 16.5 degrees away, close to the ideal 16.6
    d = fibonacci_sphere(150)
    cos = np.clip(d @ d.T, -1, 1)
    np.fill_diagonal(cos, -1)
    nearest = np.degrees(np.arccos(cos.max(axis=1)))
    assert nearest.min() > 14.0
    assert nearest.max() < 16.5


def test_every_camera_looks_at_the_centre():
    for d in fibonacci_sphere(150):
        pose = camera_to_world(d * 3.0)
        assert np.allclose(-pose[:3, 2], -d)  # a blender camera looks down its own -z


def test_poses_are_proper_rotations():
    for d in fibonacci_sphere(150):
        r = camera_to_world(d * 3.0)[:3, :3]
        assert np.allclose(r.T @ r, np.eye(3))
        assert np.isclose(np.linalg.det(r), 1.0)


def test_same_as_blender():
    # rotation matrices blender 5.2 prints for (centre - position).to_track_quat('-Z', 'Z') at radius 3
    blender = {
        0: [[0.993333, 0.0, 0.115277], [0.0, 1.0, 0.0], [-0.115277, 0.0, 0.993333]],
        75: [[0.636794, 0.483435, -0.600654], [0.483435, 0.35654, 0.799482], [0.600654, -0.799482, -0.006667]],
        149: [[-0.453999, -0.885546, 0.098455], [-0.885546, 0.460666, 0.059963], [-0.098455, -0.059963, -0.993333]],
    }
    d = fibonacci_sphere(150)
    for i, m in blender.items():
        assert np.allclose(camera_to_world(d[i] * 3.0)[:3, :3], m, atol=1e-6)


def test_opposite_directions_turn_half_way():
    r = shortest_turn(np.array([0.0, 0.0, -1.0]), np.array([0.0, 0.0, 1.0]))
    assert np.allclose(r @ [0.0, 0.0, -1.0], [0.0, 0.0, 1.0])


def test_change_of_world_keeps_every_view():
    # the world turns: the centre stays put, every camera still looks at it, blender's z becomes the trainer's y
    for d in fibonacci_sphere(150):
        pose = to_trainer(camera_to_world(d * 3.0))
        pos = pose[:3, 3]
        assert np.allclose(-pose[:3, 2], -pos / np.linalg.norm(pos))
        assert np.isclose(pos[1], 3.0 * d[2])


def test_right_multiplication_would_break_the_view():
    # the mistake the left multiplication avoids: turning each camera instead of the world
    pose = camera_to_world(fibonacci_sphere(150)[40] * 3.0)
    wrong = pose @ BLENDER_TO_TRAINER
    pos = wrong[:3, 3]
    assert not np.allclose(-wrong[:3, 2], -pos / np.linalg.norm(pos), atol=1e-3)


def test_radius_from_the_bounding_box():
    assert np.isclose(sphere_radius((0, 0, 0), (3, 4, 0)), 10.0)
    assert sphere_radius((0, 0, 0), (0.01, 0.01, 0.01)) == 0.05


def test_transforms_json():
    t = transforms((-0.5, -0.5, -0.5), (0.5, 0.5, 0.5))
    assert len(t['frames']) == 150
    assert math.isclose(math.degrees(t['camera_angle_x']), 39.5978, abs_tol=1e-3)
    assert np.array(t['frames'][0]['transform_matrix']).shape == (4, 4)
