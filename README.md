ffmpeg live-transcoder
======================


Docker image using ffmpeg to encode a live stream from a source and push it to another target endpoint.
The image is based on: https://github.com/jrottenberg/ffmpeg.

Status
======

Under development.

Usage
=====

The Docker image expects an argument `--user-config-json` to be passed to the `ENTRYPOINT` which is a python script.

For an example of the `json` object you can check `default_config.json`.

Usage:

```
    docker run ddragosd/ffmpeg-live-transcoder:2.4.3-1.1 \
        --user-config-json "`cat /usr/local/live-transcoder-config.json`"

```

To specify a log file:

```
    docker run -v /var/log/streamkit:/var/log/streamkit ddragosd/ffmpeg-live-transcoder:2.4.3-1.1 \
        --user-config-json "`cat /usr/local/live-transcoder-config.json`" \
        --log-file "/var/log/streamkit/ffmpeg-live-transcoding.log"
```


SSH into the Docker container
=============================

```
docker run -ti --entrypoint='bash' ddragosd/ffmpeg-live-transcoder:2.4.3-1.1
```

