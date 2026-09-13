#!/bin/sh
set -eu
printf '0 8 * * * /usr/local/bin/python /app/run.py >> /proc/1/fd/1 2>> /proc/1/fd/2\n' > /etc/crontabs/root
if ! python /app/run.py --startup; then
    echo 'Essai au démarrage en échec ; le passage quotidien reste programmé.'
fi
exec crond -f -l 8
