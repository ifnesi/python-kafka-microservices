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

from utils import set_producer_consumer, delivery_report, get_script_name, log, save_pid


# Global variables
SCRIPT = get_script_name(__file__)
PRODUCE_TOPIC_ASSEMBLED = "pizza-assembled"
PRODUCE_TOPIC_STATUS = "pizza-status"
CONSUME_TOPICS = ["pizza-ordered"]

# Set producer/consumer objects
producer, consumer = set_producer_consumer(
    sys.argv[1],
    producer_extra_config={
        "on_delivery": delivery_report,
    },
    consumer_extra_config={
        "auto.offset.reset": "earliest",
        "group.id": "pizza_assemble",
        "enable.auto.commit": True,
    },
)


def pizza_assembled(order_id: str, cooking_time: int):
    # Produce to kafka topic
    producer.produce(
        PRODUCE_TOPIC_ASSEMBLED,
        key=order_id,
        value=json.dumps(
            {
                "cooking_time": cooking_time,
            }
        ).encode(),
    )
    producer.flush()


def update_pizza_status(
    order_id: str,
    status: int,
):
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


def receive_orders():
    consumer.subscribe(CONSUME_TOPICS)
    log(
        "INFO",
        SCRIPT,
        f"Subscribed to topic(s): {', '.join(CONSUME_TOPICS)}",
    )
    while True:
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
                    try:
                        order_details = json.loads(event.value().decode())
                        order = order_details.get("order", dict())
                    except Exception as err1:
                        log(
                            "ERROR",
                            SCRIPT,
                            f"Error when processing event.value() {event.value()}: {err1}",
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
                        log(
                            "INFO",
                            SCRIPT,
                            f"Preparing order {order_id}, assembling time is {assembling_time} second(s)",
                        )
                        time.sleep(assembling_time)
                        log(
                            "INFO",
                            SCRIPT,
                            f"Order {order_id} is assembled!",
                        )

                        # Update kafka topics
                        cooking_time = seed % 10 + 10
                        pizza_assembled(
                            order_id,
                            cooking_time,
                        )
                        update_pizza_status(
                            order_id,
                            200,
                        )
                except Exception as err2:
                    log(
                        "ERROR",
                        SCRIPT,
                        f"Error when processing event.key() {event.key()}: {err2}",
                    )


if __name__ == "__main__":
    # Save PID
    save_pid(SCRIPT)

    receive_orders()
