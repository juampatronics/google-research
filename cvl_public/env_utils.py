# coding=utf-8
# Copyright 2025 The Google Research Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utility for loading the goal-conditioned environments."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import random

import d4rl  # pylint: disable=unused-import
from dopamine.replay_memory import circular_replay_buffer
import gym
from gym import spaces
import metaworld
import numpy as np
import tensorflow as tf

from cvl_public import ant_env
from cvl_public import fetch_envs
from cvl_public import point_env

os.environ['SDL_VIDEODRIVER'] = 'dummy'

METAWORLD_50_ENVS = [
    'assembly',
    'basketball',
    'bin-picking',
    'box-close',
    'button-press-topdown',
    'button-press-topdown-wall',
    'button-press',
    'button-press-wall',
    'coffee-button',
    'coffee-pull',
    'coffee-push',
    'dial-turn',
    'disassemble',
    'door-close',
    'door-lock',
    'door-open',
    'door-unlock',
    'hand-insert',
    'drawer-close',
    'drawer-open',
    'faucet-open',
    'faucet-close',
    'hammer',
    'handle-press-side',
    'handle-press',
    'handle-pull-side',
    'handle-pull',
    'lever-pull',
    'peg-insert-side',
    'pick-place-wall',
    'pick-out-of-hole',
    'reach',
    'push-back',
    'push',
    'pick-place',
    'plate-slide',
    'plate-slide-side',
    'plate-slide-back',
    'plate-slide-back-side',
    'peg-unplug-side',
    'soccer',
    'stick-push',
    'stick-pull',
    'push-wall',
    'reach-wall',
    'shelf-place',
    'sweep-into',
    'sweep',
    'window-open',
    'window-close',
]

METAWORLD_10_ENVS = [
    'reach',
    'push',
    'pick-place',
    'door-open',
    'drawer-close',
    'button-press-topdown',
    'peg-insert-side',
    'window-open',
    'sweep',
    'basketball',
]

FETCH_ENVS = ['FetchSlide', 'FetchPickAndPlace', 'FetchReach', 'FetchPush']

DMC_ENVS = [
    'cartpole-swingup', 'finger-spin', 'cheetah-run', 'reacher-easy',
    'walker-walk', 'walker-run'
]

D4RL_ANT_ENVS = [
    'antmaze-umaze-v2', 'antmaze-umaze-diverse-v2', 'antmaze-medium-play-v2',
    'antmaze-medium-diverse-v2', 'antmaze-large-play-v2',
    'antmaze-large-diverse-v2'
]

D4RL_MAZE2d_ENVS = [
    'maze2d-open-dense-v0', 'maze2d-umaze-dense-v1', 'maze2d-medium-dense-v1',
    'maze2d-large-dense-v1'
]

D4RL_GYM_ENVS = [
    'halfcheetah-medium-v2', 'halfcheetah-medium-replay-v2',
    'walker2d-medium-v2', 'walker2d-medium-replay-v2', 'hopper-medium-v2',
    'hopper-medium-replay-v2', 'ant-medium-v2', 'ant-medium-replay-v2'
]

D4RL_ADROIT_ENVS = ['hammer-human-v1', 'hammer-cloned-v1']


def euler2quat(euler):
  """Convert Euler angles to quaternions."""
  euler = np.asarray(euler, dtype=np.float64)
  assert euler.shape[-1] == 3, 'Invalid shape euler {}'.format(euler)

  ai, aj, ak = euler[..., 2] / 2, -euler[..., 1] / 2, euler[..., 0] / 2
  si, sj, sk = np.sin(ai), np.sin(aj), np.sin(ak)
  ci, cj, ck = np.cos(ai), np.cos(aj), np.cos(ak)
  cc, cs = ci * ck, ci * sk
  sc, ss = si * ck, si * sk

  quat = np.empty(euler.shape[:-1] + (4,), dtype=np.float64)
  quat[..., 0] = cj * cc + sj * ss
  quat[..., 3] = cj * sc - sj * cs
  quat[..., 2] = -(cj * ss + sj * cc)
  quat[..., 1] = cj * cs - sj * sc
  return quat


class StateWrapper:
  """Native state for generic OpenAI Gym envs."""

  def __init__(self,
               env,):
    self.env = env

    self.state_space = env.observation_space
    self.observation_space = env.observation_space
    self.action_space = env.action_space

  def set_task(self, task):
    return self.env.set_task(task)

  def reset(self):
    state = self.env.reset()
    return state, state

  def step(self, action):
    next_state, rew, done, info = self.env.step(action)
    return (next_state, next_state), rew, done, info

  def seed(self, seed):
    self.env.seed(seed)

  def close(self):
    self.env.close()


class PixelWrapper:
  """Pixel rendering for generic OpenAI Gym envs."""

  def __init__(self,
               env,
               height=96,
               width=96,
               n_channels=3,
               camera_name='corner3'):
    self.env = env
    self.height = height
    self.width = width
    self.n_channels = n_channels
    self.camera_name = camera_name

    self.state_space = env.observation_space
    self.observation_space = spaces.Box(
        low=0,
        high=255,
        shape=[self.height, self.width, self.n_channels],
        dtype=np.uint8)
    self.action_space = env.action_space

  def set_task(self, task):
    return self.env.set_task(task)

  def reset(self):
    state = self.env.reset()
    obs = self._render()
    return obs, state

  def step(self, action):
    next_state, rew, done, info = self.env.step(action)
    next_obs = self._render()
    return (next_obs, next_state), rew, done, info

  def _render(self):
    obs = self.env.render(
        resolution=(self.height, self.width),
        offscreen=True,
        camera_name=self.camera_name)
    return obs.copy()  # [h,w,n_channels]

  def seed(self, seed):
    self.env.seed(seed)

  def close(self):
    self.env.close()


class DopamineReplayDatasetWrapper:
  """Offline Dopamine replay buffer wrapper."""

  def __init__(self, env, path):
    self.env = env
    self.observation_space = self.env.observation_space
    self.observation_shape = self.observation_space.shape
    self.observation_dtype = self.observation_space.dtype
    self.action_space = self.env.action_space
    self.path = path
      ml1 = metaworld.ML1(name)
      env = ml1.train_classes[name]()
      task = random.choice(ml1.train_tasks)
      env.set_task(task)  # Set task
      if camera_position is not None:
        env.model.cam_pos[2][:] = camera_position

      if obs_type == 'pixels':
        env = PixelWrapper(
            env,
            height=height,
            width=width,
            n_channels=n_channels,
            camera_name=camera_name)
      else:
        env = StateWrapper(env)
      env = DopamineReplayDatasetWrapper(env, path=dataset_path)
      return env
    CLASS = make_metaworld
  elif env_name.startswith('offline_') and env_name.split(
      'offline_')[-1] in D4RL_GYM_ENVS:
    CLASS = lambda: gym.make(env_name.split('offline_')[-1])
    is_gc = False
  else:
    raise NotImplementedError('Unsupported environment: %s' % env_name)

  # Disable type checking in line below because different environments have
  # different kwargs, which pytype doesn't reason about.
  gym_env = CLASS(**kwargs)  # pytype: disable=wrong-keyword-args
  obs_dim = gym_env.observation_space.shape[0] // 2
  if env_name.startswith('offline_') and env_name.split(
      'offline_')[-1] in D4RL_GYM_ENVS:
    max_episode_steps = gym_env._max_episode_steps  # pylint: disable=protected-access
  return gym_env, obs_dim, max_episode_steps, is_gc


class SawyerPush(metaworld.envs.mujoco.env_dict.ALL_V2_ENVIRONMENTS['push-v2']):
  """Wrapper for the SawyerPush environment."""

  def __init__(self,
               goal_min_x=-0.1,
               goal_min_y=0.5,
               goal_max_x=0.1,
               goal_max_y=0.9):
    super(SawyerPush, self).__init__()
    self._random_reset_space.low[3] = goal_min_x
    self._random_reset_space.low[4] = goal_min_y
    self._random_reset_space.high[3] = goal_max_x
    self._random_reset_space.high[4] = goal_max_y
    self._partially_observable = False
    self._freeze_rand_vec = False
    self._set_task_called = True
    self.reset()
    self._freeze_rand_vec = False  # Set False to randomize the goal position.

  @property
  def observation_space(self):
    return gym.spaces.Box(
        low=np.full(14, -np.inf),
        high=np.full(14, np.inf),
        dtype=np.float32)

  def _get_obs(self):
    finger_right, finger_left = (self._get_site_pos('rightEndEffector'),
                                 self._get_site_pos('leftEndEffector'))
    tcp_center = (finger_right + finger_left) / 2.0
    gripper_distance = np.linalg.norm(finger_right - finger_left)
    gripper_distance = np.clip(gripper_distance / 0.1, 0., 1.)
    obj = self._get_pos_objects()
    # Note: we should ignore the target gripper distance. The arm goal is set
    # to be the same as the puck goal.
    state = np.concatenate([tcp_center, obj, [gripper_distance]])
    goal = np.concatenate([self._target_pos, self._target_pos, [0.5]])
    return np.concatenate([state, goal]).astype(np.float32)

  def step(self, action):
    obs = super(SawyerPush, self).step(action)
    dist = np.linalg.norm(self._target_pos - self._get_pos_objects())
    r = float(dist < 0.05)  # Taken from the metaworld code.
    return obs, r, False, {}


class SawyerDrawer(
    metaworld.envs.mujoco.env_dict.ALL_V2_ENVIRONMENTS['drawer-close-v2']):
  """Wrapper for the SawyerDrawer environment."""

  def __init__(self):
    super(SawyerDrawer, self).__init__()
    self._random_reset_space.low[0] = 0
    self._random_reset_space.high[0] = 0
    self._partially_observable = False
    self._freeze_rand_vec = False
    self._set_task_called = True
    self._target_pos = np.zeros(0)  # We will overwrite this later.
    self.reset()
    self._freeze_rand_vec = False  # Set False to randomize the goal position.

  def _get_pos_objects(self):
    return self.get_body_com('drawer_link') +  np.array([.0, -.16, 0.0])

  def reset_model(self):
    super(SawyerDrawer, self).reset_model()
    self._set_obj_xyz(np.random.uniform(-0.15, 0.0))
    self._target_pos = self._get_pos_objects().copy()

    self._set_obj_xyz(np.random.uniform(-0.15, 0.0))
    return self._get_obs()

  @property
  def observation_space(self):
    return gym.spaces.Box(
        low=np.full(8, -np.inf),
        high=np.full(8, np.inf),
        dtype=np.float32)

  def _get_obs(self):
    finger_right, finger_left = (self._get_site_pos('rightEndEffector'),
                                 self._get_site_pos('leftEndEffector'))
    tcp_center = (finger_right + finger_left) / 2.0
    obj = self._get_pos_objects()
    # Arm position is same as drawer position. We only provide the drawer
    # Y coordinate.
    return np.concatenate([tcp_center, [obj[1]],
                           self._target_pos, [self._target_pos[1]]])

  def step(self, action):
    obs = super(SawyerDrawer, self).step(action)
    return obs, 0.0, False, {}


class SawyerWindow(
    metaworld.envs.mujoco.env_dict.ALL_V2_ENVIRONMENTS['window-open-v2']):
  """Wrapper for the SawyerWindow environment."""

  def __init__(self):
    super(SawyerWindow, self).__init__()
    self._random_reset_space.low[:2] = np.array([0.0, 0.8])
    self._random_reset_space.high[:2] = np.array([0.0, 0.8])
    self._partially_observable = False
    self._freeze_rand_vec = False
    self._set_task_called = True
    self._target_pos = np.zeros(3)  # We will overwrite this later.
    self.reset()
    self._freeze_rand_vec = False  # Set False to randomize the goal position.

  def reset_model(self):
    super(SawyerWindow, self).reset_model()
    self.data.set_joint_qpos('window_slide', np.random.uniform(0.0, 0.2))
    self._target_pos = self._get_pos_objects().copy()
    self.data.set_joint_qpos('window_slide', np.random.uniform(0.0, 0.2))
    return self._get_obs()

  @property
  def observation_space(self):
    return gym.spaces.Box(
        low=np.full(8, -np.inf),
        high=np.full(8, np.inf),
        dtype=np.float32)

  def _get_obs(self):
    finger_right, finger_left = (self._get_site_pos('rightEndEffector'),
                                 self._get_site_pos('leftEndEffector'))
    tcp_center = (finger_right + finger_left) / 2.0
    obj = self._get_pos_objects()
    # Arm position is same as window position. Only use X position of window.
    return np.concatenate([tcp_center, [obj[0]],
                           self._target_pos,
                           [self._target_pos[0]]]).astype(np.float32)

  def step(self, action):
    obs = super(SawyerWindow, self).step(action)
    return obs, 0.0, False, {}


class SawyerBin(
    metaworld.envs.mujoco.env_dict.ALL_V2_ENVIRONMENTS['bin-picking-v2']):
  """Wrapper for the SawyerBin environment."""

  def __init__(self):
    self._goal = np.zeros(3)
    super(SawyerBin, self).__init__()
    self._partially_observable = False
    self._freeze_rand_vec = False
    self._set_task_called = True
    self.reset()
    self._freeze_rand_vec = False  # Set False to randomize the goal position.

  def reset(self):
    super(SawyerBin, self).reset()
    body_id = self.model.body_name2id('bin_goal')
    pos1 = self.sim.data.body_xpos[body_id].copy()
    pos1 += np.random.uniform(-0.05, 0.05, 3)
    pos2 = self._get_pos_objects().copy()
    t = np.random.random()
    self._goal = t * pos1 + (1 - t) * pos2
    self._goal[2] = np.random.uniform(0.03, 0.12)
    return self._get_obs()

  def step(self, action):
    super(SawyerBin, self).step(action)
    dist = np.linalg.norm(self._goal - self._get_pos_objects())
    r = float(dist < 0.05)  # Taken from metaworld
    done = False
    info = {}
    return self._get_obs(), r, done, info

  def _get_obs(self):
    pos_hand = self.get_endeff_pos()
    finger_right, finger_left = (
        self._get_site_pos('rightEndEffector'),
        self._get_site_pos('leftEndEffector')
    )
    gripper_distance_apart = np.linalg.norm(finger_right - finger_left)
    gripper_distance_apart = np.clip(gripper_distance_apart / 0.1, 0., 1.)
    obs = np.concatenate((pos_hand, [gripper_distance_apart],
                          self._get_pos_objects()))
    goal = np.concatenate([self._goal + np.array([0.0, 0.0, 0.03]),
                           [0.4], self._goal])
    return np.concatenate([obs, goal]).astype(np.float32)

  @property
  def observation_space(self):
    return gym.spaces.Box(
        low=np.full(2 * 7, -np.inf),
        high=np.full(2 * 7, np.inf),
        dtype=np.float32)


class SawyerDrawerImage(SawyerDrawer):
  """Wrapper for the SawyerDrawer environment with image observations."""

  def __init__(self, camera='corner2', task='openclose'):
    self._task = task
    self._camera_name = camera
    self._dist = []
    self._dist_vec = []
    super(SawyerDrawerImage, self).__init__()

  def reset_metrics(self):
    self._dist_vec = []
    self._dist = []

  def step(self, action):
    _, _, done, info = super(SawyerDrawerImage, self).step(action)
    y = self._get_pos_objects()[1]
    # L1 distance between current and target drawer location.
    dist = abs(y - self._goal_y)
    self._dist.append(dist)
    r = float(dist < 0.04)
    img = self._get_img()
    return np.concatenate([img, self._goal_img], axis=-1), r, done, info

  def _move_hand_to_obj(self):
    for _ in range(20):
      self.data.set_mocap_pos(
          'mocap', self._get_pos_objects() + np.array([0.0, 0.0, 0.03]))
      self.data.set_mocap_quat('mocap', np.array([1, 0, 1, 0]))
      self.do_simulation([-1, 1], self.frame_skip)

  def reset(self):
    if self._dist:
      self._dist_vec.append(self._dist)
    self._dist = []

    # reset the cameras
    camera_name = 'behindGripper'
    index = self.model.camera_name2id(camera_name)
    self.model.cam_fovy[index] = 30.0

    camera_name = 'topview'
    index = self.model.camera_name2id(camera_name)
    self.model.cam_fovy[index] = 20.0
    self.model.cam_pos[index][1] = 0.7

    camera_name = 'corner2'
    index = self.model.camera_name2id(camera_name)
    self.model.cam_fovy[index] = 8.0
    self.model.cam_pos[index][0] = 1.5
    self.model.cam_pos[index][1] = -0.2
    self.model.cam_pos[index][2] = 1.1

    camera_name = 'corner3'
    index = self.model.camera_name2id(camera_name)
    self.model.cam_fovy[index] = 30.0
    self.model.cam_pos[index][0] = 0.3
    self.model.cam_pos[index][1] = 0.45
    self.model.cam_pos[index][2] = 0.7

    # Get the goal image.
    super(SawyerDrawerImage, self).reset()
    self._move_hand_to_obj()
    self._goal_y = self._get_pos_objects()[1]
    self._goal_img = self._get_img()

    # Reset the environment again.
    super(SawyerDrawerImage, self).reset()
    if self._task == 'close':
      self._set_obj_xyz(-0.15)
    elif self._task == 'open':
      self._set_obj_xyz(0.0)
    else:
      assert self._task == 'openclose'
      self._set_obj_xyz(np.random.choice([-0.15, 0.0]))
    self._move_hand_to_obj()
    img = self._get_img()

    # Add the initial distance.
    y = self._get_pos_objects()[1]
    # L1 distance between current and target drawer location.
    dist = abs(y - self._goal_y)
    self._dist.append(dist)
    return np.concatenate([img, self._goal_img], axis=-1)

  def _get_img(self):
    assert self._camera_name in ['behindGripper', 'topview',
                                 'corner2', 'corner3']
    # Hide the goal marker position
    self._set_pos_site('goal', np.inf * self._target_pos)
    # IMPORTANT: Pull the context to the current thread.
    for ctx in self.sim.render_contexts:
      ctx.opengl_context.make_context_current()

    img = self.render(offscreen=True,
                      resolution=(64, 64),
                      camera_name=self._camera_name)
    if self._camera_name in ['behindGripper']:
      img = img[::-1]
    return img.flatten()

  @property
  def observation_space(self):
    return gym.spaces.Box(
        low=np.full((64*64*6), 0),
        high=np.full((64*64*6), 255),
        dtype=np.uint8)


class SawyerPushImage(
    metaworld.envs.mujoco.env_dict.ALL_V2_ENVIRONMENTS['push-v2']):
  """Wrapper for the SawyerPush environment with image observations."""

  def __init__(self, camera='corner2', rand_y=True, start_at_obj=False):
    self._start_at_obj = start_at_obj
    self._rand_y = rand_y
    self._camera_name = camera
    self._dist = []
    self._dist_vec = []
    super(SawyerPushImage, self).__init__()
    self._partially_observable = False
    self._freeze_rand_vec = False
    self._set_task_called = True
    self.reset()
    self._freeze_rand_vec = False  # Set False to randomize the goal position.

  def reset(self):
    if self._dist:
      self._dist_vec.append(self._dist)
    self._dist = []

    camera_name = 'corner'
    index = self.model.camera_name2id(camera_name)
    self.model.cam_fovy[index] = 20.0
    self.model.cam_pos[index][2] = 0.5
    self.model.cam_pos[index][0] = -1.0

    camera_name = 'corner2'
    index = self.model.camera_name2id(camera_name)
    self.model.cam_fovy[index] = 45
    self.model.cam_pos[index][0] = 0.7
    self.model.cam_pos[index][1] = 0.65
    self.model.cam_pos[index][2] = 0.1
    self.model.cam_quat[index] = euler2quat(
        np.array([-np.pi / 2, np.pi / 2, 0.0]))

    # Get the goal image.
    s = super(SawyerPushImage, self).reset()
    self._goal = s[:7][3:6]
    self._goal[1] += np.random.uniform(0.0, 0.25)
    if self._rand_y:
      self._goal[0] += np.random.uniform(-0.1, 0.1)
    self._set_obj_xyz(self._goal)
    for _ in range(200):
      self.data.set_mocap_pos('mocap', self._get_pos_objects())
      self._set_obj_xyz(self._goal)
      self.do_simulation([-1, 1], self.frame_skip)
    self._goal_img = self._get_img()

    # Reset the environment again.
    s = super(SawyerPushImage, self).reset()
    obj = s[:7][3:6] + np.array([0.0, -0.2, 0.0])
    self._set_obj_xyz(obj)
    self.do_simulation([-1, 1], self.frame_skip)
    if self._start_at_obj:
      for _ in range(20):
        self.data.set_mocap_pos('mocap', self._get_pos_objects())
        self.do_simulation([-1, 1], self.frame_skip)
    img = self._get_img()

    # Add the first distances
    obj = self.get_body_com('obj')
    dist = np.linalg.norm(obj - self._goal)
    self._dist.append(dist)
    return np.concatenate([img, self._goal_img], axis=-1)

  def step(self, action):
    super(SawyerPushImage, self).step(action)
    obj = self.get_body_com('obj')
    dist = np.linalg.norm(obj - self._goal)
    r = float(dist < 0.05)  # Taken from the metaworld code.
    self._dist.append(dist)
    img = self._get_img()
    done = False
    info = {}
    return np.concatenate([img, self._goal_img], axis=-1), r, done, info

  def _get_img(self):
    if self._camera_name.startswith('default-'):
      camera_name = self._camera_name.split('default-')[1]
    else:
      camera_name = self._camera_name
    # Hide the goal marker position.
    self._set_pos_site('goal', np.inf * self._target_pos)
    # IMPORTANT: Pull the context to the current thread.
    for ctx in self.sim.render_contexts:
      ctx.opengl_context.make_context_current()
    img = self.render(offscreen=True, resolution=(64, 64),
                      camera_name=camera_name)
    if camera_name in ['behindGripper']:
      img = img[::-1]
    return img.flatten()

  @property
  def observation_space(self):
    return gym.spaces.Box(
        low=np.full((64*64*6), 0),
        high=np.full((64*64*6), 255),
        dtype=np.uint8)


class SawyerWindowImage(SawyerWindow):
  """Wrapper for the SawyerWindow environment with image observations."""

  def __init__(self, task=None, start_at_obj=True):
    self._start_at_obj = start_at_obj
    self._task = task
    self._camera_name = 'corner2'
    self._dist = []
    self._dist_vec = []
    super(SawyerWindowImage, self).__init__()

  def reset_metrics(self):
    self._dist_vec = []
    self._dist = []

  def step(self, action):
    _, _, done, info = super(SawyerWindowImage, self).step(action)
    x = self.data.get_joint_qpos('window_slide')
    # L1 distance between current and target drawer location.
    dist = abs(x - self._goal_x)
    self._dist.append(dist)
    r = (dist < 0.05)
    img = self._get_img()
    return np.concatenate([img, self._goal_img], axis=-1), r, done, info

  def reset(self):
    if self._dist:
      self._dist_vec.append(self._dist)
    self._dist = []

    # Reset the cameras.
    camera_name = 'corner2'
    index = self.model.camera_name2id(camera_name)
    if self._start_at_obj:
      self.model.cam_fovy[index] = 10.0
      self.model.cam_pos[index][0] = 1.5
      self.model.cam_pos[index][1] = -0.1
      self.model.cam_pos[index][2] = 1.1
    else:
      self.model.cam_fovy[index] = 17.0
      self.model.cam_pos[index][1] = -0.1
      self.model.cam_pos[index][2] = 1.1

    # Get the goal image.
    super(SawyerWindowImage, self).reset()
    goal_slide_pos = np.random.uniform(0, 0.2)
    for _ in range(20):
      self.data.set_mocap_pos('mocap', self._get_pos_objects())
      self.data.set_joint_qpos('window_slide', goal_slide_pos)
      self.do_simulation([-1, 1], self.frame_skip)
    self._goal_x = goal_slide_pos
    self._goal_img = self._get_img()

    # Reset the environment again.
    super(SawyerWindowImage, self).reset()
    if self._task == 'open':
      init_slide_pos = 0.0
    elif self._task == 'close':
      init_slide_pos = 0.2
    else:
      assert self._task == 'openclose'
      init_slide_pos = np.random.choice([0.0, 0.2])

    if self._start_at_obj:
      for _ in range(50):
        self.data.set_mocap_pos('mocap', self._get_pos_objects())
        self.data.set_joint_qpos('window_slide', init_slide_pos)
        self.do_simulation([-1, 1], self.frame_skip)
    else:
      self.data.set_joint_qpos('window_slide', init_slide_pos)
      self.do_simulation([-1, 1], self.frame_skip)
    img = self._get_img()

    # Add the initial distance.
    x = self.data.get_joint_qpos('window_slide')
    # L1 distance between current and target drawer location.
    dist = abs(x - self._goal_x)
    self._dist.append(dist)
    return np.concatenate([img, self._goal_img], axis=-1)

  def _get_img(self):
    assert self._camera_name in ['corner', 'topview', 'corner3',
                                 'behindGripper', 'corner2']
    # Hide the goal marker position.
    self._set_pos_site('goal', np.inf * self._target_pos)
    # IMPORTANT: Pull the context to the current thread.
    for ctx in self.sim.render_contexts:
      ctx.opengl_context.make_context_current()
    img = self.render(offscreen=True,
                      resolution=(64, 64),
                      camera_name=self._camera_name)
    if self._camera_name in ['corner', 'topview', 'behindGripper']:
      img = img[::-1]
    return img.flatten()

  @property
  def observation_space(self):
    return gym.spaces.Box(
        low=np.full((64*64*6), 0),
        high=np.full((64*64*6), 255),
        dtype=np.uint8)


class SawyerBinImage(
    metaworld.envs.mujoco.env_dict.ALL_V2_ENVIRONMENTS['bin-picking-v2']):
  """Wrapper for the SawyerBin environment with image observations."""

  def __init__(self, camera='corner2', start_at_obj=True, alias=False):
    self._alias = alias
    self._start_at_obj = start_at_obj
    self._dist = []
    self._dist_vec = []
    self._camera_name = camera
    super(SawyerBinImage, self).__init__()
    self._partially_observable = False
    self._freeze_rand_vec = False
    self._set_task_called = True
    self.reset()
    self._freeze_rand_vec = False  # Set False to randomize the goal position.

  def reset_metrics(self):
    self._dist_vec = []
    self._dist = []

  def _hand_obj_dist(self):
    body_id = self.model.body_name2id('hand')
    hand_pos = self.sim.data.body_xpos[body_id]
    obj_pos = self._get_pos_objects()
    return np.linalg.norm(hand_pos - obj_pos)

  def _obj_goal_dist(self):
    obj_pos = self._get_pos_objects()
    return np.linalg.norm(self._goal[:2] - obj_pos[:2])

  def step(self, action):
    super(SawyerBinImage, self).step(action)
    dist = self._obj_goal_dist()
    self._dist.append(dist)
    r = float(dist < 0.05)  # Success if within 5cm of the goal.
    img = self._get_img()
    done = False
    info = {}
    return np.concatenate([img, self._goal_img], axis=-1), r, done, info

  def reset(self):
    if self._dist:
      self._dist_vec.append(self._dist)
    self._dist = []

    # reset the cameras
    camera_name = 'corner2'
    index = self.model.camera_name2id(camera_name)
    self.model.cam_fovy[index] = 14.0
    self.model.cam_pos[index][0] = 1.3
    self.model.cam_pos[index][1] = -0.05
    self.model.cam_pos[index][2] = 0.9

    camera_name = 'topview'
    index = self.model.camera_name2id(camera_name)
    self.model.cam_pos[index][1] = 0.7
    self.model.cam_pos[index][2] = 0.9

    # Get the goal image.
    super(SawyerBinImage, self).reset()
    body_id = self.model.body_name2id('bin_goal')
    obj_pos = self.sim.data.body_xpos[body_id].copy()
    obj_pos[:2] += np.random.uniform(-0.05, 0.05, 2)
    obj_pos[2] = 0.05
    self._set_obj_xyz(obj_pos)
    hand_offset = np.random.uniform([0.0, 0.0, 0.0],
                                    [0.0, 0.0, 0.05])
    for t in range(40):
      self.data.set_mocap_pos('mocap', obj_pos + hand_offset)
      self.do_simulation((t > 20) * np.array([1.0, -1.0]), self.frame_skip)
    self._goal = self._get_pos_objects().copy()
    self._goal_img = self._get_img()

    # Reset the environment again.
    super(SawyerBinImage, self).reset()
    obj_pos = self._get_pos_objects()
    if self._start_at_obj:
      for t in range(40):
        self.data.set_mocap_pos('mocap', obj_pos + np.array([0.0, 0.0, 0.05]))
        self.do_simulation((t > 40) * np.array([1.0, -1.0]), self.frame_skip)
    img = self._get_img()

    # Add the initial distance.
    self._dist.append(self._obj_goal_dist())
    return np.concatenate([img, self._goal_img], axis=-1)

  def _get_img(self):
    if self._camera_name.startswith('default-'):
      camera_name = self._camera_name.split('default-')[1]
    else:
      camera_name = self._camera_name
    assert camera_name in ['corner', 'topview', 'corner3',
                           'behindGripper', 'corner2']
    # IMPORTANT: Pull the context to the current thread.
    for ctx in self.sim.render_contexts:
      ctx.opengl_context.make_context_current()
    resolution = (64, 64)
    img = self.render(offscreen=True, resolution=resolution,
                      camera_name=camera_name)
    if camera_name in ['corner', 'topview', 'behindGripper']:
      img = img[::-1]
    return img.flatten()

  @property
  def observation_space(self):
    return gym.spaces.Box(
        low=np.full((64*64*6), 0),
        high=np.full((64*64*6), 255),
        dtype=np.uint8)
