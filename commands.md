# rebuild container
docker kill puller; docker rm puller; docker build -t puller . && docker run -p 4000:3000 --name puller --restart always -d puller && docker logs -f --tail 500 puller


#update sync_calendar.py, send_email.py, secrets_parameters.py on server & enter it
cd /$HOME/Documents/aws_server && scp -i "Debian_KP_Phill.pem" -r $HOME/Documents/GitHub/headsup3/sync_calendar.py admin@ec2-13-58-216-232.us-east-2.compute.amazonaws.com:~/headsup3 && scp -i "Debian_KP_Phill.pem" -r $HOME/Documents/GitHub/headsup3/send_email.py admin@ec2-13-58-216-232.us-east-2.compute.amazonaws.com:~/headsup3 && scp -i "Debian_KP_Phill.pem" -r $HOME/Documents/GitHub/headsup3/secrets_parameters.py admin@ec2-13-58-216-232.us-east-2.compute.amazonaws.com:~/headsup3  && ssh -i "Debian_KP_Phill.pem" admin@ec2-13-58-216-232.us-east-2.compute.amazonaws.com

#update duties.csv on server & enter it
cd /$HOME/Documents/aws_server && scp -i "Debian_KP_Phill.pem" -r $HOME/Documents/GitHub/headsup3/duties.csv admin@ec2-13-58-216-232.us-east-2.compute.amazonaws.com:~/headsup3 && ssh -i "Debian_KP_Phill.pem" admin@ec2-13-58-216-232.us-east-2.compute.amazonaws.com

#update ps_query on server
cd /$HOME/Documents/aws_server && scp -i "Debian_KP_Phill.pem" -r $HOME/Documents/GitHub/headsup3/ps_query.py admin@ec2-13-58-216-232.us-east-2.compute.amazonaws.com:~/headsup3

#update secrets_parameters.py on server
cd /$HOME/Documents/aws_server && scp -i "Debian_KP_Phill.pem" -r $HOME/Documents/GitHub/headsup3/secrets_parameters.py admin@ec2-13-58-216-232.us-east-2.compute.amazonaws.com:~/headsup3


#update all files on server
cd /$HOME/Documents/aws_server && scp -i "Debian_KP_Phill.pem" -r $HOME/Documents/GitHub/headsup3/ admin@ec2-13-58-216-232.us-east-2.compute.amazonaws.com:~/headsup3 && ssh -i "Debian_KP_Phill.pem" admin@ec2-13-58-216-232.us-east-2.compute.amazonaws.com



# update Dockerfile
cd /$HOME/Documents/aws_server && scp -i "Debian_KP_Phill.pem" -r $HOME/Documents/GitHub/headsup3/Dockerfile admin@ec2-13-58-216-232.us-east-2.compute.amazonaws.com:~/headsup3

# update pypypowerschool
cd /$HOME/Documents/aws_server && scp -i "Debian_KP_Phill.pem" -r $HOME/Documents/GitHub/headsup3/pypypowerschool.py admin@ec2-13-58-216-232.us-east-2.compute.amazonaws.com:~/headsup3


# update ps_query
cd /$HOME/Documents/aws_server && scp -i "Debian_KP_Phill.pem" -r $HOME/Documents/GitHub/headsup3/ps_query.py admin@ec2-13-58-216-232.us-east-2.compute.amazonaws.com:~/headsup3


# update sync_calendar.py on server & enter it
cd /$HOME/Documents/aws_server && scp -i "Debian_KP_Phill.pem" -r $HOME/Documents/GitHub/headsup3/sync_calendar.py admin@ec2-13-58-216-232.us-east-2.compute.amazonaws.com:~/headsup3 && ssh -i "Debian_KP_Phill.pem" admin@ec2-13-58-216-232.us-east-2.compute.amazonaws.com






#restart container
docker kill headsup; cd $HOME/headsup3; docker run --name headsup --restart always -d headsup && docker logs -f --tail 500 headsup

# enter docker shell
docker exec -it headsup /bin/bash

# log in to server
cd /$HOME/Documents/aws_server && ssh -i "Debian_KP_Phill.pem" admin@ec2-13-58-216-232.us-east-2.compute.amazonaws.com

# follow logs
docker logs -f --tail 500 headsup

#copy latest log from container to slot root & exit
sudo docker cp headsup:logs/debug.log . && exit

#copy latest log from slot to local machine
scp -i "Debian_KP_Phill.pem" -r  admin@ec2-13-58-216-232.us-east-2.compute.amazonaws.com:~/debug.log $HOME/Documents/







#DOESNT WORK copy sync_calendar.py into container and restart it
sudo docker cp ~/headsup3/sync_calendar.py headsup:/ && docker kill headsup; docker rm headsup; cd $HOME/headsup3; docker run --name headsup --restart always -d headsup && docker logs -f --tail 500 headsup