#!/usr/bin/env python3

import logging
from vcas_viewer.core.logging_config import configure_logging, finalize_session
import time

# Настройка с trace уровнем для показа полной статистики
configure_logging('minimal', 'trace')

logger = logging.getLogger('Test')
logger.debug('Это debug сообщение')
logger.info('Это info сообщение')
logger.warning('Это warning сообщение')
logger.error('Это error сообщение')
logger.critical('Это critical сообщение')

# Создать разные логеры для демонстрации
other_logger = logging.getLogger('Test.Other')
other_logger.warning('Другое warning сообщение')

time.sleep(0.1)  # Небольшая пауза
finalize_session()
