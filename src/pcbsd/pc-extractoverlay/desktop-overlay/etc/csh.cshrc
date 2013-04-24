# $FreeBSD: src/etc/csh.cshrc,v 1.3 1999/08/27 23:23:40 peter Exp $
#
# System-wide .cshrc file for csh(1).
if ( $?LANG ) then
else
  setenv LANG en_US.UTF-8
endif
#setenv LC_CTYPE en_US.UTF-8
#setenv LC_COLLATE POSIX
setenv  EDITOR  	ee
setenv  PAGER   	less
setenv  BLOCKSIZE       K

# Set the MANPATH
unsetenv MANPATH
setenv MANPATH `manpath`

# Enable the delete key
bindkey [3~ delete-char
