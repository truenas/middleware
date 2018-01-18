#set debug-file-directory /mnt/tank/world
define init_python
python
sys.path.append('/usr/local/share/python-gdb')
import libpython
end
end
