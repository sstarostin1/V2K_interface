#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Отладочный скрипт для проверки структуры каналов
"""

import sys
import os

# Добавляем текущую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mock_vcas_server import MockVCASServer

def main():
    """Проверка структуры каналов"""
    print("=== Диагностика структуры каналов ===")

    server = MockVCASServer()
    channels = server.get_channel_names()

    print(f"\nВсего каналов: {len(channels)}")
    print("\nПервые 15 каналов:")
    for i, channel in enumerate(channels[:15]):
        print(f"  {i+1:2d}. {channel}")

    print("\nАнализ разделителей:")
    slash_count = sum(1 for ch in channels if '/' in ch)
    dot_count = sum(1 for ch in channels if '.' in ch)

    print(f"Каналов со слешами (/): {slash_count}")
    print(f"Каналов с точками (.): {dot_count}")

    print("\nПримеры каналов с разными разделителями:")
    slash_channels = [ch for ch in channels if '/' in ch][:5]
    dot_channels = [ch for ch in channels if '.' in ch][:5]

    if slash_channels:
        print("Со слешами:")
        for ch in slash_channels:
            print(f"  {ch}")

    if dot_channels:
        print("С точками:")
        for ch in dot_channels:
            print(f"  {ch}")

    print("\n=== Анализ завершен ===")

if __name__ == "__main__":
    main()
