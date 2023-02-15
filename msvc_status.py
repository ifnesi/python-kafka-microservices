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
CONSUME_TOPICS = [
    SYS_CONFIG["kafka-topics"]["pizza_status"],
]

# Set consumer object
_, CONSUMER = set_producer_consumer(
    sys.argv[1],
    disable_producer=True,
    consumer_extra_config={
        "group.id": SYS_CONFIG["kafka-consumer-group-id"]["microservice_status"],
    },
)

# Set signal handler
GRACEFUL_SHUTDOWN = GracefulShutdown(consumer=CONSUMER)

# SQLite
ORDERS_DB = SYS_CONFIG["sqlite-orders"]["db"]
ORDER_TABLE = SYS_CONFIG["sqlite-orders"]["table"]
with GRACEFUL_SHUTDOWN as _:
    with DB(
        ORDERS_DB,
        ORDER_TABLE,
        sys_config=SYS_CONFIG,
    ) as db:
        db.create_order_table()
        db.delete_past_timestamp(hours=2)


#####################
# General functions #
#####################
def get_pizza_status():
    """Subscribe to pizza-status topic to update in-memory DB (order_ids dict)"""
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
                        with DB(
                            ORDERS_DB,
                            ORDER_TABLE,
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
                                        "status",
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

    # Start consumer
    get_pizza_status()
