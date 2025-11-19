




vcas_mappers = (lambda m: float(m['value']), lambda v: {'val':str(v)} )
vcas_str_mappers = (lambda m: str(m['value']), lambda v: {'val':str(v)} )

ceac124_mappers = (lambda m: float(m['dac']), lambda v: {'val':str(v)} )
vsdc_mappers = (lambda m: float(m['int']), None )
gvim_mappers = (lambda m: float(m['mask']), None )
regout_mappers = (lambda m: float(m['value']), None )
pulse_reg_mappers = (lambda m: m['value']=='ON', lambda v: {'value':'ON' if v else 'OFF'} )