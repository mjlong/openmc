#!/bin/sh

matdir="/scratch/jinmiao/jlmiao/BEAVRS_matrix"
for t in $(seq 1 300); do 
    i=`expr 47000 + $t`; 
    if [ -d "$matdir/seed_$i" ]
    then  # simulation done; moved or moving to scratch
        sw=$(find $matdir/seed_$i/ -maxdepth 1 -name source*h5|wc -l);    
        hc=$(find $matdir/seed_$i/ -maxdepth 1 -name statepoint*h5|wc -l); 
        if [ "345" = $hc ] && [ "1" = $sw ] 
        then 
            echo $i ":moved"
        else 
            echo $i ":moving by other scripts"
        fi
    else 
        ir=$(qstat -u jinmiao | grep mid$i | wc -l);
        if [ "1" = $ir ]
        then # running
            echo $i ":running or queueing"
	else # completed or aborted
	    sw=0
	    hc=0
	    if [ -d seed_$i ] 
	    then 
                sw=$(find ./seed_$i/ -maxdepth 1 -name source*h5|wc -l);    
                hc=$(find ./seed_$i/ -maxdepth 1 -name statepoint*h5|wc -l); 
	    fi
            echo $i $hc $sw 
            if [ "345" = $hc ] && [ "1" = $sw ] 
	    then # completed
                echo $i ":moving"
                mv seed_$i /scratch/jinmiao/jlmiao/BEAVRS_matrix/ 
	    else # aborted, resubmit
                echo resubmit $i'...'
                rm -rf s$i; 
                mkdir s$i
                rm -rf seed_$i; 
                mkdir seed_$i
                cp s000/*.xml s$i/
                cp s000/s000.pbs s$i/s$i.pbs
                cd s$i/
                sed -i "s/@@seed@@/$i/g" s$i.pbs
                sed -i "s/@@seed@@/$i/g" settings.xml
                qsub s$i.pbs
                cd ..
                sleep 5
	    fi
        fi 
    fi  
    sleep 0.2
done
