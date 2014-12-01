__author__ = 'ddragosd'
# coding=utf-8

"""
Controller for the FFmpeg process
"""

import subprocess
import json
from urllib2 import Request, urlopen, URLError
import logging
import re
import time
import datetime
from configobj import ConfigObj
import os
import argparse


class LiveTranscoder:
    def __init__(self):
        # initialize config
        # Initialize Blank Configs
        self.config = ConfigObj()

        # Initialize Logger
        self.log = logging.getLogger("LiveTranscoder")
        self.log.setLevel(logging.DEBUG)
        log_format = logging.Formatter("%(asctime)s %(name)s [%(levelname)s]: %(message)s")
        log_filename = "/var/log/streamkit/live_transcoder_%s.log" % \
                       (datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d_%H_%M_%S'))
        try:
            file_handler = logging.FileHandler(log_filename)
            file_handler.setFormatter(log_format)
            self.log.addHandler(file_handler)
        except:
            pass

        # when executing the collector separately, log directly on the output stream
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(log_format)
        self.log.addHandler(stream_handler)

        logging.getLogger('LiveTranscoder').addHandler(stream_handler)

    def _get_default_config(self, file_name='/etc/live-transcoder/default_config.json'):
        config_file = open(file_name)
        cfg = json.load(config_file)
        config_file.close()

        return cfg

    def _get_user_config(self, user_config_json):
        try:
            self.log.info("Loading user-data: %s", user_config_json)
            config = json.loads(user_config_json)
            self.log.info("User-Data: %s", json.dumps(config))
            return config
        except Exception, e:
            self.log.exception(e)
            return None


    def _updateStreamMetadataInConfig(self, config):
        """
        Reads config.source metadata (width, height, bitrate, HD) and adds it back into the config object
        """
        self.log.info("Reading metadata for %s", config.get("source"))
        cfg = config

        proc = subprocess.Popen(["ffmpeg", "-i", config.get("source")], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stdoutdata, stderrdata = proc.communicate()
        ffmpeg_response = stderrdata

        self.log.debug("FFMPEG result %s", ffmpeg_response)
        regex = re.compile("bitrate:\s(\d+)\s", re.IGNORECASE | re.MULTILINE | re.DOTALL)
        bitrate = regex.search(ffmpeg_response)
        if bitrate is not None:
            bitrate = bitrate.group(1)
            cfg["bitrate"] = bitrate
            self.log.info("Source bitrate: %s", bitrate)

        regex = re.compile("\s(\d+)x(\d+)\s", re.IGNORECASE | re.MULTILINE | re.DOTALL)
        size = regex.search(ffmpeg_response)
        width = 1
        height = 1
        ratio = 0
        isHD = False
        if size is not None:
            width = int(size.group(1))
            height = int(size.group(2))
            ratio = round(width / float(height), 2)
            isHD = ratio == 1.77
            self.log.info("Source size: width=%d, height=%d, ratio=%.4f, HD=%s", width, height, ratio, isHD)

        cfg["width"] = width
        cfg["height"] = height
        cfg["HD"] = isHD

        return cfg


    def _getTranscodingCmd(self, config):
        bitrates = None
        if config["HD"] == True:
            bitrates = config["hd_streams"]
        else:
            bitrates = config["sd_streams"]

        cmd = 'ffmpeg -i %s ' % (config["source"])
        sub_commands = []
        for quality in bitrates:
            if int(quality["bitrate"]) <= int(config["bitrate"]):
                sub_cmd_template = """-f flv -c:a copy -c:v libx264 -s %dx%d -x264opts bitrate=%d -rtmp_playpath %s -rtmp_app %s %s """
                sub_cmd_template_audio = """-f flv -c:a copy -b:a %dk -c:v libx264 -s %dx%d -x264opts bitrate=%d -rtmp_playpath %s -rtmp_app %s %s """
                target_stream = config["target_stream"]
                target_stream = target_stream.replace("$width", str(quality["width"]))
                target_stream = target_stream.replace("$height", str(quality["height"]))
                target_stream = target_stream.replace("$bitrate", str(quality["bitrate"]))
                sub_cmd = ''
                if "audio_bitrate" in quality:
                    sub_cmd = sub_cmd_template_audio % (
                        quality["audio_bitrate"], quality["width"], quality["height"], quality["bitrate"],
                        target_stream,
                        config["target_app"], config["target_host"] )
                else:
                    sub_cmd = sub_cmd_template % (
                        quality["width"], quality["height"], quality["bitrate"], target_stream,
                        config["target_app"], config["target_host"] )
                cmd = cmd + sub_cmd
        return cmd

    def _runTranscodingCommand(self, command_with_args):
        try:
            s = subprocess.Popen(command_with_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            while True:
                line = s.stdout.readline()
                if not line:
                    break
                self.log.info(line)
            self.log.info("FFmpeg process stopped normally.")
            return 1
        except Exception, e:
            # Note that FFMpeg will always exit with error code for live transcoding
            self.log.info("FFmpeg process stopped. Reason:")
            self.log.exception(e)
            return -1

    def startLiveTranscoding(self, user_config_json):
        # Load default
        self.config.merge(self._get_default_config())
        # Merge with user data
        user_config = self._get_user_config(user_config_json)
        if user_config is not None:
            self.config.merge(user_config)
        self.log.info("Running live-transcoder with configuration: %s", self.config)

        max_retries = int(self.config["max_retries"])
        max_retries_delay = int(self.config["max_retries_delay_sec"])
        for i in range(1, max_retries + 1):
            self.config = self._updateStreamMetadataInConfig(self.config)

            cmd = self._getTranscodingCmd(self.config)
            self.log.info("Executing FFmpeg command:\n%s\n", cmd)

            # start live transcoding
            cmd_args = cmd.split()
            self.log.info("Running command. (run=%d/%d)", i, max_retries)
            r = self._runTranscodingCommand(cmd_args)
            self.log.info("Transcoding command stopped. (run=%d/%d). Code=%d", i, max_retries, r)
            time.sleep(max_retries_delay)

        self.log.info("Live-Transcoder has completed ! You can now shutdown the instance.")


transcoder = LiveTranscoder()
user_config_json = None
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--user-config-json', dest='user_config_json')
    args = parser.parse_args()
    user_config_json = args.user_config_json

transcoder.startLiveTranscoding(user_config_json)