# -*- coding: utf-8 -*-
from urllib.parse import urlparse

class TangoFactory:

	def __init__(self,*args):
		from .tango_channels import TangoChannel
		self.__class = TangoChannel

	def __call__(self, attr_name, *args):
		return self.__class(attr_name)

class VCASFactory:

	def __init__(self, host, port):
		from .v2k_channels import ChannelServerQt
		self.__server =ChannelServerQt(host, port)

	def __call__(self, attr_name, mappers):
		return self.__server.get_channel(attr_name, mappers)

class PulseFactory:

	def __init__(self, host, port):
		from .v2k_channels import ChannelServerQt
		self.__server =PulseServerQt(host, port)

	def __call__(self, attr_name, mappers):
		return self.__server.get_channel(attr_name, mappers)



class ChannelFactory(object):

	_defaul_conf = {
			'vcas':('172.16.1.110',20041),
    		'pulse':('172.16.1.108',21030),
    		'tango':()
	}
	
	_scheme_to_factory = {
		'tango' : TangoFactory,
		'vcas'  : VCASFactory,
		'pulse'  : PulseFactory
	} 


	def __init__(self, conf):
		self._conf = self._defaul_conf.copy()
		self._conf.update(conf)

		self._factories = {}
		
	def _get_factory(self, scheme):
		factory = self._factories.get(None)
		
		if factory is None:
			
			factory_class = self._scheme_to_factory[scheme]
			factory = factory_class(*self._conf[scheme])

			self._factories[scheme] = factory

		return factory

	def __call__(self, scheme, name, *args):
		
		factory = self._get_factory(scheme)
		return factory(name, *args)
