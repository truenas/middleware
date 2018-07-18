: brand ( x y -- ) \ "FreeNAS" [wide] logo in B/W (7 rows x 43 columns)

	2dup at-xy ."  ______              _     _   __    _____ " 1+
	2dup at-xy ." |  ____|            | \   | | /  \  /  ___|" 1+
	2dup at-xy ." | |___ _ __ ____ ___|  \  | |/ /\ \|  (__  " 1+
	2dup at-xy ." |  ___| '__/ _ |/ _ \ |\\ | | |__| |\___ \ " 1+
	2dup at-xy ." | |   | | |  __/  __/ | \\| |  __  |____) |" 1+
	2dup at-xy ." | |   | | |    |    | |  \  | |  | |      |" 1+
	     at-xy ." |_|   |_|  \___|\___|_|   \_|_|  |_|_____/ "

	\ Put the cursor back at the bottom
	0 25 at-xy
;
