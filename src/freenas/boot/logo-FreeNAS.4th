: logo ( x y -- ) \ "FreeNAS" logo in B/W (11 rows x 30 columns)

	6 + swap 0 + swap

	2dup at-xy ." +mmdhs/.   ,.:+sydmNMm       " 1+
	2dup at-xy ."  hMMMMMMdydNMMMMMMMMM:       " 1+
	2dup at-xy ."  yMMMMMMMMMMMMMMMNNNo        " 1+
	2dup at-xy ." /MMMMMMMMMMMMMMMmho.        ." 1+
	2dup at-xy ." NMMMMMMMMMMMMMMMMm:'    ..:yN" 1+
	2dup at-xy ." MMMMMMMMMMMMMMMmMNmddmydmNMMo" 1+
	2dup at-xy ." mMMMMMMMMMMMMMs./ymMMMMMMmy- " 1+
	2dup at-xy ." :NMMMMMMMMMMMM.   `.oMMm-`   " 1+
	2dup at-xy ."  -mMMMMMMMMMMMmo/:/yNMh.     " 1+
	2dup at-xy ."  .mhdMMMMMMMMMMMMMMMh/       " 1+
	     at-xy ."  +'  `+ymMMMMMMNmy+'         "

	\ Put the cursor back at the bottom
	0 25 at-xy
;
