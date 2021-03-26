<%
    pci_ids = middleware.call_sync('device.get_to_isolate_pci_ids')
    if not pci_ids:
        raise FileShouldNotExist()
%>\
softdep nouveau pre: vfio-pci
softdep nvidia pre: vfio-pci
softdep nvidia* pre: vfio-pci
