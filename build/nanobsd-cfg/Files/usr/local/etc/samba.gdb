set pagination off
set logging file /var/log/samba4/samba.backtraces
set logging on
set verbose off
set width 0
set height 0
set print pretty on

printf "[backtrace full]\n"
backtrace full
printf "\n"

printf "[info registers]\n"
info registers
printf "\n"

printf "[instruction pointer]\n"
x/16i $pc
printf "\n"

printf "[thread apply all backtrace]"
thread apply all backtrace
printf "\n"

printf "[current frame]\n"
frame
printf "\n"

detach
quit
