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
    GracefulShutdown,
    log_ini,
    save_pid,
    get_hostname,
    log_exception,
    timestamp_now,
    delivery_report,
    get_script_name,
    get_system_config,
    validate_cli_args,
    log_event_received,
    set_producer_consumer,
    import_state_store_class,
)


####################
# Global variables #
####################
SCRIPT = get_script_name(__file__)
HOSTNAME = get_hostname()
log_ini(SCRIPT)

# Validate command arguments
kafka_config_file, sys_config_file = validate_cli_args(SCRIPT)

# Get system config file
SYS_CONFIG = get_system_config(sys_config_file)

# Set producer/consumer objects
PENDING_ORDER = "PENDING"
PRODUCE_TOPIC_DELIVERED = SYS_CONFIG["kafka-topics"]["pizza_delivered"]
PRODUCE_TOPIC_PENDING = SYS_CONFIG["kafka-topics"]["pizza_pending"]
PRODUCE_TOPIC_STATUS = SYS_CONFIG["kafka-topics"]["pizza_status"]
TOPIC_PIZZA_ORDERED = SYS_CONFIG["kafka-topics"]["pizza_ordered"]
TOPIC_PIZZA_BAKED = SYS_CONFIG["kafka-topics"]["pizza_baked"]
CONSUME_TOPICS = [TOPIC_PIZZA_ORDERED, TOPIC_PIZZA_BAKED]
_, PRODUCER, CONSUMER, _ = set_producer_consumer(
    kafka_config_file,
    producer_extra_config={
        "on_delivery": delivery_report,
        "client.id": f"""{SYS_CONFIG["kafka-client-id"]["microservice_delivery"]}_{HOSTNAME}""",
    },
    consumer_extra_config={
        "group.id": f"""{SYS_CONFIG["kafka-consumer-group-id"]["microservice_delivery"]}_{HOSTNAME}""",
        "client.id": f"""{SYS_CONFIG["kafka-client-id"]["microservice_delivery"]}_{HOSTNAME}""",
    },
)

# Set signal handler
GRACEFUL_SHUTDOWN = GracefulShutdown(consumer=CONSUMER)

# State Store (Get DB class dynamically)
DB = import_state_store_class(SYS_CONFIG["state-store-orders"]["db_module_class"])
CUSTOMER_DB = SYS_CONFIG["state-store-delivery"]["name"]
with GRACEFUL_SHUTDOWN as _:
    with DB(
        CUSTOMER_DB,
        sys_config=SYS_CONFIG,
    ) as db:
        db.create_customer_table()
        db.delete_past_timestamp(
            SYS_CONFIG["state-store-delivery"]["table_customers"],
            hours=int(
                SYS_CONFIG["state-store-delivery"]["table_customers_retention_hours"]
            ),
        )


#####################
# General functions #
#####################
def pizza_delivered(order_id: str):
    PRODUCER.produce(
        PRODUCE_TOPIC_DELIVERED,
        key=order_id,
        value=json.dumps(
            {
                "status": SYS_CONFIG["status-id"]["delivered"],
                "timestamp": timestamp_now(),
            }
        ).encode(),
    )
    PRODUCER.flush()


def pizza_pending(order_id: str):
    PRODUCER.produce(
        PRODUCE_TOPIC_PENDING,
        key=order_id,
        value=json.dumps(
            {
                "status": SYS_CONFIG["status-id"]["pending"],
                "timestamp": timestamp_now(),
            }
        ).encode(),
    )
    PRODUCER.flush()


def receive_pizza_baked():
    def deliver_pizza(
        order_id: str,
        customer_id: str,
        factor: int = 1,
    ):
        # Delivery pizza (blocking point as it is not using asyncio, but that is for demo purposes)
        delivery_time = factor * (int(customer_id, 16) % 10 + 5)
        logging.info(
            f"Deliverying order '{order_id}' for customer_id '{customer_id}', delivery time is {delivery_time} second(s)"
        )
        time.sleep(delivery_time)
        logging.info(f"Order '{order_id}' delivered to customer_id '{customer_id}'")
        # Update kafka topics (pizza delivered)
        pizza_delivered(order_id)

    CONSUMER.subscribe(CONSUME_TOPICS)
    logging.info(f"Subscribed to topic(s): {', '.join(CONSUME_TOPICS)}")
    while True:
        with GRACEFUL_SHUTDOWN as _:
            event = CONSUMER.poll(1)
            if event is not None:
                if event.error():
                    logging.error(event.error())
                else:
                    try:
                        # Add a little delay just to allow the logs on the previous micro-service to be displayed first
                        time.sleep(0.2)

                        log_event_received(event)

                        order_id = event.key().decode()
                        topic = event.topic()

                        if topic == TOPIC_PIZZA_ORDERED:
                            # Early warning that a pizza must be delivered once ready (usually it should arrive before the pizza is baked)
                            try:
                                order_details = json.loads(event.value().decode())
                                order = order_details.get("order", dict())
                                customer_id = order.get("customer_id", "0000")

                                # Check if it is a pending order, that happens when the early notification (for some reason) arrives after the notification the pizza is baked
                                is_pending = False
                                with DB(
                                    CUSTOMER_DB,
                                    sys_config=SYS_CONFIG,
                                ) as db:
                                    check_order = db.get_order_id_customer(order_id)
                                    if check_order is not None:
                                        if check_order["customer_id"] == PENDING_ORDER:
                                            is_pending = True

                                if is_pending:
                                    # Update customer_id for the order_id
                                    with DB(
                                        CUSTOMER_DB,
                                        sys_config=SYS_CONFIG,
                                    ) as db:
                                        db.update_customer(order_id, customer_id)
                                        deliver_pizza(
                                            order_id,
                                            customer_id,
                                            factor=2,  # penalised for not receiving the early warning before the notification the pizza is baked
                                        )

                                else:
                                    # In a real life scenario this microservices would have the delivery address of the customer_id
                                    with DB(
                                        CUSTOMER_DB,
                                        sys_config=SYS_CONFIG,
                                    ) as db:
                                        db.add_customer(order_id, customer_id)

                                    logging.info(
                                        f"Early warning to deliver order '{order_id}' to customer_id '{customer_id}'"
                                    )

                            except Exception:
                                log_exception(
                                    f"Error when processing event.value() {event.value()}",
                                    sys.exc_info(),
                                )

                        elif topic == TOPIC_PIZZA_BAKED:
                            # Pizza ready to be delivered
                            # Get customer_id (and address in a real life scenario) based on the order_id
                            with DB(
                                CUSTOMER_DB,
                                sys_config=SYS_CONFIG,
                            ) as db:
                                customer_id = db.get_order_id_customer(order_id)

                            if customer_id is not None:
                                deliver_pizza(
                                    order_id,
                                    customer_id["customer_id"],
                                    factor=1,
                                )

                            else:
                                logging.warning(
                                    f"customer_id not associated to any order or invalid order '{order_id or ''}'"
                                )

                                # Update kafka topics (error with order)
                                pizza_pending(order_id)

                                # Add order_id to the DB as "pending", that happens when the early notification (for some reason) arrives after the notification the pizza is baked
                                with DB(
                                    CUSTOMER_DB,
                                    sys_config=SYS_CONFIG,
                                ) as db:
                                    db.add_customer(order_id, PENDING_ORDER)

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
    receive_pizza_baked()
