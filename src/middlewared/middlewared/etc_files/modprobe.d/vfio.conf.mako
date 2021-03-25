<%
    pci_ids = middleware.call_sync('device.get_to_isolate_pci_ids')
    if not pci_ids:
        raise FileShouldNotExist()
%>\
options vfio-pci ids=${",".join(pci_ids)}
