import os
import yaml
from typing import Dict, Any

from src.utils.constants import DEFAULT_CONFIG

CONFIG_PATH = "config.yaml"


def load_config() -> Dict[str, Any]:
    
    config = DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f)

        for key, value in user_config.items():
            if key == "last_active_trade":
                if isinstance(value, str) or value is None:
                    config[key] = value #type: ignore
                else:
                    print(f"⚠️ Некорректное значение для '{key}': {value}. Ожидалась строка (например '1d'). Оставлено: {config[key]}")
            # Проверка для остальных (числовых) параметров
            elif isinstance(value, (int, float)) and value >= 0:
                config[key] = value # type: ignore
            else:
                print(f"⚠️ Некорректное значение для '{key}': {value} (Ожидалось число >= 0). Оставлено: {config[key]}")
        
        return config

    except yaml.YAMLError as e:
        print(f"❌ Ошибка синтаксиса YAML в {CONFIG_PATH}: {e}")
        return DEFAULT_CONFIG
    except Exception as e:
        print(f"❌ Неизвестная ошибка при загрузке конфига: {e}")
        return DEFAULT_CONFIG
