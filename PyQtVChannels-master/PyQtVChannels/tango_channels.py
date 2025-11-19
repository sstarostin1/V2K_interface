# -*- coding: utf-8 -*-
from PyQt5.QtNetwork import QTcpSocket
from PyQt5.QtCore import QByteArray, QObject, Qt, QTimer, pyqtSignal
import sys

import time

from datetime import datetime


from .channels import Channel

from tango import AttributeProxy, EventType, EventData

class AttrProxy(QObject):

        eventRecieved = pyqtSignal(EventData)

        def __init__(self, attr_name):
            super().__init__()
            self._attr = AttributeProxy(attr_name)

        def read(self, *args, **kwargs):
            return self._attr.read(*args, **kwargs)


        def write(self, value):
            return self._attr.write(value)


        def subscribe_event(self, e_type, *args, **kwargs):
            self._attr.subscribe_event( e_type, self.__on_event)

        def __on_event(self, ev):     
            self.eventRecieved.emit(ev)

class TangoChannel(Channel):

    
            
                
    def __init__(self, attr_name, ):
        super(TangoChannel, self).__init__(attr_name)
        self._attr = AttrProxy(attr_name)
        self._attr.subscribe_event( EventType.PERIODIC_EVENT,self.__on_event)
        self._attr.subscribe_event( EventType.CHANGE_EVENT,self.__on_event)
        self._attr.eventRecieved.connect(self.__on_event, Qt.QueuedConnection)
        self._value = self._attr.read().value
        self._update_time[0] = datetime.now()
    
    def __on_event(self, ev):     
        
        if ev.attr_value:
            #print (ev.attr_value.name,ev.attr_value.value)
            self._value = ev.attr_value.value
            self.updated.emit()
        else:
            print( ev)

    def set(self, value):
        
        self._update_time[0] = datetime.now()
        self._value = value
        self._attr.write(value)
        # self.updated.emit()

    def get(self,force=False):
        self._value = self._attr.read().value
        self.updated.emit()        


if __name__ == '__main__':
    import sys
    
    from PyQt5 import QtCore
    app = QtCore.QCoreApplication(sys.argv)
    kickers_enable = [TangoChannel('camac6/gzi11/pos_13/enable0'),TangoChannel('camac6/gzi11/pos_13/enable1')]

    
    # chan.updated.connect(slot)
    for kiker in kickers_enable:
        def slot():
            chan = kiker
            print(chan.name,chan.value, chan.update_time )
        kiker.updated.connect(slot)
    
    sys.exit(app.exec_())
