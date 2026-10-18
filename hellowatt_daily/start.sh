#!/bin/sh
set -eu
# Independent of the daily collection: no Hello Watt login here.
python /app/install_card.py &
printf '*/10 * * * * /usr/local/bin/python /app/run.py >> /proc/1/fd/1 2>> /proc/1/fd/2\n' > /etc/crontabs/root
if ! python /app/run.py --startup; then
    echo 'Essai au démarrage différé ou en échec ; le planificateur reste actif.'
fi
exec crond -f -l 8
