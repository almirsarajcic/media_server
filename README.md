# Media server setup

Composition of docker images consisting of [Plex](https://www.plex.tv) for video streaming, [Transmission](https://transmissionbt.com) as a BitTorrent client of choice, collection managers [Sonarr](https://sonarr.tv) for TV shows and [Radarr](https://radarr.video) for movies, [Jackett](https://github.com/Jackett/Jackett) as a proxy between Sonarr, Radarr and various torrent trackers and [Bazarr](https://www.bazarr.media/) for subtitles, all working together to make your home media center setup easier.

Tested on Ubuntu 20.04.2 LTS for Raspberry Pi 4 Model B with external HDD.

## Setup

1. create new directory in a desired location (the drive needs to have a lot of free space as your movies and TV shows collection will be saved there), e.g. `mkdir /media/exdrive/media_server`
2. copy `docker-compose.yml` file there, e.g. `cp docker-compose.yml /media/exdrive/media_server`
3. create new file `.env` in that directory and fill it using `.env.sample` as a template
4. update line `cd /media/exdrive/media_server` in `media_server.sh` file with your location, put it in `/usr/bin` and make it executable using `sudo chmod +x /usr/bin/media_server.sh`
5. put `media_server.service` file in `/etc/systemd/system` directory, update permissions using `sudo chmod 644 /etc/systemd/system/media_server.service`
6. check service status using `systemctl status media_server`, enable with `systemctl enable media_server` and reload systemd manager configuration with command `systemctl daemon-reload`
7. (optional) update crontab to restart media server every day at 4 AM to get docker image updates (`sudo crontab -e` and add the line `0 4   *   *   *    sudo systemctl restart media_server`)
8. visit each service's web address to configure it
9. enjoy

## Web Addresses

All the services can be accessed using your IP address and their port. Ports can be configured in `docker-compose.yml`.

- Bazarr http://localhost:6767
- Jackett http://localhost:9117
- Plex http://localhost:32400
- Radarr http://localhost:7878
- Sonarr http://localhost:8989
- Transmission http://localhost:9091
