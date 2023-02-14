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
import logging


from utils import (
    DB,
    GracefulShutdown,
    log_ini,
    save_pid,
    log_exception,
    get_script_name,
    validate_cli_args,
    get_string_status,
    log_event_received,
    set_producer_consumer,
)


# Global variables
CONSUME_TOPICS = ["pizza-status"]
ORDERS_DB = "orders.db"
ORDER_TABLE = "orders"
SCRIPT = get_script_name(__file__)
log_ini(SCRIPT)
graceful_shutdown = None
consumer = None


# General functions
def get_pizza_status():
    """Subscribe to pizza-status topic to update in-memory DB (order_ids dict)"""
    consumer.subscribe(CONSUME_TOPICS)
    logging.info(f"Subscribed to topic(s): {', '.join(CONSUME_TOPICS)}")
    while True:
        with graceful_shutdown as _:
            event = consumer.poll(0.25)
            if event is not None:
                if event.error():
                    logging.error(event.error())
                else:
                    try:
                        log_event_received(event)

                        order_id = event.key().decode()
                        with DB(ORDERS_DB, ORDER_TABLE) as db:
                            order_data = db.get_order_id(
                                order_id,
                            )
                            if order_data is not None:
                                try:
                                    pizza_status = json.loads(
                                        event.value().decode()
                                    ).get("status", -200)
                                except Exception:
                                    pizza_status = -999
                                    log_exception(
                                        f"Error when processing event.value() {event.value()}",
                                        sys.exc_info(),
                                    )
                                finally:
                                    logging.info(
                                        f"Order '{order_id}' status updated: {get_string_status(pizza_status)} ({pizza_status})"
                                    )
                                    db.update_order_status(
                                        order_id,
                                        pizza_status,
                                    )
                            else:
                                logging.error(f"Order '{order_id}' not found")

                    except Exception:
                        log_exception(
                            f"Error when processing event.key() {event.key()}",
                            sys.exc_info(),
                        )

                # Manual commit
                consumer.commit(asynchronous=False)


if __name__ == "__main__":
    # Save PID
    save_pid(SCRIPT)

    # Set consumer object
    validate_cli_args(SCRIPT)
    _, consumer = set_producer_consumer(
        sys.argv[1],
        disable_producer=True,
        consumer_extra_config={
            "group.id": "pizza_status",
        },
    )

    # Set signal handler
    graceful_shutdown = GracefulShutdown(consumer=consumer)

    # SQLite
    with graceful_shutdown as _:
        with DB(ORDERS_DB, ORDER_TABLE) as db:
            db.create_order_table()
            db.delete_past_timestamp(hours=2)

    # Start consumer group
    get_pizza_status()
