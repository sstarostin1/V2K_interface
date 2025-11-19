
from PyQt5.QtNetwork import QTcpSocket
from PyQt5.QtCore import QByteArray, QObject,  QTimer, pyqtSignal
import sys

import time

from datetime import datetime


from .channels import Channel
  
vcas_mappers = (lambda m: float(m['value']), lambda v: {'val':str(v)} )

pulse_reg_mappers = (lambda m: m['value']=='ON', lambda v: {'value':'ON' if v else 'OFF'} )
pks_mapper = (lambda m: m['value'] ,None)


class AbstractTextServerQt(QObject):



    class Channel(Channel):

       
        
        def __init__(self, server, name, mappers):
            super(ChannelServerQt.Channel, self).__init__(name, parent=server)
            self.in_mapper, self.out_mapper = mappers
            self._server = server

        def _handler(self, message):
            # print(message)
            self._value = self.in_mapper(message)
            self._update_time[0] = datetime.now()
            if "time" in message:
                self._update_time[1] = datetime.strptime(message["time"],'%d.%m.%Y %H_%M_%S.%f')
            else:
                self._update_time[1] = None
            

            self.updated.emit()
        
        def _send(self,method, value):
            message = self.out_mapper(value)
            message.update({'name':self._name, "method": method})

            
            self._server.send_message(message)

        def get(self, force = False):
            self._send("get")


        def set(self, value):
            self._send("set", value)  


   


    def __init__(self, host, port):

        super(AbstractTextServerQt,self).__init__()
        self._host =host
        self._port =int(port)
        self.subsc_map = {}
        self.ibuffer = None
        self.delay = 1
        self.ibuffer =QByteArray()
        self.tcpSocket = QTcpSocket()
        
        self.is_connected = False
        self.decoder = str
        
        self.tcpSocket.readyRead.connect(self._read_handler)
        self.tcpSocket.connected.connect(self._connected_handler)
        self.tcpSocket.disconnected.connect(self._disconnected_handler)
        self.tcpSocket.error.connect(self._error_handler)
        
        self.tcpSocket.connectToHost(self._host,self._port)
        
    
    
    def __reconnect(self):
        
        if self.tcpSocket.isValid() and self.tcpSocket.state() > QTcpSocket.UnconnectedState:
            return
        self.tcpSocket.close()
        
        del self.tcpSocket
        self.tcpSocket = QTcpSocket()
        
        self.tcpSocket.readyRead.connect(self._read_handler)       
        self.tcpSocket.connected.connect(self._connected_handler)
        self.tcpSocket.disconnected.connect(self._disconnected_handler)
        self.tcpSocket.error.connect(self._error_handler)
        
        self.tcpSocket.connectToHost(self._host, self._port)
        
    
    def _connected_handler(self):
        self.is_connected = True
        self.delay = 1
        self._resubscribe()
        
        

    def _state_changed_handler(self,state):
        
        pass
    
    def _disconnected_handler(self):
        
        self.is_connected = False
        QTimer.singleShot(self.delay*1000,self.__reconnect)
        self._unsubscribe_all()

    def _error_handler(self,error):
        
        self.is_connected = False
        if self.tcpSocket.state() == QTcpSocket.UnconnectedState:
            QTimer.singleShot(self.delay*1000,self.__reconnect)
            if self.delay < 300:
                self.delay = self.delay*2
    
    def _read_handler(self):

        buf = self.tcpSocket.readAll()
        self.ibuffer.append(buf)

        pos = self.ibuffer.indexOf('\n')
        while pos > 0:
            tmp = self.ibuffer.left(pos)
            self.ibuffer.remove(0,pos+1)
            #print(tmp.data().decode('KOI8-R'))
            #message = self._decode(tmp.data().decode('KOI8-R'))

            #print(tmp.data().decode('UTF-8'))
            message = self._decode(tmp.data().decode('UTF-8'))

            if message:
                self._notify(message)
            pos = self.ibuffer.indexOf('\n')

    
    
    def _decode(self,data):
        raise NotImplementedError('_decode method not implemented')


    def _encode(self, message):
        raise NotImplementedError('_decode method not implemented')        
    
    def _push(self,data): 
        self.tcpSocket.writeData(data.encode('ASCII'))
    
    def _notify(self, message):
        # print(message)
        name = message.get('name',None)
        if name:
            channel = self.subsc_map[name]
            channel._handler(message)



    def _subscribe(self, name):
        raise NotImplementedError
    
    def _resubscribe(self):
        for name in self.subsc_map:
            self._subscribe(name)
    
    def _unsubscribe_all(self):
        pass

    def disconnect(self):
        self.tcpSocket.close()
    
    

    def send_message(self, message):
        txt_message = self._encode(message)
        self._push(txt_message)    
    
    
    def collect_incoming_data(self,data):
        self.ibuffer.append(data)
    
    

    def get_channel(self, name, mappers):
        if not name:
            return None
        if name not in self.subsc_map:
            channel = ChannelServerQt.Channel(self, name, mappers)
            self.subsc_map[name] = channel
            if self.is_connected:
                self._subscribe(name)
        else:
            channel = self.subsc_map[name]
        return channel

class ChannelServerQt(AbstractTextServerQt):


    ibuffer = None
    delay = 1


    def __init__(self, host, port):

        super(ChannelServerQt,self).__init__(host, port )
        
    def __normalize(self, message):
        for k,v in message.items():
            if k in ('val','value','v'):
                message["value"] = v
                del message[k]
                break
        return message
    
    
    def _decode(self,data):
        # print(data)
        obj = None
        tokens = data.split('|')
        
        resp_dict = dict()
        for token in tokens:
            
            if token:
                k,v = token.split(':')
                resp_dict[k]=v
        resp_dict = self.__normalize(resp_dict)
        return resp_dict

    
    

    def _subscribe(self, name):
        self.send_message({"method":"subscribe","name":name})
    


    def _encode(self, message):
        return '|'.join(["%s:%s" %(k,v) for k,v in message.items()])+"\n"
    
    
    
    

    # def found_terminator(self):
        # data = ''.join(self.ibuffer)
        
class PulseServerQt(AbstractTextServerQt):




    ibuffer = None
    delay = 1
    errors = ["Element, Register or KVCH not found","ERROR: Wrong Server Header"]

    def __init__(self, host, port):

        super(PulseServerQt,self).__init__(host, port)
        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._poll_data)
        
    def _poll_data(self):
        for name in self.subsc_map:
            self.send_message({"name":name, "method":"GET ALL"})

    
    def _decode(self,data):
        #print(data)
        obj = None
        tokens = data.split('|')
        
        resp_dict = dict()

        resp_dict['value'] = tokens[1]
        if resp_dict['value'] in self.errors:
            raise RuntimeError("Bad name or answer")
        resp_dict["name"] = tokens[0].split(' ')[1]
        return resp_dict
    
    def _unsubscribe_all(self):
        self._timer.stop()

    def _resubscribe(self):
        self._timer.start()
   
    def _encode(self, message):
        return ' '.join(["Pulse",message["name"],message["method"]])+"\n"
    
    
    def _subscribe(self, name):
        pass



if __name__ == '__main__':
    import sys
    
    from PyQt5 import QtCore
    app = QtCore.QCoreApplication(sys.argv)
    cas =ChannelServerQt('172.16.1.110',20041)
    
    chan = cas.get_channel('BEP/Currents/pPMT',vcas_mappers)
    pulse_server = PulseServerQt('172.16.1.108',21030)
    #pulse_server = PulseServerQt('127.0.0.1',21030)

    #chan = pulse_server.get_channel('M1',pulse_reg_mappers)

    def slot():
        print(chan.name,chan.value, chan.update_time )
    # chan.updated.connect(slot)
    chan.updated.connect(slot)
    
    sys.exit(app.exec_())
