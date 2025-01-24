#!/usr/bin/env bash

while true
do
  python "$@"
  status=$?
  if [ $status -eq 0 ]
  then
    exit 0
  else
    echo "Script crashed with exit code $status. Restarting in 5s."
    sleep 5
  fi
done