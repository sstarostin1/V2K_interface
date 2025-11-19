# -*- coding: utf-8 -*-
from PyQt5.QtCore import QObject, pyqtSignal
from datetime import datetime


class Channel(QObject):

    updated = pyqtSignal()
    
    _name = None
    _update_time = [None,None]
    
    _value = None
    _updated = None 
    
    _is_valid = False
    _is_writable = True
    
    
    def __init__(self, name, parent=None):
        super(Channel, self).__init__(parent=None)
        self._name = name
        
    
    @property
    def value(self):
        return self._value
    
    @property
    def update_time(self):
        return self._update_time
    

    @property
    def is_valid(self):
        return self._is_valid
    

    @property
    def is_writable(self):
        return self._is_writable



    @property
    def name(self):
        return self._name
    
    def set(self, value):
        raise NotImplementedError    

    def get(self, force = False):
        raise NotImplementedError    

class VirtualChannel(Channel):

    def __init__(self, name, initial_value):
        super(VirtualChannel, self).__init__(name)
        self._value = initial_value
        self._update_time[0] = datetime.now()

    def set(self, value):
        self._update_time[0] = datetime.now()
        self._value = value
        self.updated.emit()

    def get(self,value):
        pass

