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

# Microservice to bake pizzas

import sys
import json
import time
import logging

from utils import (
    GracefulShutdown,
    log_ini,
    save_pid,
    delivery_report,
    get_script_name,
    validate_cli_args,
    set_producer_consumer,
)


# Global variables
PRODUCE_TOPIC_BAKED = "pizza-baked"
PRODUCE_TOPIC_STATUS = "pizza-status"
CONSUME_TOPICS = ["pizza-assembled"]
SCRIPT = get_script_name(__file__)
log_ini(SCRIPT)
graceful_shutdown = None
producer, consumer = None, None


# General functions
def pizza_baked(order_id: str):
    with graceful_shutdown as _:
        # Produce to kafka topic
        producer.produce(
            PRODUCE_TOPIC_BAKED,
            key=order_id,
        )
        producer.flush()


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


def receive_pizza_assembled():
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
                        try:
                            baking_time = json.loads(event.value().decode()).get(
                                "baking_time", 0
                            )
                        except Exception as err1:
                            logging.error(
                                f"Error when processing event.value() {event.value()}: {err1}"
                            )
                        else:
                            # Assemble pizza (blocking point as it is not using asyncio, but that is for demo purposes)
                            logging.info(
                                f"Preparing order '{order_id}', baking time is {baking_time} second(s)"
                            )
                            time.sleep(baking_time)
                            logging.info(f"Order '{order_id}' is baked!")

                            # Update kafka topics
                            pizza_baked(
                                order_id,
                            )
                            update_pizza_status(
                                order_id,
                                300,
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
            "group.id": "pizza_bake",
        },
    )

    # Set signal handler
    graceful_shutdown = GracefulShutdown(consumer=consumer)

    # Start consumer group
    receive_pizza_assembled()
