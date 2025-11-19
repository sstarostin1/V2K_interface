from PyQt5 import QtCore
from PyQtVChannels import ChannelFactory
from PyQtVChannels import utils
import sys

app = QtCore.QCoreApplication([])
factory = ChannelFactory({})
chan = factory('vcas','VEPP/Currents/e', utils.vcas_mappers)

def slot():
    print(chan.name,chan.value, chan.update_time )
    # chan.updated.connect(slot)
chan.updated.connect(slot)
    
sys.exit(app.exec_())
