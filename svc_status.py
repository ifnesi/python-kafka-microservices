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

# Microservice to set order status

import sys
import json
import signal

from utils import DB, set_producer_consumer, get_script_name, log, save_pid


# Global variables
SCRIPT = get_script_name(__file__)
CONSUME_TOPICS = ["pizza-status"]
ORDERS_DB = "orders.db"
ORDER_TABLE = "orders"
abort_script = True
signal_set = False


# General functions
def signal_handler(sig, frame):
    global signal_set, abort_script
    if not signal_set:
        log("INFO", SCRIPT, "Starting graceful shutdown...")
    if abort_script:
        log("INFO", SCRIPT, "Graceful shutdown completed")
        sys.exit(0)
    signal_set = True


def get_pizza_status():
    """Subscribe to pizza-status topic to update in-memory DB (order_ids dict)"""
    global signal_set, abort_script
    consumer.subscribe(CONSUME_TOPICS)
    log(
        "INFO",
        SCRIPT,
        f"Subscribed to topic(s): {', '.join(CONSUME_TOPICS)}",
    )
    while True:
        abort_script = False
        event = consumer.poll(1.0)
        if event is not None:
            if event.error():
                log(
                    "ERROR",
                    SCRIPT,
                    event.error(),
                )
            else:
                try:
                    order_id = event.key().decode()
                    with DB(ORDERS_DB, ORDER_TABLE) as db:
                        order_data = db.get_order_id(
                            order_id,
                        )
                        if order_data is not None:
                            try:
                                pizza_status = json.loads(event.value().decode()).get(
                                    "status", -1
                                )
                            except Exception as err1:
                                pizza_status = -999
                                log(
                                    "ERROR",
                                    SCRIPT,
                                    f"Error when processing event.value() {event.value()}: {err1}",
                                )
                            finally:
                                log(
                                    "INFO",
                                    SCRIPT,
                                    f"Order ID '{order_id}' had its status updated to {pizza_status}",
                                )
                                db.update_order_status(
                                    order_id,
                                    pizza_status,
                                )
                        else:
                            log(
                                "ERROR",
                                SCRIPT,
                                f"Order ID not found: {order_id}",
                            )

                except Exception as err2:
                    log(
                        "ERROR",
                        SCRIPT,
                        f"Error when processing event.key() {event.key()}: {err2}",
                    )
        abort_script = True
        if signal_set:
            signal_handler(signal.SIGTERM, None)


# Set consumer object
_, consumer = set_producer_consumer(
    sys.argv[1],
    disable_producer=True,
    consumer_extra_config={
        "auto.offset.reset": "earliest",
        "group.id": "pizza_status",
        "enable.auto.commit": True,
    },
)

if __name__ == "__main__":
    # Save PID
    save_pid(SCRIPT)

    # Set signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # SQLite
    with DB(ORDERS_DB, ORDER_TABLE) as db:
        db.initialise_table()

    # Start consumer before starting the web app
    get_pizza_status()
