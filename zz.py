import hashlib
import os


def get_info(i):
    st = i.stat()
    uid, gid = st.st_uid, st.st_gid
    path = i.path
    with open(path, 'rb') as f:
        sha = hashlib.file_digest(f, 'sha256').hexdigest()
        print(f'uid: {uid!r} gid: {gid!r}, path: {path!r}, sha256: {sha!r}')


def recursive_iterate(path):
    with os.scandir(path) as dir_contents:
        for i in dir_contents:
            if i.is_file():
                get_info(i)
            elif i.is_dir():
                print(f'dir: {i.path!r}')
                recursive_iterate(i.path)
            else:
                continue


if __name__ == '__main__':
    recursive_iterate('.')
