# $FreeBSD: head/etc/root/dot.cshrc 170088 2007-05-29 06:37:58Z dougb $
#
# .cshrc - csh resource script, read at beginning of execution by each shell
#
# see also csh(1), environ(7).
#

alias h		history 25
alias j		jobs -l
alias la	ls -a
alias lf	ls -FA
alias ll	ls -lA

# A righteous umask
umask 22

set path = (/sbin /bin /usr/sbin /usr/bin /usr/games /usr/local/sbin /usr/local/bin $HOME/bin /usr/local/fusion-io)

setenv	EDITOR	vi
setenv	PAGER	less
setenv	BLOCKSIZE	K

if ($?prompt) then
	# An interactive shell -- set some stuff up
	set filec
	set history = 500
	set savehist = 500
	set mail = (/var/mail/$USER)
	if ( $?tcsh ) then
		bindkey "^W" backward-delete-word
		bindkey -k up history-search-backward
		bindkey -k down history-search-forward
	endif
endif

# Decrease likelihood of filesystem metadata corruption on [CF,SD,USB]
# persistent media by setting '-o noatime'.
alias mountrw	mount -o noatime -uw

#Bind Delete, Home, End and Insert keys
if ($?tcsh && $?prompt) then
bindkey "\e[1~" beginning-of-line # Home
bindkey "\e[7~" beginning-of-line # Home rxvt
bindkey "\e[2~" overwrite-mode # Ins
bindkey "\e[3~" delete-char # Delete
bindkey "\e[4~" end-of-line # End
bindkey "\e[8~" end-of-line # End rxvt
endif
