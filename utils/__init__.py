import os
import sys
import signal
import logging
import sqlite3
import datetime

from configparser import ConfigParser
from confluent_kafka import Producer, Consumer


# Global variables
ORDER_STATUSES = {
    -1: "Oops! Unknown order",
    100: "Order received and being prepared",
    200: "Your pizza is in the oven",
    300: "Your pizza is out for delivery",
    400: "Your pizza was delivered",
    -999: "Oops! Invalid order",
}


# Generic functions
def log_ini(
    script: str,
    level: int = logging.INFO,
):
    logging.basicConfig(
        format=f"\n({script}) %(levelname)s %(asctime)s.%(msecs)03d - %(message)s",
        level=level,
        datefmt="%H:%M:%S",
    )


def validate_cli_args(script: str):
    if len(sys.argv) <= 1:
        logging.error(
            f"Missing configuration file. Usage: {script}.py {{CONFIGURATION_FILE}} (under the folder 'config/')",
        )
        sys.exit(0)
    else:
        config_file = os.path.join("config", sys.argv[1])
        if not os.path.isfile(config_file):
            logging.error(f"Configuration file not found: {config_file}")
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


def get_string_status(status: int) -> str:
    return ORDER_STATUSES.get(
        status,
        f"Oops! Unknown status ({status})",
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
                "config",
                config_file,
            ),
            "r",
        )
    )

    kafka_config = dict(config_parser["kafka"])

    # Set producer config
    if not disable_producer:
        producer = Producer(
            {
                **kafka_config,
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
                **kafka_config,
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
                    logging.info("Closing consumer group...")
                    self.consumer.close()
                    logging.info("Consumer group successfully closed")
                except Exception as err:
                    logging.error(f"Unable to close consumer group: {err}")
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
        orders_db: str,
        order_table: str,
    ):
        self.orders_db = orders_db
        self.order_table = order_table
        self.conn = None
        self.cur = None

    def __enter__(self):
        self.conn = sqlite3.connect(self.orders_db)
        self.cur = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn is not None:
            try:
                self.conn.close()
            except:
                pass

    def initialise_table(self):
        self.execute(
            f"""CREATE TABLE IF NOT EXISTS {self.order_table} (
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

    def delete_old_orders(self, hours: int = 1):
        self.execute(
            f"""DELETE FROM orders
            WHERE timestamp < {int(datetime.datetime.now().timestamp() * 1000) - hours * 60 * 60 * 1000}"""
        )
        self.conn.commit()

    def execute(self, expression: str):
        return self.cur.execute(expression)

    def get_order_id(
        self,
        order_id: str,
    ) -> dict:
        self.execute(f"SELECT * FROM {self.order_table} WHERE order_id='{order_id}'")
        data = self.cur.fetchone()
        if data is not None:
            cols = list(map(lambda x: x[0], self.cur.description))
            data = dict(zip(cols, data))
            data["extras"] = ", ".join(data["extras"].split(","))
            data["status_str"] = get_string_status(data["status"])
        return data

    def get_orders(
        self,
    ) -> dict:
        self.execute(f"SELECT * FROM {self.order_table} ORDER BY timestamp DESC")
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
                    data_all[item["order_id"]]["status"]
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
            f"UPDATE {self.order_table} SET status={status} WHERE order_id='{order_id}'"
        )
        self.conn.commit()

    def add_order(
        self,
        order_id: str,
        order_details: dict,
    ):
        self.execute(
            f"""INSERT INTO {self.order_table} (
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
                100,
                '{order_details["order"]["sauce"]}',
                '{order_details["order"]["cheese"]}',
                '{order_details["order"]["main_topping"]}',
                '{",".join(order_details["order"]["extra_toppings"])}'
            )"""
        )
        self.conn.commit()
