<%
    from packaging import version

    info = middleware.call_sync('system.dmidecode_info')
    vers = info['system-version']
    prod = info['system-product-name']

    gen1_2 = gen3 = False
    if not all((prod, vers)) or not prod.startswith('TRUENAS-M'):
        # nvdimm config module is only relevant on m series.
        raise FileShouldNotExist()
    elif vers in ('0123456789', '123456789'):
        # 0123456789/12345679 are some of the default values that we've
        # seen from supermicro. Before gen3 m-series hardware, we were not
        # changing this value so this is a way to identify gen1/2.
	gen1_2 = True
    else:
        try:
	    curr_vers = version.parse(vers).major
	    gen3_min_vers = version.Version('3.0').major
        except Exception as e:
	    middleware.logger.error('Failed determining hardware version: %r', e)
	    raise FileShouldNotExist()
        else:
            # for now we only check to make sure that the current version is 3 because
            # we quickly found out that the SMBIOS defaults for the system-version value
            # from supermicro aren't very predictable. Since setting these values on a
            # system that doesn't support the dual-nvdimm configs leads to "no carrier"
            # on the ntb0 interface, we play it safe. The `gen3_min_vers` will need to be
            # changed as time goes on if we start tagging hardware with 4.0,5.0 etc etc
            if curr_vers == gen3_min_vers:
                gen3 = True
            else:
                gen1_2 = True

    options = [
        'options ntb driver_override="ntb_split"',
        'options ntb_transport use_dma=1',
    ]

    if gen1_2:
        # single nvdimm on gen1/2 hardware
        options.append('options ntb_split config="ntb_pmem:1:4:0,ntb_transport"')
    elif gen3:
        # dual nvdimm on gen3 hardware
        options.append('options ntb_hw_plx usplit=1')
        options.append('options ntb_split config="ntb_pmem:1:4:0,ntb_pmem:1:4:0,ntb_transport"')
%>\
% for option in options:
${option}
% endfor
