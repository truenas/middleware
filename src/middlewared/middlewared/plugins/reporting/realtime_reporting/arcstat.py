from .utils import normalize_value, safely_retrieve_dimension


def get_arc_stats(netdata_metrics: dict) -> dict:
    data = {
        'arc_free_memory': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.free', 'free', 0),
        ),
        'arc_available_memory': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.avail', 'avail', 0),
        ),
        'arc_size': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.size', 'size', 0),
        ),
        'demand_accesses_per_second': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.dread', 'dread', 0),
        ),
        'demand_data_accesses_per_second': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.ddread', 'ddread', 0),
        ),
        'demand_metadata_accesses_per_second': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.dmread', 'dmread', 0),
        ),
        'demand_data_hits_per_second': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.ddhit', 'ddhit', 0),
        ),
        'demand_data_io_hits_per_second': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.ddioh', 'ddioh', 0),
        ),
        'demand_data_misses_per_second': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.ddmis', 'ddmis', 0),
        ),
        'demand_data_hit_percentage': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.ddh_p', 'ddh_p', 0),
        ),
        'demand_data_io_hit_percentage': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.ddi_p', 'ddi_p', 0),
        ),
        'demand_data_miss_percentage': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.ddm_p', 'ddm_p', 0),
        ),
        'demand_metadata_hits_per_second': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.dmhit', 'dmhit', 0),
        ),
        'demand_metadata_io_hits_per_second': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.dmioh', 'dmioh', 0),
        ),
        'demand_metadata_misses_per_second': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.dmmis', 'dmmis', 0),
        ),
        'demand_metadata_hit_percentage': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.dmh_p', 'dmh_p', 0),
        ),
        'demand_metadata_io_hit_percentage': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.dmi_p', 'dmi_p', 0),
        ),
        'demand_metadata_miss_percentage': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.dmm_p', 'dmm_p', 0),
        ),
        'l2arc_hits_per_second': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.l2hits', 'l2hits', 0),
        ),
        'l2arc_misses_per_second': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.l2miss', 'l2miss', 0),
        ),
        'total_l2arc_accesses_per_second': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.l2read', 'l2read', 0),
        ),
        'l2arc_access_hit_percentage': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.l2hit_p', 'l2hit_p', 0),
        ),
        'l2arc_miss_percentage': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.l2miss_p', 'l2miss_p', 0),
        ),
        'bytes_read_per_second_from_the_l2arc': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.l2bytes', 'l2bytes', 0),
        ),
        'bytes_written_per_second_to_the_l2arc': normalize_value(
            safely_retrieve_dimension(netdata_metrics, 'truenas_arcstats.l2wbytes', 'l2wbytes', 0),
        ),

    }

    return data
