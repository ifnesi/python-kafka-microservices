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

# Microservice to deliver pizzas

import sys
import json
import time
import logging

from utils import (
    DB,
    GracefulShutdown,
    log_ini,
    save_pid,
    delivery_report,
    get_script_name,
    validate_cli_args,
    set_producer_consumer,
)


# Global variables
PRODUCE_TOPIC_STATUS = "pizza-status"
TOPIC_PIZZA_ORDERED = "pizza-ordered"
TOPIC_PIZZA_BAKED = "pizza-baked"
CONSUME_TOPICS = [TOPIC_PIZZA_ORDERED, TOPIC_PIZZA_BAKED]
CUSTOMER_DB = "customers.db"
CUSTOMER_TABLE = "customers"
SCRIPT = get_script_name(__file__)
log_ini(SCRIPT)
graceful_shutdown = None
producer, consumer = None, None


# General functions
def update_pizza_status(
    order_id: str,
    status: int,
):
    with graceful_shutdown as _:
        # Produce to kafka topic
        producer.produce(
            PRODUCE_TOPIC_STATUS,
            key=order_id,
            value=json.dumps(
                {
                    "status": status,
                }
            ).encode(),
        )
        producer.flush()


def receive_pizza_baked():
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
                        order_id = event.key().decode()
                        topic = event.topic()

                        if topic == TOPIC_PIZZA_ORDERED:
                            # Early warning that a pizza must be delivered once ready
                            try:
                                order_details = json.loads(event.value().decode())
                                order = order_details.get("order", dict())
                                customer_id = order.get("customer_id", "0000")
                                # Add to DB order_id <> customer_id
                                # In a real life scenatio this microservices would have the delivery address of the customer_id
                                with DB(CUSTOMER_DB, CUSTOMER_TABLE) as db:
                                    db.add_customer(order_id, customer_id)
                                logging.info(
                                    f"Early warning to deliver order '{order_id}' to customer_id '{customer_id}'"
                                )

                            except Exception as err1:
                                logging.error(
                                    f"Error when processing event.value() {event.value()}: {err1}"
                                )

                        elif topic == TOPIC_PIZZA_BAKED:
                            # Pizza ready to be delivered
                            # Get customer_id (and address in a real life scenario) based on the order_id
                            with DB(CUSTOMER_DB, CUSTOMER_TABLE) as db:
                                customer_id = db.get_order_id_customer(order_id)[
                                    "customer_id"
                                ]

                            if customer_id is not None:
                                # Delivery pizza (blocking point as it is not using asyncio, but that is for demo purposes)
                                delivery_time = int(customer_id, 16) % 10 + 5
                                logging.info(
                                    f"Deliverying order '{order_id}' for customer_id '{customer_id}', delivery time is {delivery_time} second(s)"
                                )
                                time.sleep(delivery_time)
                                logging.info(
                                    f"Order '{order_id}' delivered to customer_id '{customer_id}'"
                                )

                                # Update kafka topics (pizza delivered)
                                update_pizza_status(
                                    order_id,
                                    400,
                                )

                            else:
                                logging.warning(
                                    f"customer_id '{customer_id}' not found (Order '{order_id}')"
                                )
                                # Update kafka topics (error with order)
                                update_pizza_status(
                                    order_id,
                                    999,
                                )

                    except Exception as err2:
                        logging.error(
                            f"Error when processing event.key() {event.key()}: {err2}"
                        )
                # Manual commit
                consumer.commit(asynchronous=False)


if __name__ == "__main__":
    # Save PID
    save_pid(SCRIPT)

    # Set producer/consumer objects
    validate_cli_args(SCRIPT)
    producer, consumer = set_producer_consumer(
        sys.argv[1],
        producer_extra_config={
            "on_delivery": delivery_report,
        },
        consumer_extra_config={
            "group.id": "pizza_delivery",
        },
    )

    # Set signal handler
    graceful_shutdown = GracefulShutdown(consumer=consumer)

    # SQLite
    with graceful_shutdown as _:
        with DB(CUSTOMER_DB, CUSTOMER_TABLE) as db:
            db.create_customer_table()
            db.delete_past_timestamp(hours=2)

    # Start consumer group
    receive_pizza_baked()
