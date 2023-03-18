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
import time
import logging

from threading import Thread


from utils import (
    GracefulShutdown,
    log_ini,
    save_pid,
    get_hostname,
    log_exception,
    get_script_name,
    validate_cli_args,
    get_string_status,
    log_event_received,
    get_system_config,
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

# Set consumer object
CONSUME_TOPICS = [
    SYS_CONFIG["kafka-topics"]["pizza_status"],
]
_, _, CONSUMER, _ = set_producer_consumer(
    kafka_config_file,
    disable_producer=True,
    consumer_extra_config={
        "group.id": f"""{SYS_CONFIG["kafka-consumer-group-id"]["microservice_status"]}_{HOSTNAME}""",
        "client.id": f"""{SYS_CONFIG["kafka-client-id"]["microservice_status"]}_{HOSTNAME}""",
    },
)

# Set signal handler
GRACEFUL_SHUTDOWN = GracefulShutdown(consumer=CONSUMER)

# State Store (Get DB class dynamically)
DB = import_state_store_class(SYS_CONFIG["state-store-orders"]["db_module_class"])
ORDERS_DB = SYS_CONFIG["state-store-orders"]["name"]
with GRACEFUL_SHUTDOWN as _:
    with DB(
        ORDERS_DB,
        sys_config=SYS_CONFIG,
    ) as db:
        db.create_order_table()
        db.delete_past_timestamp(
            SYS_CONFIG["state-store-orders"]["table_orders"],
            hours=int(SYS_CONFIG["state-store-orders"]["table_orders_retention_hours"]),
        )
        db.create_status_table()
        db.delete_past_timestamp(
            SYS_CONFIG["state-store-orders"]["table_status"],
            hours=int(SYS_CONFIG["state-store-orders"]["table_status_retention_hours"]),
        )


#####################
# General functions #
#####################
def thread_status_watchdog():
    """As this microservice is stateful it's needed a way to check if any status got stuck"""
    while True:
        with DB(
            ORDERS_DB,
            sys_config=SYS_CONFIG,
        ) as db:
            stuck_status = db.check_status_stuck()
            for order_id, data in stuck_status.items():
                logging.warning(f"Order '{order_id}' got stuck!")
                # Update order to set status as stuck
                db.update_order_status(
                    order_id,
                    SYS_CONFIG["status-id"]["stuck"],
                )
                # Delete order from status table (state store for statefulness)
                db.delete_stuck_status(order_id)
        time.sleep(SYS_CONFIG["state-store-orders"]["status_watchdog_minutes"] * 60)


def get_pizza_status():
    """Subscribe to pizza-status topic to update in-memory DB (order_ids dict)"""
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
                        log_event_received(event)

                        order_id = event.key().decode()
                        with DB(
                            ORDERS_DB,
                            sys_config=SYS_CONFIG,
                        ) as db:
                            order_data = db.get_order_id(
                                order_id,
                            )
                            if order_data is not None:
                                try:
                                    pizza_status = json.loads(
                                        event.value().decode()
                                    ).get(
                                        "STATUS",
                                        SYS_CONFIG["status-id"]["unknown"],
                                    )
                                except Exception:
                                    pizza_status = SYS_CONFIG["status-id"][
                                        "something_wrong"
                                    ]
                                    log_exception(
                                        f"Error when processing event.value() {event.value()}",
                                        sys.exc_info(),
                                    )
                                finally:
                                    logging.info(
                                        f"""Order '{order_id}' status updated: {get_string_status(SYS_CONFIG["status"], pizza_status)} ({pizza_status})"""
                                    )
                                    db.update_order_status(
                                        order_id,
                                        pizza_status,
                                    )
                                    # Add to status to check statefulness (daemon on msvc_status)
                                    db.upsert_status(
                                        order_id,
                                        pizza_status,
                                    )
                                    # Delete order from status table (state store for statefulness)
                                    if int(pizza_status) in (
                                        SYS_CONFIG["status-id"]["stuck"],
                                        SYS_CONFIG["status-id"]["cancelled"],
                                        SYS_CONFIG["status-id"]["delivered"],
                                        SYS_CONFIG["status-id"]["something_wrong"],
                                        SYS_CONFIG["status-id"]["unknown"],
                                    ):
                                        db.delete_stuck_status(order_id)

                            else:
                                logging.error(f"Order '{order_id}' not found")

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

    # Order status watchdog
    Thread(target=thread_status_watchdog, daemon=True).start()

    # Start consumer
    get_pizza_status()
