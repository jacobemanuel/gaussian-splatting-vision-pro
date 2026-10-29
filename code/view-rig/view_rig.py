# the camera rig the study renders every CAD model with, without blender:
# 150 directions on a fibonacci sphere, a camera on each one looking at the model's centre,
# and the poses in the y-up world the splat trainer reads.
# same numbers as the render script, which places the cameras with blender's to_track_quat('-Z', 'Z')

import json
import math

import numpy as np

GOLDEN = (1 + math.sqrt(5)) / 2
# blender is z-up, the trainer (nerfstudio / gsplat) is y-up: a -90 degree turn of the world about x
BLENDER_TO_TRAINER = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], dtype=float)


def fibonacci_sphere(n=150):
    """n unit vectors spread evenly over the sphere, in render order"""
    # the cosine of the polar angle steps evenly, so every band of the sphere gets the same share,
    # and the azimuth turns by the golden ratio each time, so neighbours never line up
    i = np.arange(n)
    theta = np.arccos(1 - 2 * (i + 0.5) / n)
    phi = 2 * math.pi * i / GOLDEN
    return np.stack([np.sin(theta) * np.cos(phi), np.sin(theta) * np.sin(phi), np.cos(theta)], axis=1)


def sphere_radius(bbox_min, bbox_max, scale=2.0):
    """how far every camera sits from the centre: the bounding box diagonal times scale, 5 cm at least"""
    diag = float(np.linalg.norm(np.subtract(bbox_max, bbox_min)))
    return max(diag * scale, 0.05)


def shortest_turn(a, b):
    """rotation that takes unit vector a onto unit vector b along the shortest arc"""
    axis = np.cross(a, b)
    s = float(np.linalg.norm(axis))
    c = float(a @ b)
    if s < 1e-12:
        # parallel: nothing to do, or opposite: half a turn about x, the same fallback blender uses
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    k = axis / s
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + s * K + (1 - c) * K @ K


def camera_to_world(position, target=(0.0, 0.0, 0.0)):
    """4x4 pose of a camera at position looking at target, blender style (it looks down its own -z).
    the turn is the shortest one from -z onto the view direction, which is what to_track_quat('-Z', 'Z')
    gives, so there is no fixed up and the picture's roll changes from view to view"""
    position = np.asarray(position, dtype=float)
    view = np.asarray(target, dtype=float) - position
    view /= np.linalg.norm(view)
    pose = np.eye(4)
    pose[:3, :3] = shortest_turn(np.array([0.0, 0.0, -1.0]), view)
    pose[:3, 3] = position
    return pose


def to_trainer(pose):
    """the same camera in the trainer's y-up world. the world turns, so it's a left multiplication.
    multiplying on the right would turn every camera about its own x axis instead"""
    return BLENDER_TO_TRAINER @ pose


def transforms(bbox_min, bbox_max, n=150, scale=2.0, focal_mm=50.0, sensor_mm=36.0):
    """the camera part of a nerfstudio-style transforms.json for one model"""
    r = sphere_radius(bbox_min, bbox_max, scale)
    frames = [{'file_path': f'images/{i:03d}.png', 'transform_matrix': to_trainer(camera_to_world(d * r)).tolist()}
              for i, d in enumerate(fibonacci_sphere(n))]
    return {'camera_angle_x': 2 * math.atan(sensor_mm / (2 * focal_mm)), 'frames': frames}


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='write the camera poses of the view rig for one bounding box')
    ap.add_argument('--bbox-min', type=float, nargs=3, default=(-0.5, -0.5, -0.5))
    ap.add_argument('--bbox-max', type=float, nargs=3, default=(0.5, 0.5, 0.5))
    ap.add_argument('--n', type=int, default=150)
    ap.add_argument('--out', default='transforms.json')
    a = ap.parse_args()
    with open(a.out, 'w') as f:
        json.dump(transforms(a.bbox_min, a.bbox_max, a.n), f, indent=1)
    print(f'{a.n} cameras written to {a.out}')
