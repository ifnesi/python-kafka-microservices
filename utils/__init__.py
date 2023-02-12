import os
import sqlite3
import datetime

from configparser import ConfigParser
from confluent_kafka import Producer, Consumer


def log(
    level: str,
    script: str,
    message: str,
):
    """Display log message on the console"""
    print(f"[{level} | {script}]: {message}")


def save_pid(script: str):
    PID_FOLDER = "pid"
    if not os.path.isdir(PID_FOLDER):
        os.mkdir(PID_FOLDER)
    with open(os.path.join(PID_FOLDER, f"{script}.pid"), "w") as f:
        f.write(str(os.getpid()))


def get_script_name(file: str) -> str:
    return os.path.splitext(os.path.basename(file))[0]


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
        consumer = Consumer(
            {
                **kafka_config,
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
        log(
            "ERROR",
            "---",
            "Delivery failed for Data record {msg.key()}: {err}",
        )
    else:
        msg_key = "" if msg.key() is None else msg.key().decode()
        msg_value = "" if msg.value() is None else msg.value().decode()
        log(
            "INFO",
            "---",
            f"Event successfully produced\n - Topic: {msg.topic()}\n - Partition: {msg.partition()}\n - Offset: {msg.offset()}\n - Key: {msg_key}\n - Value: {msg_value}",
        )


class DB:
    def __init__(
        self,
        orders_db: str,
        order_table: str,
    ):
        self.orders_db = orders_db
        self.order_table = order_table
        self.conn = None
        self.cur = None
        self.statuses = {
            -1: "Oops! Unknown Order ID",
            100: "Order received and being prepared",
            200: "Your pizza is in the oven",
            300: "Your pizza is out for delivery",
            400: "Your pizza is delivered",
            -999: "Oops! Invalid Order ID",
        }

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
            f"""DELETE FROM orders WHERE timestamp < {int(datetime.datetime.now().timestamp() * 1000) - hours * 60 * 60 * 1000}"""
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
            data["status_str"] = self.statuses.get(data["status"], "???")
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
                data_all[item["order_id"]]["status_str"] = self.statuses.get(
                    data_all[item["order_id"]]["status"], "???"
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
            f"""
        INSERT INTO {self.order_table} (order_id,timestamp,name,customer_id,status,sauce,cheese,topping,extras)
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
        )
        """
        )
        self.conn.commit()
