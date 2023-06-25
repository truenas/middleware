import constants
import os

from nslcd import NslcdClient
from contextlib import contextmanager


class MidNslcdClient:
    def is_alive(self):
        return os.path.exists(constants.NSLCD_SOCKET)

    @contextmanager
    def __nslcd_ctx(self, action):
        if not self.is_alive():
            raise RuntimeError('nslcd socket not found')

        try:
            c = NslcdClient(action)
            yield c
        finally:
            c.close()

    def __group_list_from_resp(self, con):
        results = []
        while con.get_response() == constants.NSLCD_RESULT_BEGIN:
            entry = {
                'gr_name': con.read_string(),
                'gr_passwd': con.read_string(),
                'gr_gid': con.read_int32(),
                'gr_mem': con.read_stringlist()
            }
            results.append(entry)

        return results

    def __passwd_list_from_resp(self, con):
        results = []
        while con.get_response() == constants.NSLCD_RESULT_BEGIN:
            entry = {
                'pw_name': con.read_string(),
                'pw_passwd': con.read_string(),
                'pw_uid': con.read_int32(),
                'pw_gid': con.read_int32(),
                'pw_gecos': con.read_string(),
                'pw_dir': con.read_string(),
                'pw_shell': con.read_string()
            }
            results.append(entry)

        return results

    def getgrall(self):
        try:
            with self.__nslcd_ctx(constants.NSLCD_ACTION_GROUP_ALL) as con:
                res = self.__group_list_from_resp(con)
        except OSError:
            # nss_disable_enumeration yes
            res = []

        return res

    def getgrgid(self, gid):
        with self.__nslcd_ctx(constants.NSLCD_ACTION_GROUP_BYGID) as con:
            con.write_int32(int(gid))
            res = self.__group_list_from_resp(con)

        if not res:
            raise KeyError(f'nslcd.getgrgid(): gid not found: {gid}')

        return res[0]

    def getgrnam(self, group_name):
        with self.__nslcd_ctx(constants.NSLCD_ACTION_GROUP_BYNAME) as con:
            con.write_string(group_name)
            res = self.__group_list_from_resp(con)

        if not res:
            raise KeyError(f'nslcd.getgrnam(): group not found: {group_name}')

        return res[0]

    def getpwall(self):
        try:
            with self.__nslcd_ctx(constants.NSLCD_ACTION_PASSWD_ALL) as con:
                res = self.__passwd_list_from_resp(con)
        except OSError:
            # nss_disable_enumeration yes
            res = []

        return res

    def getpwuid(self, uid):
        with self.__nslcd_ctx(constants.NSLCD_ACTION_PASSWD_BYUID) as con:
            con.write_int32(int(uid))
            res = self.__passwd_list_from_resp(con)

        if not res:
            raise KeyError(f'nslcd.getpwuid(): uid not found: {uid}')

        return res[0]

    def getpwnam(self, user_name):
        with self.__nslcd_ctx(constants.NSLCD_ACTION_PASSWD_BYNAME) as con:
            con.write_string(user_name)
            res = self.__passwd_list_from_resp(con)

        if not res:
            raise KeyError(f'nslcd.getpwnam(): user not found: {user_name}')

        return res[0]
