#/bin/sh

matdir="/scratch/jinmiao/jlmiao/BEAVRS_matrix"
for i in $(seq 1 300) 
do 
    r=`expr 47000 + $i`
    if [ -d "$matdir/mat$r" ]
    then 
        fc=$(find $matdir/mat$r/ -maxdepth 1 -type d -name "seed_*"|wc -l);         
	echo $r $fc
	if [ "11" = $fc ]
	then 
	    echo $r ":copied"
	fi
    else
        if [ -d "$matdir/seed_$r" ]
        then
            sw=$(find $matdir/seed_$r/ -maxdepth 1 -name source*h5|wc -l);    
            hc=$(find $matdir/seed_$r/ -maxdepth 1 -name statepoint*h5|wc -l); 
            if [ "345" = $hc ] && [ "1" = $sw ] 
            then 
                echo $r ":ready to copy"
                for t in $(seq 335 345)
                do 
                  echo treating $r '-' $t'...'
                  mkdir -p $matdir/mat$r/seed_$t
                  cp       $matdir/seed_$r/statepoint.$t.h5 $matdir/mat$r/seed_$t/statepoint.1.h5
                done 
            else 
                echo $r ":not ready to copy, still in moving"
            fi
        fi
    fi

    sleep 1
done
