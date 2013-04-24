# $FreeBSD: src/share/skel/dot.cshrc,v 1.13 2001/01/10 17:35:28 archie Exp $
#
# .cshrc - csh resource script, read at beginning of execution by each shell
#
# see also csh(1), environ(7).
#

alias h		history 100 
alias j		jobs -l
alias la	ls -a
alias lf	ls -FA
alias ll	ls -lA
alias ls	ls -G

# A righteous umask
umask 22

set path = (/sbin /bin /usr/sbin /usr/bin /usr/games /usr/local/sbin /usr/local/bin /usr/local/kde4/bin $HOME/bin)

setenv	CLICOLOR true
setenv	EDITOR	vi
setenv	PAGER	more
setenv	BLOCKSIZE	K

if ($?prompt) then
	# An interactive shell -- set some stuff up
	switch ($TERM)
    	case "xterm*":
		set prompt = '%{\033]0;%n@%m:%~\007%}[%B%n@%m%b] %B%~%b%# '
       		breaksw
    	default:
		set prompt = '[%B%n@%m%b] %B%~%b%# '
       		breaksw
	endsw
	set autolist = ambiguous
	set complete = enhance
	set correct = cmd
	set filec
	set autocorrect
	set filec
	set history = 100
	set savehist = 100
	set mail = (/var/mail/$USER)
	if ( $?tcsh ) then
		bindkey "^W" backward-delete-word
		bindkey -k up history-search-backward
		bindkey -k down history-search-forward
	endif
endif
