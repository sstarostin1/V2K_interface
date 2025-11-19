# -*- coding: utf-8 -*-
"""
Тестовый VCAS сервер-заглушка для отладки и разработки
Генерирует фиктивные данные каналов с различными директориями и поддиректориями
"""

import socket
import threading
import time
import random
import json
from datetime import datetime, timedelta
import logging
import sys
import os

# Добавляем путь к модулям проекта
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from vcas_viewer.core.logging_config import parse_logging_level, configure_logging

# Пытаемся загрузить реальные данные каналов для более реалистичной генерации
REAL_DATA_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'real_vcas_channels_data.json')
REAL_CHANNEL_DATA = None

try:
    if os.path.exists(REAL_DATA_FILE):
        with open(REAL_DATA_FILE, 'r', encoding='utf-8') as f:
            REAL_CHANNEL_DATA = json.load(f)
        logging.getLogger(__name__).info(f"Загружены реальные данные каналов из {REAL_DATA_FILE}")
except Exception as e:
    logging.getLogger(__name__).warning(f"Не удалось загрузить реальные данные каналов: {e}")


class MockVCASServer:
    """Тестовый сервер VCAS для отладки"""

    def __init__(self, host='127.0.0.1', port=20042):
        self.host = host
        self.port = port
        self.socket = None
        self.clients = []
        self.client_subscriptions = {}  # socket: set of subscribed channels
        self.running = False
        self.logger = logging.getLogger('MockVCASServer')

        # Генерируем тестовые данные каналов
        self.channels_data = self._generate_test_channels()

        # Таймеры для индивидуального обновления каналов
        self.channel_update_threads = {}
        self.channel_update_timers = {}  # channel_name: next_update_time



    def _generate_test_channels(self):
        """Генерация тестовых данных каналов с вложенной структурой на основе реального сервера"""

        # Проверяем, загружены ли реальные данные каналов
        if REAL_CHANNEL_DATA and 'directories' in REAL_CHANNEL_DATA and 'channel_details' in REAL_CHANNEL_DATA:
            # Используем структуру из реальных данных
            directories = REAL_CHANNEL_DATA['directories']
            channels_list = []
            for dir_name, dir_channels in directories.items():
                channels_list.extend(dir_channels)
            channels_list.sort()

            self.logger.info(f"Генерация на основе реальных данных: {len(channels_list)} каналов")
            return {
                'structure': {},  # Для совместимости
                'list': channels_list,
                'details': self._generate_channel_details_from_real_data(channels_list, REAL_CHANNEL_DATA['channel_details'])
            }
        else:
            # Fallback: генерация на основе жестко заданной структуры
            self.logger.info("Ретрансляция на fallback генерацию - реальные данные не загружены")
            return self._generate_fallback_channels()

    def _generate_channel_details_from_real_data(self, channels_list, real_channel_details):
        """Генерация деталей каналов на основе реальных данных"""
        details = {}

        for channel_name in channels_list:
            if channel_name in real_channel_details:
                real_info = real_channel_details[channel_name]
                details[channel_name] = {
                    'type': real_info.get('type', 'rw'),
                    'units': real_info.get('units', ''),
                    'descr': real_info.get('descr', f'Channel {channel_name}'),
                    'val': self._generate_realistic_value(channel_name, real_info.get('units', '')),
                    'host': 'mock-server',
                    'port': str(self.port)
                }
            else:
                # Fallback для каналов, которых нет в реальных данных
                details[channel_name] = {
                    'type': 'rw',
                    'units': '',
                    'descr': f'Channel {channel_name}',
                    'val': self._generate_fallback_value(''),
                    'host': 'mock-server',
                    'port': str(self.port)
                }

        return details

    def _generate_fallback_channels(self):
        """Генерация каналов в fallback режиме (старый код)"""
        # Это копия вашего исходного метода генерации каналов
        channel_structure = {
            "VEPP": {
                "FZ_tau": {"type": "rw", "units": "s", "descr": "Время жизни пучков в ВЭПП по ФЗ"},
                "Energy": {"type": "ro", "units": "MeV", "descr": "Энергия пучка"},
                "Lifetime": {"type": "ro", "units": "s", "descr": "Время жизни пучка"},
                "Lum": {
                    "Lsm": {"type": "ro", "units": "", "descr": "Светимость"},
                    "Lumi": {"type": "ro", "units": "m^-1s^-1", "descr": "Интегральная светимость"},
                    "smBetas": {
                        "smBXe": {"type": "ro", "units": "m", "descr": "Размер пучка Xe в IP"},
                        "smBXp": {"type": "ro", "units": "m", "descr": "Размер пучка Xp в IP"},
                        "smBYe": {"type": "ro", "units": "m", "descr": "Размер пучка Ye в IP"},
                        "smBYp": {"type": "ro", "units": "m", "descr": "Размер пучка Yp в IP"}
                    }
                },
                "Nu": {
                    "Pi": {
                        "x": {"type": "ro", "units": "", "descr": "Тюнинг частоты x"},
                        "y": {"type": "ro", "units": "", "descr": "Тюнинг частоты y"}
                    },
                    "nuX": {"type": "ro", "units": "", "descr": "Частота настройки X"},
                    "nuY": {"type": "ro", "units": "", "descr": "Частота настройки Y"}
                }
            },
            "BEP": {
                "BPM": self._generate_bpm_structure(),
                "CCD": self._generate_ccd_structure(),
                "Currents": {
                    "FZ": {"type": "rw", "units": "mA", "descr": "Ток электронов/позитронов в БЭП по ФЗ"},
                    "PMT": {"type": "rw", "units": "mA", "descr": "Ток электронов/позитронов в БЭП"},
                    "PMT_int": {"type": "rw", "units": "mA*h", "descr": "Интеграл тока в БЭП"},
                    "ePMT": {"type": "rw", "units": "mA", "descr": "Ток электронов в БЭП"},
                    "ePMT_raw": {"type": "rw", "units": "mA", "descr": "Ток электронов в БЭП"},
                    "pPMT": {"type": "rw", "units": "mA", "descr": "Ток позитронов в БЭП"},
                    "pPMT_raw": {"type": "rw", "units": "mA", "descr": "Ток позитронов в БЭП"},
                    "p_tau": {"type": "ro", "units": "s", "descr": "Время жизни позитронов"}
                },
                "Energy": {
                    "E_hall": {"type": "ex", "units": "MeV", "descr": "Энергия БЭП, измеренная по датчику Холла"},
                    "E_nmr": {"type": "ex", "units": "MeV", "descr": "Энергия БЭП, измеренная по ЯМР"},
                    "E_set": {"type": "ex", "units": "MeV", "descr": "Энергия БЭП, посчитанная по току источника"}
                },
                "Field": {
                    "Hall_0": {
                        "Gs": {"type": "rw", "units": "Gs", "descr": "Hall 0"},
                        "mV": {"type": "rw", "units": "mV", "descr": "Hall 0 voltage"}
                    },
                    "Hall_1": {
                        "Gs": {"type": "rw", "units": "Gs", "descr": "Hall 1"},
                        "mV": {"type": "rw", "units": "mV", "descr": "Hall 1 voltage"}
                    },
                    "Hall_2": {
                        "Gs": {"type": "rw", "units": "Gs", "descr": "Hall 2"},
                        "mV": {"type": "rw", "units": "mV", "descr": "Hall 2 voltage"}
                    }
                },
                "Injection": {
                    "State": {"type": "rw", "units": "", "descr": "Состояние инжекции в БЭП. SUSPEND,ON"}
                },
                "PS": {
                    "BIT1": {"type": "rw", "units": "A", "descr": "Заданный в шинах БЭП по БИТ1"},
                    "BIT2": {"type": "rw", "units": "A", "descr": "Заданный в шинах БЭП по БИТ2"},
                    "SetCur": {"type": "rw", "units": "A", "descr": "Заданный ток в шинах БЭП"},
                    "Thermo": {
                        "Left": {"type": "rw", "units": "C", "descr": "Термодатчик левое звено"},
                        "Right": {"type": "rw", "units": "C", "descr": "Термодатчик правое звено"},
                        "Control": {"type": "rw", "units": "C", "descr": "Термодатчик контрольный"}
                    }
                },
                "PhiDissector": {
                    "emeanz": {"type": "rw", "units": "cm", "descr": "Mean_z продольного распределения электронов"},
                    "emu1z": {"type": "rw", "units": "cm", "descr": "Первый момент продольного распределения электронов"},
                    "emu2z": {"type": "rw", "units": "cm", "descr": "Второй момент продольного распределения электронов"},
                    "esigmaz": {"type": "rw", "units": "cm", "descr": "Sigma_z продольного распределения электронов"},
                    "pmeanz": {"type": "rw", "units": "cm", "descr": "Mean_z продольного распределения позитронов"},
                    "pmu1z": {"type": "rw", "units": "cm", "descr": "Первый момент продольного распределения позитронов"},
                    "pmu2z": {"type": "rw", "units": "cm", "descr": "Второй момент продольного распределения позитронов"},
                    "psigmaz": {"type": "rw", "units": "cm", "descr": "Sigma_z продольного распределения позитронов"}
                },
                "RF": {
                    "Fase": {"type": "rw", "units": "", "descr": ""},
                    "Freq": {"type": "rw", "units": "kHz", "descr": ""},
                    "I": {"type": "rw", "units": "A", "descr": ""},
                    "Probros": {"type": "rw", "units": "", "descr": "Состояние проброса"},
                    "Separ": {"type": "rw", "units": "", "descr": ""},
                    "Tune_matching": {"type": "rw", "units": "", "descr": "Состояние сведения частот"},
                    "U": {"type": "rw", "units": "kV", "descr": ""}
                },
                "SR": {
                    "Volotek1": {
                        "Emission": {"type": "rw", "units": "mA", "descr": "Эмиссия"},
                        "Pressure": {"type": "rw", "units": "Torr", "descr": "Давление"},
                        "State": {"type": "rw", "units": "", "descr": "Tango Device State"},
                        "Status": {"type": "rw", "units": "", "descr": "Tango Device Status"}
                    },
                    "Volotek2": {
                        "Emission": {"type": "rw", "units": "mA", "descr": "Эмиссия"},
                        "Pressure": {"type": "rw", "units": "Torr", "descr": "Давление"},
                        "State": {"type": "rw", "units": "", "descr": "Tango Device State"},
                        "Status": {"type": "rw", "units": "", "descr": "Tango Device Status"}
                    }
                },
                "State": {"type": "rw", "units": "Text", "descr": "Состояние БЭП"},
                "Thermo": self._generate_thermo_structure(),
                "UM": self._generate_um_structure(),
                "Vacuum": self._generate_vacuum_structure()
            },
            "CMD": {
                "DCR1": {"type": "rw", "units": "", "descr": "Двойной счетчик совпадений 1"},
                "DCR2": {"type": "rw", "units": "", "descr": "Двойной счетчик совпадений 2"},
                "DCR3": {"type": "rw", "units": "", "descr": "Двойной счетчик совпадений 3"},
                "DLum": {"type": "rw", "units": "", "descr": ""},
                "DLumBGO": {"type": "rw", "units": "", "descr": ""},
                "DLumInt": {"type": "rw", "units": "", "descr": ""},
                "DLumIntBGO": {"type": "rw", "units": "", "descr": ""},
                "Events": {"type": "rw", "units": "", "descr": "Количество событий"},
                "RunNumber": {"type": "rw", "units": "", "descr": "Номер прогона"},
                "RunState": {"type": "rw", "units": "", "descr": "Статус прогона"},
                "RunTransition": {"type": "rw", "units": "", "descr": "Переход состояния прогона"},
                "Trigger": {"type": "rw", "units": "", "descr": "Триггер"}
            },
            "Cryo": {
                "Level": {
                    "Cr-1": {
                        "LHe": {"type": "rw", "units": "", "descr": "Уровень жидкого гелия"},
                        "LN": {"type": "rw", "units": "", "descr": "Уровень жидкого азота"}
                    },
                    "Cr-2": {
                        "LHe": {"type": "rw", "units": "", "descr": "Уровень жидкого гелия"},
                        "LN": {"type": "rw", "units": "", "descr": "Уровень жидкого азота"}
                    }
                },
                "Thermo": {
                    "Cr-1": self._generate_cryo_thermo_section(),
                    "Cr-2": self._generate_cryo_thermo_section()
                }
            },
            "Diagnostics": {
                "BPM": {
                    "Position_X": {"type": "rw", "units": "mm", "descr": "Позиция пучка по X"},
                    "Position_Y": {"type": "rw", "units": "mm", "descr": "Позиция пучка по Y"},
                    "Intensity": {"type": "ro", "units": "counts", "descr": "Интенсивность пучка"}
                },
                "FCT": {
                    "Frequency": {"type": "rw", "units": "MHz", "descr": "Частота быстрого контроля"},
                    "Phase": {"type": "rw", "units": "deg", "descr": "Фаза быстрого контроля"}
                },
                "Profile": {
                    "Sigma_X": {"type": "ro", "units": "mm", "descr": "Размер пучка по X"},
                    "Sigma_Y": {"type": "ro", "units": "mm", "descr": "Размер пучка по Y"}
                }
            },
            "Magnets": {
                "Quadrupoles": {
                    "Q1_PS": {"type": "rw", "units": "A", "descr": "Питание квадруполя Q1"},
                    "Q2_PS": {"type": "rw", "units": "A", "descr": "Питание квадруполя Q2"},
                    "Q3_PS": {"type": "rw", "units": "A", "descr": "Питание квадруполя Q3"}
                },
                "Dipoles": {
                    "D1_Current": {"type": "rw", "units": "A", "descr": "Ток диполя D1"},
                    "D2_Current": {"type": "rw", "units": "A", "descr": "Ток диполя D2"}
                }
            },
            "RF": {
                "Generator": {
                    "Amplitude": {"type": "rw", "units": "MV", "descr": "Амплитуда генератора"},
                    "Phase": {"type": "rw", "units": "deg", "descr": "Фаза генератора"},
                    "Frequency": {"type": "rw", "units": "MHz", "descr": "Частота генератора"}
                },
                "Cavity": {
                    "Voltage": {"type": "ro", "units": "MV", "descr": "Напряжение резонатора"},
                    "Temperature": {"type": "ro", "units": "C", "descr": "Температура резонатора"}
                }
            },
            "Vacuum": {
                "Pressure": {
                    "Section_1": {"type": "ro", "units": "mbar", "descr": "Давление секция 1"},
                    "Section_2": {"type": "ro", "units": "mbar", "descr": "Давление секция 2"},
                    "Section_3": {"type": "ro", "units": "mbar", "descr": "Давление секция 3"}
                },
                "Pumps": {
                    "Turbo_1": {"type": "rw", "units": "rpm", "descr": "Скорость турбонасоса 1"},
                    "Turbo_2": {"type": "rw", "units": "rpm", "descr": "Скорость турбонасоса 2"}
                }
            },
            "Temperature": {
                "Cooling": {
                    "Water_In": {"type": "ro", "units": "C", "descr": "Температура воды на входе"},
                    "Water_Out": {"type": "ro", "units": "C", "descr": "Температура воды на выходе"},
                    "Flow": {"type": "ro", "units": "l/min", "descr": "Расход охлаждающей воды"}
                },
                "Magnets": {
                    "Quad_1": {"type": "ro", "units": "C", "descr": "Температура квадруполя 1"},
                    "Dipole_1": {"type": "ro", "units": "C", "descr": "Температура диполя 1"}
                }
            },
            "TEST": {
                "SimpleChannel": {"type": "rw", "units": "V", "descr": "Простой тестовый канал"},
                "ReadOnlyChannel": {"type": "ro", "units": "Hz", "descr": "Канал только для чтения"},
                "ExclusiveChannel": {"type": "ex", "units": "", "descr": "Эксклюзивный канал"}
            },
            "DEBUG": {
                "Counter": {"type": "rw", "units": "count", "descr": "Счетчик для отладки"},
                "Timer": {"type": "ro", "units": "ms", "descr": "Таймер системы"},
                "Status": {"type": "ro", "units": "enum", "descr": "Статус системы"}
            }
        }

        # Преобразуем структуру в плоский список каналов
        channels_list = []

        def extract_channels(prefix, structure):
            for name, value in structure.items():
                full_name = f"{prefix}/{name}" if prefix else name

                if isinstance(value, dict):
                    if "type" in value:
                        # Это конечный канал
                        channels_list.append(full_name)
                    else:
                        # Это директория, продолжаем рекурсию
                        extract_channels(full_name, value)
                else:
                    # Это конечный канал
                    channels_list.append(full_name)

        extract_channels("", channel_structure)

        # Сортируем список каналов
        channels_list.sort()

        self.logger.info(f"Сгенерировано {len(channels_list)} тестовых каналов")
        self.logger.info(f"Структура каналов: {channels_list[:10]}...")  # Показываем первые 10

        return {
            'structure': channel_structure,
            'list': channels_list,
            'details': self._generate_channel_details(channels_list, channel_structure)
        }

    def _generate_channel_details(self, channels_list, channel_structure):
        """Генерация детальной информации о каналах"""
        details = {}

        for channel in channels_list:
            # Разбираем путь канала
            parts = channel.split('/')
            current = channel_structure

            # Находим канал в структуре
            for part in parts:
                if part in current:
                    current = current[part]
                else:
                    current = {}
                    break

            if isinstance(current, dict) and "type" in current:
                # Генерируем значения в зависимости от типа канала
                channel_type = current["type"]
                units = current.get("units", "")
                descr = current.get("descr", f"Канал {channel}")

                # Генерируем начальное значение на основе реальных данных или по единицам измерения
                value = self._generate_realistic_value(channel, units)

                details[channel] = {
                    'type': channel_type,
                    'units': units,
                    'descr': descr,
                    'val': value,
                    'host': 'mock-server',
                    'port': str(self.port)
                }

        return details

    def _generate_bpm_structure(self):
        """Генерация структуры BPM (Beam Position Monitors)"""
        bpm_structure = {}
        for i in range(1, 13):  # BPM 1-12
            bpm_structure[f"{i:02d}"] = {
                "int": {"type": "rw", "units": "mA", "descr": "Датчик положения пучка интенсивность"},
                "x": {"type": "rw", "units": "mm", "descr": "Датчик положения пучка x"},
                "z": {"type": "rw", "units": "mm", "descr": "Датчик положения пучка z"}
            }
        return bpm_structure

    def _generate_ccd_structure(self):
        """Генерация структуры CCD камер"""
        ccd_structure = {}
        for cam in ["B3", "B5", "B6", "B7", "B8", "B9", "B10", "B11"]:
            ccd_structure[cam] = {
                "ampl": {"type": "ex", "descr": "Амплитуда"},
                "maxL": {"type": "rw", "units": "ADC count", "descr": ""},
                "phi": {"type": "rw", "descr": "угол наклона пучка на датчике"},
                "sigma_x": {"type": "rw", "units": "mm", "descr": "размер пучка по горизонтали на датчике"},
                "sigma_z": {"type": "rw", "units": "mm", "descr": "размер пучка по вертикали на датчике"},
                "x": {"type": "rw", "units": "mm", "descr": "х-координата на датчике"},
                "x0": {"type": "rw", "units": "mm", "descr": "ноль по горизонтали на датчике"},
                "xx": {"type": "ex", "units": "mm", "descr": "Второй момент по x"},
                "xz": {"type": "ex", "units": "mm", "descr": "Перекрестный момент"},
                "z": {"type": "rw", "units": "mm", "descr": "z-координата на датчике"},
                "z0": {"type": "rw", "units": "mm", "descr": "ноль по вертикали на датчике"},
                "zz": {"type": "ex", "units": "mm", "descr": "Второй момент по z"}
            }
        return ccd_structure

    def _generate_thermo_structure(self):
        """Генерация структуры термодатчиков"""
        thermo_structure = {}
        for i in range(1, 13):  # B1-B12
            thermo_structure[f"B{i}.1"] = {"type": "rw", "units": "C", "descr": "Температура"}
            thermo_structure[f"B{i}.2"] = {"type": "rw", "units": "C", "descr": "Температура"}
        return thermo_structure

    def _generate_um_structure(self):
        """Генерация структуры µ-магнитов"""
        um_structure = {
            "QX": self._generate_um_section("QX", 12),
            "QZ": self._generate_um_section("QZ", 12),
            "SQ": self._generate_um_section("SQ", 12),
            "SX": self._generate_um_section("SX", 12),
            "SZ": self._generate_um_section("SZ", 12),
            "X": self._generate_um_x_section(),
            "Z": self._generate_um_z_section()
        }
        return um_structure

    def _generate_um_section(self, prefix, count):
        """Генерация секции µ-магнитов"""
        section = {}
        for i in range(1, count + 1):
            section[f"{prefix}{i}"] = {
                "Cur": {"type": "rw", "units": "A", "descr": "Ток"},
                "SetCur": {"type": "rw", "units": "A", "descr": "Установленный ток"},
                "Vol": {"type": "rw", "units": "V", "descr": "Напряжение"}
            }
        return section

    def _generate_um_x_section(self):
        """Генерация секции X µ-магнитов"""
        x_section = {}
        for mag in ["1F1X", "1F2X", "1F3X", "1X1", "1X2", "2F1X", "2F2X", "2F3X", "2X1", "2X2", "3F1X", "3F2X", "3F3X", "3X1", "3X2", "4F1X", "4F2X", "4F3X", "4X1", "4X2",
                   "KM2", "KM3", "KME1", "KME2", "KME3", "KMP1", "KMP2", "KMP3", "KX1"]:
            x_section[mag] = {
                "Cur": {"type": "rw", "units": "A", "descr": "Ток"},
                "SetCur": {"type": "rw", "units": "A", "descr": "Установленный ток"},
                "Vol": {"type": "rw", "units": "V", "descr": "Напряжение"}
            }
        return x_section

    def _generate_um_z_section(self):
        """Генерация секции Z µ-магнитов"""
        z_section = {}
        for mag in ["1D1Z", "1D2Z", "1D3Z", "1F1Z", "2D1Z", "2D2Z", "2D3Z", "2F1Z", "3D1Z", "3D2Z", "3D3Z", "3F1Z", "4D1Z", "4D2Z", "4D3Z", "4F1Z",
                   "KZ1", "KZ4", "KZE3", "KZE4", "KZP4", "Z1", "Z10", "Z11", "Z12", "Z2", "Z3", "Z4", "Z5", "Z6", "Z7", "Z8", "Z9"]:
            z_section[mag] = {
                "Cur": {"type": "rw", "units": "A", "descr": "Ток"},
                "SetCur": {"type": "rw", "units": "A", "descr": "Установленный ток"},
                "Vol": {"type": "rw", "units": "V", "descr": "Напряжение"}
            }
        return z_section

    def _generate_vacuum_structure(self):
        """Генерация структуры вакуумных систем"""
        vacuum_structure = {}
        # MRN секции
        for section in ["1M1-H1", "1M1-H2", "1M2-H1", "1M2-H2", "2M1-H1", "2M1-H2", "2M2-H1", "2M2-H2", "3M1-H1", "3M1-H2", "3M2-H1", "3M2-H2", "4M1-H1", "4M1-H2", "4M2-H1", "4M2-H2", "Center"]:
            vacuum_structure[f"MRN/{section}"] = {
                "c": {"type": "rw", "units": "", "descr": "Ток коллектора"},
                "u": {"type": "rw", "units": "", "descr": "Напряжение"}
            }

        # PMM секции
        for section in ["1M1-L", "2M1-L", "2M2-L", "3M1-L", "3M2-L", "4M1-L", "4M2-L", "L-SND", "Res-L", "Vpusk-L"]:
            vacuum_structure[f"PMM/{section}"] = {"type": "rw", "units": "", "descr": "Давление"}

        return vacuum_structure

    def _generate_cryo_thermo_section(self):
        """Генерация секции термодатчиков криогена"""
        cryo_thermo = {}
        for i in range(6):
            cryo_thermo[f"T{i}"] = {"type": "rw", "units": "K", "descr": f"Температура криогена {i}"}
        return cryo_thermo

    def start(self):
        """Запуск сервера"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)

            self.running = True
            self.logger.info(f"Mock VCAS сервер запущен на {self.host}:{self.port}")

            # Запускаем поток для принятия подключений
            accept_thread = threading.Thread(target=self._accept_connections)
            accept_thread.daemon = True
            accept_thread.start()

            # Запускаем индивидуальные потоки для обновления каждого канала
            for channel in self.channels_data['list']:
                update_thread = threading.Thread(target=self._update_channel_loop, args=(channel,))
                update_thread.daemon = True
                self.channel_update_threads[channel] = update_thread
                update_thread.start()

            return True

        except Exception as e:
            self.logger.error(f"Ошибка запуска сервера: {str(e)}")
            return False

    def stop(self):
        """Остановка сервера"""
        self.running = False

        if self.socket:
            self.socket.close()

        # Закрываем соединения с клиентами
        for client in self.clients:
            try:
                client.close()
            except:
                pass

        self.clients.clear()
        self.logger.info("Mock VCAS сервер остановлен")

    def _accept_connections(self):
        """Принятие подключений от клиентов"""
        while self.running:
            try:
                client_socket, address = self.socket.accept()
                self.logger.info(f"Подключен клиент: {address}")
                self.clients.append(client_socket)

                # Запускаем обработчик для клиента
                client_thread = threading.Thread(target=self._handle_client, args=(client_socket,))
                client_thread.daemon = True
                client_thread.start()

            except OSError:
                # Сервер остановлен
                break
            except Exception as e:
                self.logger.error(f"Ошибка принятия подключения: {str(e)}")

    def _handle_client(self, client_socket):
        """Обработка подключенного клиента"""
        buffer = b""

        try:
            while self.running:
                try:
                    data = client_socket.recv(1024)
                    if not data:
                        break

                    buffer += data

                    # Обрабатываем полученные команды
                    while b'\n' in buffer:
                        # Извлекаем команду
                        command, buffer = buffer.split(b'\n', 1)
                        command = command.decode('utf-8').strip()

                        if command:
                            self.logger.debug(f"Получена команда: {command}")
                            response = self._process_command(command, client_socket)

                            if response:
                                client_socket.send(response.encode('utf-8'))
                                self.logger.debug(f"Отправлен ответ: {response.strip()}")

                except UnicodeDecodeError:
                    self.logger.warning("Ошибка декодирования команды")
                    buffer = b""
                except Exception as e:
                    self.logger.error(f"Ошибка обработки данных клиента: {str(e)}")
                    break

        except Exception as e:
            self.logger.error(f"Ошибка соединения с клиентом: {str(e)}")
        finally:
            # Удаляем клиента из списка
            if client_socket in self.clients:
                self.clients.remove(client_socket)
            try:
                client_socket.close()
            except:
                pass

    def _process_command(self, command, client_socket):
        """Обработка команды VCAS протокола"""
        try:
            # Парсим команду формата key1:value1|key2:value2
            if ':' not in command:
                return self._error_response("Invalid command format")

            parts = command.split('|')
            cmd_dict = {}

            for part in parts:
                if ':' in part:
                    key, value = part.split(':', 1)
                    cmd_dict[key.strip()] = value.strip()

            method = cmd_dict.get('method', '')
            channel_name = cmd_dict.get('name', '')

            if method == 'get' and channel_name == 'ChannelsList':
                # Запрос списка каналов
                return self._get_channels_list()

            elif method == 'getfull' and channel_name:
                # Запрос полной информации о канале
                return self._get_channel_info(channel_name)

            elif method == 'get' and channel_name:
                # Запрос значения канала
                return self._get_channel_value(channel_name)

            elif method == 'set' and channel_name:
                # Установка значения канала
                value = cmd_dict.get('val', '')
                return self._set_channel_value(channel_name, value)

            elif method == 'gethistory' and channel_name:
                # Запрос исторических данных канала
                duration = cmd_dict.get('duration', '300')  # По умолчанию 5 минут
                return self._get_channel_history(channel_name, duration)

            elif method == 'subscribe' and channel_name:
                # Подписка на канал для конкретного клиента
                if client_socket not in self.client_subscriptions:
                    self.client_subscriptions[client_socket] = set()
                if channel_name not in self.client_subscriptions[client_socket]:
                    self.client_subscriptions[client_socket].add(channel_name)
                    self.logger.info(f"Клиент подписан на канал {channel_name}")

                    # Отправляем текущее значение канала сразу после подписки
                    if channel_name in self.channels_data['details']:
                        info = self.channels_data['details'][channel_name]
                        current_time = datetime.now().strftime('%d.%m.%Y %H_%M_%S.%f')
                        update_message = f"name:{channel_name}|time:{current_time}|val:{info['val']}\n"
                        try:
                            client_socket.send(update_message.encode('utf-8'))
                            self.logger.debug(f"Отправлено начальное значение для {channel_name} при подписке")
                        except Exception as e:
                            self.logger.error(f"Ошибка отправки начального значения для {channel_name}: {str(e)}")

                return ""  # Пустой ответ означает успех

            else:
                return self._error_response(f"Unknown method: {method}")

        except Exception as e:
            self.logger.error(f"Ошибка обработки команды '{command}': {str(e)}")
            return self._error_response(f"Command processing error: {str(e)}")

    def _get_channels_list(self):
        """Получить список каналов"""
        channels_str = ','.join(self.channels_data['list'])
        return f"name:ChannelsList|val:{channels_str}\n"

    def _get_channel_info(self, channel_name):
        """Получить полную информацию о канале"""
        if channel_name in self.channels_data['details']:
            info = self.channels_data['details'][channel_name]
            response_parts = [f"name:{channel_name}"]

            for key, value in info.items():
                response_parts.append(f"{key}:{value}")

            return '|'.join(response_parts) + '\n'
        else:
            return self._error_response(f"Channel '{channel_name}' not found")

    def _get_channel_value(self, channel_name):
        """Получить значение канала"""
        if channel_name in self.channels_data['details']:
            info = self.channels_data['details'][channel_name]
            current_time = datetime.now().strftime('%d.%m.%Y %H_%M_%S.%f')
            return f"name:{channel_name}|time:{current_time}|val:{info['val']}\n"
        else:
            return self._error_response(f"Channel '{channel_name}' not found")

    def _set_channel_value(self, channel_name, value):
        """Установить значение канала"""
        if channel_name in self.channels_data['details']:
            # Обновляем значение в зависимости от типа канала
            info = self.channels_data['details'][channel_name]

            # Генерируем новое значение или используем установленное
            if value.strip():
                info['val'] = value
            else:
                # Генерируем случайное значение
                self._update_single_channel_value(channel_name)

            return ""  # Пустой ответ означает успех
        else:
            return self._error_response(f"Channel '{channel_name}' not found")

    def _get_channel_history(self, channel_name, duration):
        """Получить исторические данные канала"""
        if channel_name in self.channels_data['details']:
            info = self.channels_data['details'][channel_name]
            duration_seconds = int(duration)

            # Генерируем исторические данные
            # Создаем списки timestamps и values
            timestamps = []
            values = []
            base_time = datetime.now()

            # Генерируем точки с интервалом 1 секунда
            for i in range(duration_seconds):
                # Время точки (от прошлого к настоящему)
                point_time = base_time - timedelta(seconds=duration_seconds - i - 1)
                time_str = point_time.strftime('%d.%m.%Y %H_%M_%S.%f')

                # Генерируем значение с небольшим шумом вокруг текущего значения
                try:
                    base_val = float(info['val'])
                    # Добавляем небольшой шум (±5% от базового значения)
                    noise = base_val * 0.05 * (random.random() - 0.5) * 2
                    val = base_val + noise
                    val_str = f"{val:.3f}"
                except (ValueError, TypeError):
                    # Если значение не числовое, используем текущее
                    val_str = info['val']

                timestamps.append(time_str)
                values.append(val_str)

            # Формируем ответ в формате VCAS протокола
            response_parts = [f"name:{channel_name}", f"method:gethistory", f"duration:{duration}",
                            f"timestamps:{','.join(timestamps)}", f"values:{','.join(values)}"]

            return '|'.join(response_parts) + '\n'
        else:
            return self._error_response(f"Channel '{channel_name}' not found")

    def _update_channel_loop(self, channel_name):
        """Цикл обновления для одного канала с индивидуальными интервалами"""
        while self.running:
            try:
                # Обновляем значение канала
                self._update_single_channel_value(channel_name)

                # Отправляем обновления подписанным клиентам
                self._notify_subscribed_clients([channel_name])

                # Индивидуальный хаотичный интервал обновления для каждого канала (0.5-3 секунды)
                update_interval = random.uniform(0.5, 3.0)
                time.sleep(update_interval)

            except Exception as e:
                self.logger.error(f"Ошибка обновления канала {channel_name}: {str(e)}")
                time.sleep(1)

    def _generate_realistic_value(self, channel_name, units):
        """Генерировать значение канала с учетом реальных данных"""
        # Пытаемся найти информацию о реальном канале
        real_value = None
        value_range = None

        if REAL_CHANNEL_DATA and 'channel_details' in REAL_CHANNEL_DATA:
            real_channels = REAL_CHANNEL_DATA['channel_details']
            if channel_name in real_channels:
                real_info = real_channels[channel_name]
                real_value = real_info.get('val', 'none')

                # Пытаемся разобрать значение как число для определения диапазона
                try:
                    if 'val' in real_info and real_info['val'] not in ['none', '', None]:
                        # Для текущего канала используем небольшое отклонение от реального значения
                        if '.' in str(real_info['val']):
                            base_val = float(real_info['val'])
                            # Добавляем шум ±10% от значения
                            noise = base_val * 0.1 * (random.random() - 0.5) * 2
                            value = base_val + noise
                            return self._format_value_by_units(value, units)
                        else:
                            # Текстовое значение, возвращаем как есть или генерируем подобное
                            return real_info['val']
                except (ValueError, TypeError):
                    # Нечисловые значения оставляем
                    return real_info['val'] if real_info['val'] != 'none' else self._generate_fallback_value(units)

        # Fallback к генерации на основе единиц измерения
        return self._generate_fallback_value(units)

    def _generate_fallback_value(self, units):
        """Генерация значения по единицам измерения (fallback метод)"""
        if "bool" in units.lower():
            return "ON" if random.random() > 0.5 else "OFF"
        elif "count" in units.lower() or "hz" in units.lower():
            return str(random.randint(0, 1000))
        elif "deg" in units.lower():
            return "{:.3f}".format(random.uniform(-180, 180))
        elif "mm" in units.lower():
            return "{:.2f}".format(random.uniform(-50, 50))
        elif "mev" in units.lower():
            return "{:.1f}".format(random.uniform(400, 450))
        elif "v" in units.lower() or "a" in units.lower():
            return "{:.2f}".format(random.uniform(-15, 15))
        elif "mv" in units.lower():
            return "{:.3f}".format(random.uniform(0, 10))
        elif "mhz" in units.lower():
            return "{:.2f}".format(random.uniform(400, 600))
        elif "mbar" in units.lower():
            return "{:.2e}".format(random.uniform(1e-10, 1e-6))
        elif "rpm" in units.lower():
            return str(random.randint(30000, 60000))
        elif "c" in units.lower():
            return "{:.1f}".format(random.uniform(20, 40))
        elif "l/min" in units.lower():
            return "{:.1f}".format(random.uniform(0, 50))
        elif "ms" in units.lower():
            return str(random.randint(0, 10000))
        elif "%" in units:
            return "{:.1f}".format(random.uniform(0, 100))
        elif "enum" in units.lower():
            return random.choice(["IDLE", "RUNNING", "ERROR", "MAINTENANCE"])
        elif "text" in units.lower():
            return random.choice(["3", "UNKNOWN", "SUSPEND", "ON"])
        else:
            return "{:.2f}".format(random.uniform(-10, 10))

    def _format_value_by_units(self, value, units):
        """Форматировать численное значение в зависимости от единиц измерения"""
        try:
            if "deg" in units.lower():
                return "{:.3f}".format(value)
            elif "mm" in units.lower():
                return "{:.2f}".format(value)
            elif "mev" in units.lower():
                return "{:.1f}".format(value)
            elif "v" in units.lower() or "a" in units.lower():
                return "{:.3f}".format(value)
            elif "mv" in units.lower():
                return "{:.3f}".format(value)
            elif "mhz" in units.lower():
                return "{:.2f}".format(value)
            elif "mbar" in units.lower():
                return "{:.2e}".format(value)
            elif "rpm" in units.lower():
                return str(int(value))
            elif "c" in units.lower():
                return "{:.1f}".format(value)
            elif "l/min" in units.lower():
                return "{:.1f}".format(value)
            elif "ms" in units.lower():
                return str(int(value))
            elif "%" in units:
                return "{:.1f}".format(value)
            else:
                return "{:.2f}".format(value)
        except (ValueError, TypeError):
            return str(value)

    def _update_single_channel_value(self, channel_name):
        """Обновить значение одного канала"""
        if channel_name in self.channels_data['details']:
            info = self.channels_data['details'][channel_name]
            units = info.get('units', '')

            # Генерируем новое значение с учетом реальных данных
            info['val'] = self._generate_realistic_value(channel_name, units)



    def _notify_subscribed_clients(self, updated_channels):
        """Отправить обновления подписанным клиентам"""
        for client_socket, subscribed_channels in self.client_subscriptions.items():
            # Находим пересечение обновленных каналов с подписками клиента
            relevant_updates = subscribed_channels.intersection(updated_channels)

            if relevant_updates:
                for channel_name in relevant_updates:
                    try:
                        # Получаем текущее значение канала
                        info = self.channels_data['details'][channel_name]
                        current_time = datetime.now().strftime('%d.%m.%Y %H_%M_%S.%f')
                        update_message = f"name:{channel_name}|time:{current_time}|val:{info['val']}\n"

                        # Отправляем обновление клиенту
                        client_socket.send(update_message.encode('utf-8'))
                        self.logger.debug(f"Отправлено обновление для {channel_name} клиенту")

                    except Exception as e:
                        self.logger.error(f"Ошибка отправки обновления клиенту: {str(e)}")
                        # Удаляем проблемного клиента
                        if client_socket in self.client_subscriptions:
                            del self.client_subscriptions[client_socket]
                        if client_socket in self.clients:
                            self.clients.remove(client_socket)
                        try:
                            client_socket.close()
                        except:
                            pass

    def _error_response(self, message):
        """Сформировать ответ об ошибке"""
        return f"value:error|descr:{message}\n"

    def get_channels_count(self):
        """Получить количество каналов"""
        return len(self.channels_data['list'])

    def get_channel_names(self):
        """Получить список имен каналов"""
        return self.channels_data['list'].copy()


def main():
    """Главная функция для запуска сервера"""
    import argparse

    parser = argparse.ArgumentParser(description='Mock VCAS Server для отладки')
    parser.add_argument('--host', default='127.0.0.1', help='Адрес сервера')
    parser.add_argument('--port', type=int, default=20042, help='Порт сервера')
    parser.add_argument('--debug', action='store_true', help='Включить отладочное логирование (синоним --logging full)')
    parser.add_argument('--logging', default='concise', choices=['minimal', 'concise', 'full'],
                       help='Уровень логирования (minimal=WARNING+, concise=INFO+, full=DEBUG+)')

    args = parser.parse_args()

    # Определяем уровень логирования: --debug имеет приоритет
    if args.debug:
        logging_level = 'full'
    else:
        logging_level = args.logging

    configure_logging(logging_level)

    server = MockVCASServer(args.host, args.port)

    if server.start():
        print(f"Mock VCAS сервер запущен на {args.host}:{args.port}")
        print(f"Количество каналов: {server.get_channels_count()}")
        print("Нажмите Ctrl+C для остановки сервера")
        print("\nПримеры каналов:")
        for channel in server.get_channel_names()[:10]:
            print(f"  {channel}")
        if len(server.get_channel_names()) > 10:
            print(f"  ... и еще {len(server.get_channel_names()) - 10} каналов")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nОстановка сервера...")
            server.stop()
    else:
        print("Ошибка запуска сервера")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
