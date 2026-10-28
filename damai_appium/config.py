# -*- coding: UTF-8 -*-
"""
__Author__ = "WECENG"
__Version__ = "1.0.0"
__Description__ = "配置类"
__Created__ = 2023/10/27 09:54
"""
import json


class Config:
    def __init__(self, server_url, device_name, users, city, price_index, if_commit_order):
        self.server_url = server_url
        self.device_name = device_name
        self.users = users
        self.city = city
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
                      config['city'],
                      config['price_index'],
                      config['if_commit_order'])
