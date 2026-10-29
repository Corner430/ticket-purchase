# -*- coding: UTF-8 -*-
"""
__Author__ = "WECENG"
__Version__ = "2.0.0"
__Description__ = "配置类"
__Created__ = 2023/10/27 09:54
"""
import json


class Config:
    def __init__(self, server_url, device_name, users,
                 perform_index, price_index, if_commit_order):
        self.server_url = server_url
        self.device_name = device_name
        self.users = users
        self.perform_index = perform_index
        self.price_index = price_index
        self.if_commit_order = if_commit_order

    @staticmethod
    def load_config():
        with open('config.jsonc', 'r', encoding='utf-8') as config_file:
            # 支持 .jsonc 的整行注释（以 // 开头的行），再交给 json 解析
            cleaned = ''.join(
                line for line in config_file if not line.lstrip().startswith('//')
            )
        config = json.loads(cleaned)
        return Config(config['server_url'],
                      config['device_name'],
                      config['users'],
                      config['perform_index'],
                      config['price_index'],
                      # 默认 True（真实提交下单）；config.jsonc 显式写了则以其为准覆盖
                      config.get('if_commit_order', True))
