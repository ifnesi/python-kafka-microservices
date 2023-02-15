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
import hashlib
import logging
import datetime

from flask import Flask, render_template, request

from utils import (
    DB,
    GracefulShutdown,
    log_ini,
    save_pid,
    get_script_name,
    delivery_report,
    validate_cli_args,
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
PRODUCE_TOPIC = SYS_CONFIG["kafka-topics"]["pizza_ordered"]

# Set producer object
PRODUCER, _ = set_producer_consumer(
    sys.argv[1],
    producer_extra_config={
        "on_delivery": delivery_report,
    },
    disable_consumer=True,
)

# Set signal handler
GRACEFUL_SHUTDOWN = GracefulShutdown()

# SQLite
ORDERS_DB = SYS_CONFIG["sqlite-orders"]["db"]
ORDER_TABLE = SYS_CONFIG["sqlite-orders"]["table"]
with GRACEFUL_SHUTDOWN as _:
    with DB(ORDERS_DB, ORDER_TABLE) as db:
        db.create_order_table()
        db.delete_past_timestamp(hours=2)

# Webapp (Flask)
app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates",
)
log = logging.getLogger("werkzeug")
log.setLevel(logging.WARNING)


#################
# Flask routing #
#################
@app.route("/", methods=["GET"])
def view_menu():
    """View menu to order a pizza"""
    return render_template(
        "menu.html",
        title="Menu",
        sauces=SYS_CONFIG["pizza"]["sauce"],
        cheeses=SYS_CONFIG["pizza"]["cheese"],
        main_toppings=SYS_CONFIG["pizza"]["main_topping"],
        extra_toppings=SYS_CONFIG["pizza"]["extra_toppings"],
    )


@app.route("/", methods=["POST"])
def order_pizza():
    """Process pizza order request"""
    with GRACEFUL_SHUTDOWN as _:
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
        PRODUCER.produce(
            PRODUCE_TOPIC,
            key=order_id,
            value=json.dumps(order_details).encode(),
        )
        PRODUCER.flush()

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
    with GRACEFUL_SHUTDOWN as _:
        with DB(ORDERS_DB, ORDER_TABLE) as db:
            db.delete_past_timestamp(hours=2)
            return render_template(
                "view_orders.html",
                title="Orders",
                order_ids=db.get_orders(),
            )


@app.route("/orders/<order_id>", methods=["PUT"])
def get_order_ajax(order_id):
    """View order by order_id (AJAX call)"""
    with GRACEFUL_SHUTDOWN as _:
        with DB(ORDERS_DB, ORDER_TABLE) as db:
            order_details = db.get_order_id(order_id)
            if order_details is not None:
                return {
                    "str": order_details["status_str"],
                    "status": order_details["status"],
                }
    return ""


@app.route("/orders/<order_id>", methods=["GET"])
def get_order(order_id):
    """View order by order_id"""
    with GRACEFUL_SHUTDOWN as _:
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
                    status=order_details["status"],
                    status_str=order_details["status_str"],
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
                    error=f"Order '{order_id}' not found",
                    order_id=order_id,
                )


########
# Main #
########
if __name__ == "__main__":
    # Save PID
    save_pid(SCRIPT)

    # Start Flask web app
    app.run(
        host="localhost",
        port=8000,
        debug=True,
    )
