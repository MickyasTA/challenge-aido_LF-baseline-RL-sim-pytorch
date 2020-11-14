#!/usr/bin/env python3

import io

import numpy as np
from PIL import Image

from aido_schemas import (Context, DB20Commands, DB20Observations, EpisodeStart, JPGImage,
                          LEDSCommands, protocol_agent_DB20, PWMCommands, RGB, wrap_direct)
from model import DDPG
from wrappers import *

class PytorchRLBaseline:
    def __init__(self, load_model=False, model_path=None):
        self.image_processor = DTPytorchWrapper()
        self.action_processor = ActionWrapper(FakeWrap())

        self.model = DDPG(state_dim=self.image_processor.shape, action_dim=2, max_action=1, net_type="cnn")
        self.current_image = np.zeros((640, 480, 3))

        self.model.load("model", directory="./models")

    def init(self, context: Context):
        context.info('init()')

    def on_received_seed(self, data: int):
        np.random.seed(data)

    def on_received_episode_start(self, context: Context, data: EpisodeStart):
        context.info(f'Starting episode "{data.episode_name}".')

    def on_received_observations(self, data: DB20Observations):
        camera: JPGImage = data.camera
        obs = jpg2rgb(camera.jpg_data)
        self.current_image = self.image_processor.preprocess(obs)

    def compute_action(self, observation):
        action = self.model.predict(observation)

        return self.action_processor.action(action.astype(float))

    def on_received_get_commands(self, context: Context):
        pwm_left, pwm_right = self.compute_action(self.current_image)
        pwm_left = float(np.clip(pwm_left, -1, +1))
        pwm_right = float(np.clip(pwm_right, -1, +1))
        grey = RGB(0.0, 0.0, 0.0)
        led_commands = LEDSCommands(grey, grey, grey, grey, grey)
        pwm_commands = PWMCommands(motor_left=pwm_left, motor_right=pwm_right)
        commands = DB20Commands(pwm_commands, led_commands)
        context.write('commands', commands)

    def finish(self, context: Context):
        context.info('finish()')


def jpg2rgb(image_data: bytes) -> np.ndarray:
    """ Reads JPG bytes as RGB"""
    im = Image.open(io.BytesIO(image_data))
    im = im.convert('RGB')
    data = np.array(im)
    assert data.ndim == 3
    assert data.dtype == np.uint8
    return data


def main():
    node = PytorchRLBaseline()
    protocol = protocol_agent_DB20
    wrap_direct(node=node, protocol=protocol)


if __name__ == '__main__':
    main()
