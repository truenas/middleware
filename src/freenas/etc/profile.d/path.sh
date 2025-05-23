# Replace default non-superuser PATH provided by `/etc/profile` with the one that includes `/sbin` in order to
# allow non-privileged users to access `zfs` and `zpool` commands without having to type in full path.
# Requested by NAS-133669
if [ x"$PATH" = x"/usr/local/bin:/usr/bin:/bin:/usr/local/games:/usr/games" -o x"$PATH" = x"/usr/local/bin:/usr/bin:/bin:/usr/games" ];
then
  export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
fi
