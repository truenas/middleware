from middlewared.service import Service, private
from middlewared.schema import Int, returns
from middlewared.utils.network_.procfs import read_proc_net


class FTPService(Service):

    @private
    @returns(Int('number_of_connections'))
    def connection_count(self):
        ''' Return the number of active connections '''
        # FTP listening port is 21
        ftp = 21

        try:
            proc_data = read_proc_net()
            ftp_proclist = list(filter(lambda x: x.local_port == ftp and x.remote_port != 0, proc_data))
        except Exception:
            num_conn = 0
        else:
            num_conn = len(ftp_proclist)
            # NOTE: This count includes multiple 'connections' from a single client.
            #       If we want to report number of 'clients', we process the filtered list with:
            #       set_clients = set([':'.join(i.split()[4].split(':')[:-1]) for i in ftp_conn])
        return num_conn
