DATE=`date '+%Y-%m-%d %H:%M:%S'`
echo "Media server started at ${DATE}" | systemd-cat -p info

cd /media/exdrive/media_server
docker-compose pull
docker-compose up
