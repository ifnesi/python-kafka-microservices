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
import sys
import signal
import logging
import sqlite3
import datetime

from configparser import ConfigParser
from confluent_kafka import Producer, Consumer


# Generic functions
def get_system_config(
    config_file: str = "default.ini",
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
        file_name = os.path.join("config_sys", config_file)
        config_parser.read_file(open(file_name, "r"))

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
            sys_config["status"][int(v)] = sys_config["status-label"][k]

        # Filter by section (if required)
        if section is not None:
            sys_config = sys_config.get(section)

    except Exception:
        log_exception(
            f"Unable to parse system configuration file: {file_name}",
            sys.exc_info(),
        )

    return sys_config


def log_ini(
    script: str,
    level: int = logging.INFO,
):
    logging.basicConfig(
        format=f"\n({script}) %(levelname)s %(asctime)s.%(msecs)03d - %(message)s",
        level=level,
        datefmt="%H:%M:%S",
    )


def log_event_received(event) -> None:
    logging.info(
        f"""Event received from topic '{event.topic()},' key {event.key()}, value {event.value()}"""
    )


def log_exception(message: str, sys_exc_info) -> None:
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    logging.critical(f"{message}: [{exc_type} | {fname}@{exc_tb.tb_lineno}] {exc_obj}")


def validate_cli_args(script: str):
    if len(sys.argv) == 2:
        sys.argv.append("default.ini")
    elif len(sys.argv) <= 1:
        logging.error(
            (
                f"Missing configuration files. Usage: {script}.py {{KAFKA_CONFIG_FILE}} {{SYS_CONFIG_FILE}}\n"
                "Where:\n"
                " - KAFKA_CONFIG_FILE: file under the folder 'config_kafka/'\n"
                " - SYS_CONFIG_FILE: file under the folder 'config_sys/' (default file is 'default.ini')"
            )
        )
        sys.exit(0)
    else:
        kafka_config_file = os.path.join("config_kafka", sys.argv[1])
        if not os.path.isfile(kafka_config_file):
            logging.error(f"Kafka configuration file not found: {kafka_config_file}")
            sys.exit(0)
        sys_config_file = os.path.join("config_sys", sys.argv[2])
        if not os.path.isfile(sys_config_file):
            logging.error(f"System configuration file not found: {sys_config_file}")
            sys.exit(0)


def save_pid(script: str):
    """Save PID to disk"""
    PID_FOLDER = "pid"
    if not os.path.isdir(PID_FOLDER):
        os.mkdir(PID_FOLDER)
    with open(os.path.join(PID_FOLDER, f"{script}.pid"), "w") as f:
        f.write(str(os.getpid()))


def get_script_name(file: str) -> str:
    return os.path.splitext(os.path.basename(file))[0]


def get_string_status(status_dict: dict, status: int) -> str:
    return status_dict.get(
        status,
        f"""{status_dict.get(None, "Oops! Unknown status")} ({status})""",
    )


def set_producer_consumer(
    config_file: str,
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
    config_parser.read_file(
        open(
            os.path.join(
                "config_kafka",
                config_file,
            ),
            "r",
        )
    )

    config_kafka = dict(config_parser["kafka"])

    # Set producer config
    if not disable_producer:
        producer = Producer(
            {
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
                **config_kafka,
                **consumer_common_config,
                **consumer_extra_config,
            }
        )
    else:
        consumer = None

    return (
        producer,
        consumer,
    )


def delivery_report(err, msg):
    """Reports the failure or success of an event delivery"""
    if err is not None:
        logging.error(f"Delivery failed for Data record {msg.key()}: {err}")
    else:
        msg_key = "" if msg.key() is None else msg.key().decode()
        msg_value = "" if msg.value() is None else msg.value().decode()
        logging.info(
            f"Event successfully produced\n - Topic '{msg.topic()}', Partition #{msg.partition()}, Offset #{msg.offset()}\n - Key: {msg_key}\n - Value: {msg_value}"
        )


# Generic classes
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


class DB:
    """Class/context manager to connect to local DB"""

    def __init__(
        self,
        db_name: str,
        table_name: str,
        sys_config: dict = None,
    ):
        self.db_name = db_name
        self.table_name = table_name
        self.sys_config = sys_config
        self.conn = None
        self.cur = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.db_name)
        self.cur = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn is not None:
            try:
                self.conn.close()
            except:
                pass

    def create_customer_table(self):
        self.execute(
            f"""CREATE TABLE IF NOT EXISTS {self.table_name} (
                order_id TEXT PRIMARY KEY,
                timestamp INTEGER,
                customer_id TEXT
            )"""
        )
        self.conn.commit()

    def create_order_table(self):
        self.execute(
            f"""CREATE TABLE IF NOT EXISTS {self.table_name} (
                order_id TEXT PRIMARY KEY,
                timestamp INTEGER,
                name TEXT,
                customer_id TEXT,
                status INTEGER,
                sauce TEXT,
                cheese TEXT,
                topping TEXT,
                extras TEXT
            )"""
        )
        self.conn.commit()

    def delete_past_timestamp(self, hours: int = 1):
        self.execute(
            f"""DELETE FROM {self.table_name}
            WHERE timestamp < {int(datetime.datetime.now().timestamp() * 1000) - hours * 60 * 60 * 1000}"""
        )
        self.conn.commit()

    def execute(self, expression: str):
        return self.cur.execute(expression)

    def get_order_id_customer(
        self,
        order_id: str,
    ) -> dict:
        self.execute(f"SELECT * FROM {self.table_name} WHERE order_id='{order_id}'")
        data = self.cur.fetchone()
        if data is not None:
            cols = list(map(lambda x: x[0], self.cur.description))
            data = dict(zip(cols, data))
        return data

    def get_order_id(
        self,
        order_id: str,
    ) -> dict:
        self.execute(f"SELECT * FROM {self.table_name} WHERE order_id='{order_id}'")
        data = self.cur.fetchone()
        if data is not None:
            cols = list(map(lambda x: x[0], self.cur.description))
            data = dict(zip(cols, data))
            data["extras"] = ", ".join(data["extras"].split(","))
            data["status_str"] = get_string_status(
                self.sys_config["status"], data["status"]
            )
        return data

    def get_orders(
        self,
    ) -> dict:
        self.execute(f"SELECT * FROM {self.table_name} ORDER BY timestamp DESC")
        data = self.cur.fetchall()
        data_all = dict()
        if data:
            cols = list(map(lambda x: x[0], self.cur.description))
            for item in data:
                item = dict(zip(cols, item))
                data_all[item["order_id"]] = item
                data_all[item["order_id"]]["extras"] = ", ".join(
                    data_all[item["order_id"]]["extras"].split(",")
                )
                data_all[item["order_id"]]["status_str"] = get_string_status(
                    self.sys_config["status"],
                    data_all[item["order_id"]]["status"],
                )
                data_all[item["order_id"]][
                    "timestamp"
                ] = datetime.datetime.fromtimestamp(
                    data_all[item["order_id"]]["timestamp"] / 1000
                ).strftime(
                    "%Y-%b-%d %H:%M:%S"
                )
        return data_all

    def update_order_status(
        self,
        order_id: str,
        status: int,
    ):
        self.execute(
            f"""UPDATE {self.table_name} SET
                    status={status}
                WHERE order_id='{order_id}'
            """
        )
        self.conn.commit()

    def update_customer(
        self,
        order_id: str,
        customer_id: dict,
    ):
        self.execute(
            f"""UPDATE {self.table_name} SET
                    timestamp={int(datetime.datetime.now().timestamp() * 1000)},
                    customer_id='{customer_id}'
                WHERE order_id='{order_id}'
            """
        )
        self.conn.commit()

    def add_customer(
        self,
        order_id: str,
        customer_id: dict,
    ):
        self.execute(
            f"""INSERT INTO {self.table_name} (
                order_id,
                timestamp,
                customer_id
            )
            VALUES (
                '{order_id}',
                {int(datetime.datetime.now().timestamp() * 1000)},
                '{customer_id}'
            )"""
        )
        self.conn.commit()

    def add_order(
        self,
        order_id: str,
        order_details: dict,
    ):
        self.execute(
            f"""INSERT INTO {self.table_name} (
                order_id,
                timestamp,
                name,
                customer_id,
                status,
                sauce,
                cheese,
                topping,
                extras
            )
            VALUES (
                '{order_id}',
                {int(datetime.datetime.now().timestamp() * 1000)},
                '{order_details["order"]["name"]}',
                '{order_details["order"]["customer_id"]}',
                {self.sys_config["status-id"]["order_received"]},
                '{order_details["order"]["sauce"]}',
                '{order_details["order"]["cheese"]}',
                '{order_details["order"]["main_topping"]}',
                '{",".join(order_details["order"]["extra_toppings"])}'
            )"""
        )
        self.conn.commit()
