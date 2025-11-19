#!/usr/bin/env python3
import sys
sys.path.append('.')
from mock_vcas_server import MockVCASServer

server = MockVCASServer()
channels = server.get_channel_names()

print("Проверка структуры каналов:")
print(f"Всего каналов: {len(channels)}")
print("Первые 5 каналов:")
for i, ch in enumerate(channels[:5]):
    print(f"  {i+1}. {ch}")

print("Проверка символов в первом канале:")
if channels:
    first_channel = channels[0]
    print(f"Канал: {first_channel}")
    print(f"Содержит слеш (/): {'/' in first_channel}")
    print(f"Содержит точку (.): {'.' in first_channel}")
    print(f"Символы: {[c for c in first_channel]}")
