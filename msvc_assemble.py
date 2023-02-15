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

# Microservice to assemble pizzas

import sys
import json
import time
import hashlib
import logging

from utils import (
    GracefulShutdown,
    log_ini,
    save_pid,
    log_exception,
    delivery_report,
    get_script_name,
    validate_cli_args,
    log_event_received,
    get_system_config,
    set_producer_consumer,
)


####################
# Global variables #
####################
SCRIPT = get_script_name(__file__)
log_ini(SCRIPT)

# Validate command arguments
validate_cli_args(SCRIPT)

# Get system config file
SYS_CONFIG = get_system_config(sys.argv[2])
PRODUCE_TOPIC_STATUS = SYS_CONFIG["kafka-topics"]["pizza_status"]
PRODUCE_TOPIC_ASSEMBLED = SYS_CONFIG["kafka-topics"]["pizza_assembled"]
CONSUME_TOPICS = [
    SYS_CONFIG["kafka-topics"]["pizza_ordered"],
]

# Set producer/consumer objects
PRODUCER, CONSUMER = set_producer_consumer(
    sys.argv[1],
    producer_extra_config={
        "on_delivery": delivery_report,
    },
    consumer_extra_config={
        "group.id": SYS_CONFIG["kafka-consumer-group-id"]["microservice_assembled"],
    },
)

# Set signal handler
GRACEFUL_SHUTDOWN = GracefulShutdown(consumer=CONSUMER)


#####################
# General functions #
#####################
def pizza_assembled(order_id: str, baking_time: int):
    with GRACEFUL_SHUTDOWN as _:
        # Produce to kafka topic
        PRODUCER.produce(
            PRODUCE_TOPIC_ASSEMBLED,
            key=order_id,
            value=json.dumps(
                {
                    "baking_time": baking_time,
                }
            ).encode(),
        )
        PRODUCER.flush()


def update_pizza_status(
    order_id: str,
    status: int,
):
    with GRACEFUL_SHUTDOWN as _:
        # Produce to kafka topic
        PRODUCER.produce(
            PRODUCE_TOPIC_STATUS,
            key=order_id,
            value=json.dumps(
                {
                    "status": status,
                }
            ).encode(),
        )
        PRODUCER.flush()


def receive_orders():
    CONSUMER.subscribe(CONSUME_TOPICS)
    logging.info(f"Subscribed to topic(s): {', '.join(CONSUME_TOPICS)}")
    while True:
        with GRACEFUL_SHUTDOWN as _:
            event = CONSUMER.poll(0.25)
            if event is not None:
                if event.error():
                    logging.error(event.error())
                else:
                    try:
                        log_event_received(event)

                        order_id = event.key().decode()
                        try:
                            order_details = json.loads(event.value().decode())
                            order = order_details.get("order", dict())
                        except Exception:
                            log_exception(
                                f"Error when processing event.value() {event.value()}",
                                sys.exc_info(),
                            )

                        else:
                            seed = int(
                                hashlib.md5(
                                    f"""{order["sauce"]}@{order["cheese"]}@{",".join(order["extra_toppings"])}@{order["main_topping"]}""".encode()
                                ).hexdigest()[-4:],
                                16,
                            )

                            # Assemble pizza (blocking point as it is not using asyncio, but that is for demo purposes)
                            assembling_time = seed % 5 + 2
                            logging.info(
                                f"Preparing order '{order_id}', assembling time is {assembling_time} second(s)"
                            )
                            time.sleep(assembling_time)
                            logging.info(f"Order '{order_id}' is assembled!")

                            # Update kafka topics
                            baking_time = seed % 10 + 10
                            pizza_assembled(
                                order_id,
                                baking_time,
                            )
                            update_pizza_status(
                                order_id,
                                SYS_CONFIG["status-id"]["in_the_oven"],
                            )

                    except Exception:
                        log_exception(
                            f"Error when processing event.key() {event.key()}",
                            sys.exc_info(),
                        )

                # Manual commit
                CONSUMER.commit(asynchronous=False)


########
# Main #
########
if __name__ == "__main__":
    # Save PID
    save_pid(SCRIPT)

    # Start consumer
    receive_orders()
