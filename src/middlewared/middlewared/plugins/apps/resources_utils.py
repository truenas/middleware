def get_gpu_base_dict() -> dict:
    return {
        'vendor': '',
        'description': '',
        'error': None,
        'vendor_specific_config': {},
        'gpu_details': {},
    }


def get_normalized_gpu_choices(all_gpus_info: list[dict], nvidia_gpus: dict) -> list[dict]:
    all_gpus_info = {gpu['addr']['pci_slot']: gpu for gpu in all_gpus_info}
    gpus = []
    for pci_slot, gpu_info in all_gpus_info.items():
        gpu_config = get_gpu_base_dict() | {
            'vendor': gpu_info['vendor'],
            'description': gpu_info['description'],
            'gpu_details': gpu_info,
        }
        gpus.append(gpu_config)

        if gpu_info['vendor'] == 'NVIDIA':
            if pci_slot not in nvidia_gpus:
                gpu_config.update({
                    'error': 'Unable to locate GPU details from procfs',
                })
                continue

            nvidia_gpu = nvidia_gpus[pci_slot]
            error = None
            if not nvidia_gpu.get('gpu_uuid'):
                error = 'GPU UUID not found'
            elif '?' in nvidia_gpu['gpu_uuid']:
                error = 'Malformed GPU UUID found'
            if error:
                gpu_config.update({
                    'error': error,
                    'nvidia_gpu_details': nvidia_gpu,
                })
                continue

            gpu_config.update({
                'vendor_specific_config': {
                    'uuid': nvidia_gpu['gpu_uuid'],
                },
                'description': nvidia_gpu.get('model') or gpu_config['description'],
            })

        if not gpu_info['available_to_host']:
            gpu_config.update({
                'error': 'GPU not available to host',
            })

    return gpus
