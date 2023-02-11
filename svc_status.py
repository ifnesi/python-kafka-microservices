import sys
import json

from utils import DB, set_producer_consumer, get_script_name, log, save_pid


# Global variables
SCRIPT = get_script_name(__file__)
CONSUME_TOPICS = ["pizza-status"]
ORDERS_DB = "orders.db"
ORDER_TABLE = "orders"


# General functions
def get_pizza_status():
    """Subscribe to pizza-status topic to update in-memory DB (order_ids dict)"""
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


# Set producer/consumer objects
producer, consumer = set_producer_consumer(
    sys.argv[1],
    consumer_extra_config={
        "auto.offset.reset": "earliest",
        "group.id": "pizza_status",
        "enable.auto.commit": True,
    },
)

if __name__ == "__main__":
    # Save PID
    save_pid(SCRIPT)

    # SQLite
    with DB(ORDERS_DB, ORDER_TABLE) as db:
        db.initialise_table()

    # Start consumer before starting the web app
    get_pizza_status()
