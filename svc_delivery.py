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
import signal

from utils import set_producer_consumer, delivery_report, get_script_name, log, save_pid


# Global variables
order_ids = dict()
SCRIPT = get_script_name(__file__)
PRODUCE_TOPIC_STATUS = "pizza-status"
TOPIC_PIZZA_ORDERED = "pizza-ordered"
TOPIC_PIZZA_BAKED = "pizza-baked"
CONSUME_TOPICS = [TOPIC_PIZZA_ORDERED, TOPIC_PIZZA_BAKED]
abort_script = True
signal_set = False


# Set producer/consumer objects
producer, consumer = set_producer_consumer(
    sys.argv[1],
    producer_extra_config={
        "on_delivery": delivery_report,
    },
    consumer_extra_config={
        "auto.offset.reset": "earliest",
        "group.id": "pizza_delivery",
        "enable.auto.commit": True,
    },
)


# General functions
def signal_handler(sig, frame):
    global signal_set, abort_script
    if not signal_set:
        log("INFO", SCRIPT, "Starting graceful shutdown...")
    if abort_script:
        log("INFO", SCRIPT, "Graceful shutdown completed")
        sys.exit(0)
    signal_set = True


def update_pizza_status(
    order_id: str,
    status: int,
):
    global signal_set, abort_script
    abort_script = False
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
    abort_script = True
    if signal_set:
        signal_handler(signal.SIGTERM, None)


def receive_pizza_baked():
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
                    topic = event.topic()
                    if topic == TOPIC_PIZZA_BAKED:
                        if order_id in order_ids.keys():
                            # Delivery pizza (blocking point as it is not using asyncio, but that is for demo purposes)
                            delivery_time = int(order_ids[order_id], 16) % 10 + 5
                            log(
                                "INFO",
                                SCRIPT,
                                f"Deliverying order '{order_id}' for customer_id '{order_ids[order_id]}', delivery time is {delivery_time} second(s)",
                            )
                            time.sleep(delivery_time)
                            log(
                                "INFO",
                                SCRIPT,
                                f"Order {order_id} is delivered!",
                            )
                            # Update kafka topics (pizza delivered)
                            update_pizza_status(
                                order_id,
                                400,
                            )
                        else:
                            # Update kafka topics (error with order)
                            update_pizza_status(
                                order_id,
                                999,
                            )

                    elif topic == TOPIC_PIZZA_ORDERED:
                        try:
                            order_details = json.loads(event.value().decode())
                            order = order_details.get("order", dict())
                            customer_id = order.get("customer_id", "0000")
                            order_ids[order_id] = customer_id
                        except Exception as err1:
                            log(
                                "ERROR",
                                SCRIPT,
                                f"Error when processing event.value() {event.value()}: {err1}",
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


if __name__ == "__main__":
    # Save PID
    save_pid(SCRIPT)

    # Set signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    receive_pizza_baked()
