ANA_OPTIMIZED_STATE = 'optimized'
ANA_INACCESSIBLE_STATE = 'inaccessible'
ANA_PORT_INDEX_OFFSET = 5000

NVMET_DEFAULT_ANA_GRPID = 1
NVMET_NODE_A_ANA_GRPID = 2
NVMET_NODE_B_ANA_GRPID = 3

NVMET_NODE_A_MAX_CONTROLLER_ID = 31999
NVMET_NODE_B_MIN_CONTROLLER_ID = 32000


def addr_traddr_to_address(index, addr_trtype, addr_traddr, render_ctx):
    result = addr_traddr
    if index > ANA_PORT_INDEX_OFFSET:
        choices = render_ctx[f'{addr_trtype.lower()}.nvmet.port.transport_address_choices']
        pair = choices[addr_traddr].split('/')
        match render_ctx['failover.node']:
            case 'A':
                result = pair[0]
            case 'B':
                result = pair[1]
    return result


def port_subsys_index(entry, render_ctx) -> int | None:
    # Because we have elected to support overriding the global ANA
    # setting for individual subsystems this has two knock-on effects
    # 1. Additional ANA-specific port indexes are injected
    # 2. Particular subsystems will link to either the ANA or non-ANA
    #    port index.
    # However, if we're on the standby node we never want to setup
    # a link to the VIP port.
    raw_index = entry['port']['index']
    # Now check whether ANA is playing a part.
    match entry['subsys']['ana']:
        case True:
            index = raw_index + ANA_PORT_INDEX_OFFSET
        case False:
            index = raw_index
        case _:
            if render_ctx['nvmet.global.ana_enabled']:
                index = raw_index + ANA_PORT_INDEX_OFFSET
            else:
                index = raw_index
    if index < ANA_PORT_INDEX_OFFSET and render_ctx['failover.status'] == 'BACKUP':
        return None
    return index


def ana_state(render_ctx):
    return ANA_OPTIMIZED_STATE if render_ctx['failover.status'] == 'MASTER' else ANA_INACCESSIBLE_STATE


def ana_grpid(render_ctx):
    match render_ctx['failover.node']:
        case 'A':
            return NVMET_NODE_A_ANA_GRPID
        case 'B':
            return NVMET_NODE_B_ANA_GRPID
        case _:
            return NVMET_DEFAULT_ANA_GRPID


def subsys_ana(subsys, render_ctx) -> bool:
    if not render_ctx['failover.licensed']:
        return False

    if render_ctx['nvmet.global.ana_enabled']:
        if subsys['ana'] is False:
            return False
        return True
    else:
        if subsys['ana']:
            return True
        return False


def subsys_visible(subsys, render_ctx) -> bool:
    match render_ctx['failover.status']:
        case 'SINGLE' | 'MASTER':
            return True
        case 'BACKUP':
            # Depends on the various ANA settings
            match subsys['ana']:
                case True:
                    return True
                case False:
                    return False
                case _:
                    if render_ctx['nvmet.global.ana_enabled']:
                        return True
                    else:
                        return False
