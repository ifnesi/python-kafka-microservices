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

# Flask webapp

import sys
import json
import uuid
import signal
import hashlib
import datetime

from flask import Flask, render_template, request

from utils import (
    DB,
    log,
    save_pid,
    get_script_name,
    delivery_report,
    set_producer_consumer,
)


# Global variables
SCRIPT = get_script_name(__file__)
PRODUCE_TOPIC = "pizza-ordered"
ORDERS_DB = "orders.db"
ORDER_TABLE = "orders"
abort_script = True
signal_set = False

app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates",
)


# Set producer/consumer objects
producer, _ = set_producer_consumer(
    sys.argv[1],
    producer_extra_config={
        "on_delivery": delivery_report,
    },
    disable_consumer=True,
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


# Flask routing
@app.route("/", methods=["GET"])
def view_menu():
    """View menu to order a pizza"""
    return render_template(
        "menu.html",
        title="Menu",
        sauces=[
            "Tomato",
            "Organic tomato",
            "Pesto",
            "Marinara",
            "Buffalo",
            "Hummus",
        ],
        cheeses=[
            "Mozzarella",
            "Provolone",
            "Cheddar",
            "Ricotta",
            "Gouda",
            "Gruyere",
        ],
        main_toppings=[
            "Pepperoni",
            "Sausage",
            "Chicken",
            "Pork",
            "Minced meat",
            "Vegan meat",
        ],
        extra_toppings=[
            "Mushroom",
            "Onion",
            "Eggs",
            "Black olives",
            "Green pepper",
            "Fresh garlic",
        ],
    )


@app.route("/", methods=["POST"])
def order_pizza():
    """Process pizza order request"""
    global signal_set, abort_script
    abort_script = False

    # Generate order unique ID
    order_id = uuid.uuid4().hex[-5:]

    # Get request form
    request_form = dict(request.form)
    request_form.pop("extra_topping", None)

    # Generate customer ID (in a real world situation that would come from the customer id logged in to the webapp)
    customer_id = hashlib.md5(request_form["name"].encode()).hexdigest()

    # Get extra topping list
    extra_toppings = request.form.getlist("extra_topping") or list()

    order_details = {
        "status": 100,
        "timestamp": int(datetime.datetime.now().timestamp() * 1000),
        "order": {
            "extra_toppings": extra_toppings,
            "customer_id": customer_id,
            **request_form,
        },
    }

    # Add order to DB
    with DB(ORDERS_DB, ORDER_TABLE) as db:
        db.add_order(
            order_id,
            order_details,
        )

    # Produce to kafka topic
    producer.produce(
        PRODUCE_TOPIC,
        key=order_id,
        value=json.dumps(order_details).encode(),
    )
    producer.flush()
    abort_script = True
    if signal_set:
        signal_handler(signal.SIGTERM, None)

    return render_template(
        "order_confirmation.html",
        title="Confirmation",
        order_id=order_id,
        extra_toppings=", ".join(extra_toppings),
        **request_form,
    )


@app.route("/orders", methods=["GET"])
def view_orders():
    """View all orders"""
    with DB(ORDERS_DB, ORDER_TABLE) as db:
        db.delete_old_orders(hours=2)
        return render_template(
            "view_orders.html",
            title="Orders",
            order_ids=db.get_orders(),
        )


@app.route("/orders/<order_id>", methods=["GET"])
def get_order(order_id):
    """View order by order_id"""
    with DB(ORDERS_DB, ORDER_TABLE) as db:
        order_details = db.get_order_id(order_id)
        if order_details is not None:
            # Order exists
            return render_template(
                "view_order.html",
                title="Order",
                order_id=order_id,
                timestamp=datetime.datetime.fromtimestamp(
                    order_details["timestamp"] / 1000
                ).strftime("%Y-%b-%d %H:%M:%S"),
                status=order_details["status_str"],
                name=order_details["name"],
                order=f"""Sauce: {order_details["sauce"]}<br>
                        Cheese: {order_details["cheese"]}<br>
                        Main: {order_details["topping"]}<br>
                        Extras: {order_details["extras"]}""",
            )
        else:
            # Order does not exists
            return render_template(
                "view_order.html",
                title="Order",
                error=f"Order ID not found: {order_id}",
                order_id=order_id,
            )


if __name__ == "__main__":
    # Save PID
    save_pid(SCRIPT)

    # Set signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # SQLite
    with DB(ORDERS_DB, ORDER_TABLE) as db:
        db.initialise_table()
        db.delete_old_orders(hours=2)

    # Start Flask web app
    app.run(
        host="localhost",
        port=8000,
        debug=True,
    )
