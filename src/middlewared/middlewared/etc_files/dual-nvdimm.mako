<%
    info = middleware.call_sync('system.dmidecode_info')
    vers = info['system-version']
    prod = info['system-product-name']

    if (prod and not prod.startswith('TRUENAS-M')) or (vers and vers in ('0123456789', '123456789')):
        # dual-nvdimm config module is only relevant on gen3 m-series.
        # 0123456789/12345679 are some of the default values that we've
        # seen from supermicro. Before gen3 m-series hardware, we were not
        # changing this value so this is a way to identify gen1/2.
	raise FileShouldNotExist()

    try:
        curr_vers = version.parse(vers)
        min_vers = version.Version('3.0')
    except Exception as e:
        middleware.logger.error('Failed determining hardware version: %r', e)
        raise FileShouldNotExist()

    if curr_vers.major == min_vers:
        # for now we only check to make sure that the current version is 3 because
        # we quickly found out that the SMBIOS defaults for the system-version value
        # from supermicro aren't very predictable. Since setting these values on a
        # system that doesn't support the dual-nvdimm configs leads to "no carrier"
	# on the ntb0 interface, we play it safe. The `min_vers` will need to be
        # changed as time goes on if we start tagging hardware with 4.0,5.0 etc etc
        options = [
            'options ntb_hw_plx usplit=1',
            'options ntb_split config="ntb_pmem:1:4:0,ntb_pmem:1:4:0,ntb_transport"',
        ]
    else:
        raise FileShouldNotExist()
%>\
% for option in options:
${option}
% endfor
