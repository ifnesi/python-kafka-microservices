# -*- coding: utf-8 -*-
#
# Copyright 2022 Confluent Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import re
import sys
import signal
import socket
import logging
import datetime
import requests
import importlib

from configparser import ConfigParser
from confluent_kafka import Producer, Consumer
from logging.handlers import TimedRotatingFileHandler
from confluent_kafka.admin import AdminClient


####################
# Global variables #
####################
FOLDER_PID = "pid"
FOLDER_LOGS = "logs"
EXTENSION_LOGS = ".app_log"
FOLDER_CONFIG_KAFKA = "config_kafka"
FOLDER_CONFIG_SYS = "config_sys"


#####################
# Generic functions #
#####################
def get_hostname() -> str:
    return socket.gethostname()


def import_state_store_class(db_module_class: str):
    try:
        module = importlib.import_module(db_module_class)
        if module is not None:
            return module.DB
        else:
            raise Exception()
    except Exception:
        log_exception(
            f"Unable to import db_module_class: {db_module_class}\n",
            sys.exc_info(),
        )
        sys.exit(0)


def get_system_config(
    sys_config_file: str,
    section: str = None,
) -> dict:
    def parse_list(data: str) -> list:
        return [
            item.strip()
            for item in data.replace("\r", "\n").split("\n")
            if item.strip()
        ]

    try:
        # Read configuration file
        config_parser = ConfigParser(interpolation=None)
        config_parser.read_file(open(sys_config_file, "r"))

        # Parse sections
        sys_config = dict()
        for s in config_parser.sections():
            sys_config[s] = dict(config_parser[s])
        for s in ("sauce", "cheese", "main_topping", "extra_toppings"):
            sys_config["pizza"][s] = parse_list(sys_config["pizza"][s])

        # Parse order status
        sys_config["status"] = {
            None: sys_config["status-label"]["else"],
        }
        for k, v in sys_config["status-id"].items():
            sys_config["status-id"][k] = int(v)
            sys_config["status"][int(v)] = sys_config["status-label"].get(k, "???")

        # Parse status parameters
        status_completed_when = parse_list(
            sys_config["state-store-orders"]["status_completed_when"]
        )
        sys_config["state-store-orders"]["status_completed_when"] = list()
        for status in status_completed_when:
            sys_config["state-store-orders"]["status_completed_when"].append(
                int(sys_config["status-id"][status])
            )

        sys_config["state-store-orders"]["status_watchdog_minutes"] = float(
            sys_config["state-store-orders"]["status_watchdog_minutes"]
        )
        sys_config["state-store-orders"]["status_invalid_timeout_minutes"] = float(
            sys_config["state-store-orders"]["status_invalid_timeout_minutes"]
        )

        # Filter by section (if required)
        if section is not None:
            sys_config = sys_config.get(section)

    except Exception:
        log_exception(
            f"Unable to parse system configuration file: {sys_config_file}\n",
            sys.exc_info(),
        )
        sys.exit(0)

    return sys_config


def log_ini(
    script: str,
    level: int = logging.INFO,
    to_disk: bool = True,
):
    handlers = [
        logging.StreamHandler(),
    ]
    if to_disk:
        handlers.append(
            TimedRotatingFileHandler(
                os.path.join(FOLDER_LOGS, f"{script}{EXTENSION_LOGS}"),
                when="midnight",
                backupCount=2,
            ),  # log to file and rotate
        )

    logging.basicConfig(
        format=f"\n\x00%(asctime)s.%(msecs)03d [%(levelname)s] {script}: %(message)s",
        level=level,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def log_event_received(event) -> None:
    event_data = [
        event.topic(),
        event.key(),
        event.value(),
    ]
    for n in range(len(event_data)):
        try:
            event_data[n] = event_data[n].decode()
        except Exception:
            pass
    logging.info(
        f"""Event received\n- Topic: {event_data[0]}\n- Key: {event_data[1]}\n- Value: {event_data[2]}"""
    )


def log_exception(message: str, sys_exc_info) -> None:
    exc_type, exc_obj, exc_tb = sys_exc_info
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    logging.critical(f"{message}: [{exc_type} | {fname}@{exc_tb.tb_lineno}] {exc_obj}")


def validate_cli_args(script: str) -> tuple:
    DEFAULT_SYS_CONFIG = "default.ini"
    if len(sys.argv) <= 1:
        logging.error(
            (
                f"Missing configuration files. Usage: {script}.py {{KAFKA_CONFIG_FILE}} {{SYS_CONFIG_FILE}}\n"
                "Where:\n"
                " - KAFKA_CONFIG_FILE: file under the folder 'config_kafka/'\n"
                " - SYS_CONFIG_FILE: file under the folder 'config_sys/' (default file is '{DEFAULT_SYS_CONFIG}')\n"
            )
        )
        sys.exit(0)

    if len(sys.argv) == 2:
        sys.argv.append(DEFAULT_SYS_CONFIG)

    if len(sys.argv) > 1 and sys.argv[1].startswith("webapp:"):
        # If started using gunicorn
        gunicorn_params = re.findall('"(.*?)"', sys.argv[1])
        config_kafka = gunicorn_params[0]
        config_sys = gunicorn_params[1] or DEFAULT_SYS_CONFIG
    else:
        # python script called directly (not via gunicorn)
        config_kafka = sys.argv[1]
        config_sys = sys.argv[2]

    kafka_config_file = os.path.join(
        FOLDER_CONFIG_KAFKA,
        config_kafka,
    )
    sys_config_file = os.path.join(
        FOLDER_CONFIG_SYS,
        config_sys,
    )

    if not os.path.isfile(kafka_config_file):
        logging.error(f"Kafka configuration file not found: {kafka_config_file}\n")
        sys.exit(0)
    elif not os.path.isfile(sys_config_file):
        logging.error(f"System configuration file not found: {sys_config_file}\n")
        sys.exit(0)

    return (
        kafka_config_file,
        sys_config_file,
    )


def save_pid(script: str):
    """Save PID to disk"""
    if not os.path.isdir(FOLDER_PID):
        os.mkdir(FOLDER_PID)
    with open(os.path.join(FOLDER_PID, f"{script}.pid"), "w") as f:
        f.write(str(os.getpid()))


def get_script_name(file: str) -> str:
    return os.path.splitext(os.path.basename(file))[0]


def get_string_status(status_dict: dict, status: int) -> str:
    return status_dict.get(
        status,
        f"""{status_dict.get(None, "Oops! Unknown status")} ({status})""",
    )


def set_producer_consumer(
    kafka_config_file: str,
    producer_extra_config: dict = None,
    consumer_extra_config: dict = None,
    disable_producer: bool = False,
    disable_consumer: bool = False,
) -> tuple:
    """Generate producer/config kafka objects"""
    producer_extra_config = producer_extra_config or dict()
    consumer_extra_config = consumer_extra_config or dict()

    # Read configuration file
    config_parser = ConfigParser(interpolation=None)
    config_parser.read_file(open(kafka_config_file, "r"))
    all_config = {k: dict(v) for k, v in dict(config_parser).items()}

    config_kafka = all_config["kafka"]

    # Set producer config
    if not disable_producer:
        producer_common_config = {
            "partitioner": "murmur2_random",
        }
        producer = Producer(
            {
                **producer_common_config,
                **config_kafka,
                **producer_extra_config,
            }
        )
    else:
        producer = None

    # Set consumer config
    if not disable_consumer:
        consumer_common_config = {
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
            "max.poll.interval.ms": 3000000,
        }
        consumer = Consumer(
            {
                **consumer_common_config,
                **config_kafka,
                **consumer_extra_config,
            }
        )
    else:
        consumer = None

    # Set admin client
    admin_client = AdminClient(config_kafka)

    return (
        all_config,
        producer,
        consumer,
        admin_client,
    )


def get_topic_partitions(
    admin_client,
    topic_name: str,
    default_partition_number: int = 1,
) -> int:
    partitions = admin_client.list_topics(topic_name).topics.get(topic_name)
    if partitions is not None:
        partitions = len(partitions.partitions)
    else:
        partitions = default_partition_number
    return partitions


def delivery_report(err, msg):
    """Reports the failure or success of an event delivery"""
    msg_key = "" if msg.key() is None else msg.key().decode()
    if err is not None:
        logging.error(f"Delivery failed for key '{msg_key}': {err}")
    else:
        msg_value = "" if msg.value() is None else msg.value().decode()
        logging.info(
            f"Event successfully produced\n- Topic: {msg.topic()}, partition #{msg.partition()}, Offset #{msg.offset()}\n- Key: {msg_key}\n- Value: {msg_value}"
        )


def timestamp_now() -> int:
    return int(datetime.datetime.now().timestamp() * 1000)


def http_request(
    url: str,
    headers: dict = None,
    payload: dict = None,
    method: str = "POST",
    username: str = None,
    password: str = None,
) -> tuple:
    """Generic HTTP request"""
    session = requests.Session()
    if username and password:
        session.auth = (username, password)

    if method == "GET":
        session = session.get
    elif method == "PUT":
        session = session.put
    elif method == "PATCH":
        session = session.patch
    elif method == "DELETE":
        session = session.delete
    else:
        session = session.post
    try:
        response = session(
            url,
            headers=headers,
            json=payload,
        )
        return (response.status_code, response.text)
    except requests.exceptions.Timeout:
        logging.error(f"Unable to send request to '{url}': timeout")
        return (408, {err})
    except requests.exceptions.TooManyRedirects:
        logging.error(f"Unable to send request to '{url}': too many redirects")
        return (302, {err})
    except Exception as err:
        logging.error(f"Unable to send request to '{url}': {err}")
        return (500, {err})


def ksqldb(
    end_point: str,
    statement: str,
    username: str = None,
    password: str = None,
    offset_reset_earliest: bool = True,
):
    """Submit HTTP POST request to ksqlDB"""
    try:
        # Clean-up statement
        statement = statement.replace("\r", " ")
        statement = statement.replace("\t", " ")
        statement = statement.replace("\n", " ")
        while statement.find("  ") > -1:
            statement = statement.replace("  ", " ")

        url = f"{end_point.strip('/')}/ksql"
        status_code, response = http_request(
            url,
            headers={
                "Accept": "application/vnd.ksql.v1+json",
                "Content-Type": "application/vnd.ksql.v1+json; charset=utf-8",
            },
            payload={
                "ksql": statement,
                "streamsProperties": {
                    "ksql.streams.auto.offset.reset": "earliest"
                    if offset_reset_earliest
                    else "latest",
                    "ksql.streams.cache.max.bytes.buffering": "0",
                },
            },
            username=username,
            password=password,
        )
        if status_code == 200:
            logging.debug(f"ksqlDB ({status_code}): {statement}")
        else:
            raise Exception(f"{response} (Status code {status_code})")
    except Exception as err:
        logging.error(f"Unable to send request to '{url}': {err}")


###################
# Generic classes #
###################
class GracefulShutdown:
    """Class/context manager to manage graceful shutdown"""

    def __init__(self, consumer=None):
        self.was_signal_set = False
        self.safe_to_terminate = True
        self.consumer = consumer
        # Set signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def __enter__(self):
        self.safe_to_terminate = False
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.safe_to_terminate = True
        if self.was_signal_set:
            if self.consumer is not None:
                try:
                    # Close down consumer to commit final offsets.
                    logging.info("Closing consumer in consumer group...")
                    self.consumer.close()
                    logging.info("Consumer in consumer group successfully closed")
                except Exception:
                    log_exception(
                        "Unable to close consumer group",
                        sys.exc_info(),
                    )
            self.signal_handler(signal.SIGTERM, None)

    def signal_handler(self, sig, frame):
        if not self.was_signal_set:
            logging.info("Starting graceful shutdown...")
        if self.safe_to_terminate:
            logging.info("Graceful shutdown completed")
            sys.exit(0)
        self.was_signal_set = True
