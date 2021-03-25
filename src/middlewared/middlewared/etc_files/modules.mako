<%
    pci_ids = middleware.call_sync('device.get_to_isolate_pci_ids')
    if not pci_ids:
        raise FileShouldNotExist()
%>\
vfio vfio_iommu_type1 vfio_pci ids=${",".join(middleware.call_sync('device.get_to_isolate_pci_ids'))}
